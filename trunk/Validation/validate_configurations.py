"""main script for running validation sweeps in an ordered manner"""
import copy
import os
import multiprocessing
from collections import defaultdict
from itertools import product
# import pandas as pd
from run_pg import FlightRun
import extras as aux
import plots

LOGO = r"""
-------------------------------------------------
    ____  __    __      ______
   / __ \/ /_  / /_  __/ ____/_______  ___  ____
  / /_/ / __ \/ / / / / / __/ ___/ _ \/ _ \/ __ \
 / ____/ / / / / /_/ / /_/ / /  /  __/  __/ / / /
/_/   /_/ /_/_/\__, /\____/_/   \___/\___/_/ /_/
              /____/
-------------------------------------------------
"""


class RunAll:
    """class that contains the things needed to run all the flight evaluations"""

    def __init__(self, batch_name):
        # Start by defining the directories
        print("SETTING DIRECTORIES")
        self.out_d = aux.make_cat_dir("Outputs", batch_name)  # OUTPUT DIRECTORY
        self.json_d = aux.make_cat_dir(self.out_d, "JSON")  # JSON DIRECTORY
        self.plots_d = aux.make_cat_dir(self.out_d, "FLIGHT_PLOTS")  # PLOTS DIRECTORY
        self.extra_d = aux.make_cat_dir(self.out_d, "EXTRA")  # EXTRA DIRECTORY
        self.output_data = None

    def _unpack_arg_list(self, aa):
        """
        Unpack the arguments list using itertools.product()
        to avoid having 7 nested loops.
        The parameters are ordered like this because this is
        the order they are input into the mission inputs of
        the aircraft class.
        To avoid creating dozens of repeated Traditional
        configurations (iterations of Cell and Phi) this is
        done to unpack the arguments first while separating
        the traditional configurations instead of blindly
        using starmap() on the processing stage.
        Returns a list of tuples.
        """
        # Create copy of the inputs since the inputs are still
        # used as is elsewhere in the code and it is easier
        # to edit the dictionary directly like this
        a=copy.deepcopy(aa)
        configs = []

        # Forces traditional configuration if phi = 0, this enables
        # plotting of the traditional config next to the hybrid
        # one when evaluationg the effect of phi without having to
        # iterate the powerplant explicitly.
        # This preserves cell type iterations so that they all
        # show up in the graphs without gaps even when making
        # comparisons that start at Phi = 0
        if 0 in a["Base Phi"]:
            a["Base Phi"].remove(0)
            configs += product(
                a["Range"],
                a["Payload"],
                ["Traditional"],
                a["Cell"],
                a["Cell Specific Energy"],
                a["Cell Specific Power"],
                [0],
                a["Mission Name"],
            )

        # Remove the references to the Cell parameters in
        # traditional configurations to avoid repeats
        if "Traditional" in a["Powerplant"]:
            configs += product(
                a["Range"],
                a["Payload"],
                ["Traditional"],
                [None],
                [None],
                [None],
                [0],
                a["Mission Name"],
            )

        if "Hybrid" in a["Powerplant"]:
            configs += product(
                a["Range"],
                a["Payload"],
                ["Hybrid"],
                a["Cell"],
                a["Cell Specific Energy"],
                a["Cell Specific Power"],
                a["Base Phi"],
                a["Mission Name"],
            )
        # print(*configs, sep ='\n')
        # This removes duplicates from the list that may
        # have been caused by the zero phi special case
        for i,_ in enumerate(configs):
            # print(f"I NUMBER:{i}")
            for j,_ in enumerate(configs):
                # print(f"J NUMBER:{j}")
                if i != j:
                    if configs[i] == configs[j]:
                        del configs[j]

        return configs

    def run_and_plot(self, flightargs):
        """Run and plot a single flight"""
        print(f"\nBEGIN RUN FOR\n {flightargs}\n\n")
        try:
            fr = FlightRun(flightargs)

            flight_json = os.path.join(self.json_d, fr.arg_str + ".json")

            converged = fr.run_and_validate()

            # exit at this point if the flight did not converge,
            # writing the json with the inputs and empty outputs
            if not converged:
                aux.dump_json(fr.results(), flight_json)
                return {}

            # organize all the data if the flight is valid, and then plot it
            fr.process_data()
            aux.dump_json(fr.results(), flight_json)
            flight_plots_dir = aux.make_cat_dir(self.plots_d, fr.arg_str)
            plots.plot_flight(fr.outputs, flight_plots_dir)

            # also plot profiling data
            plots.perf_profile(fr.perf_profiling, flight_plots_dir)
            print(f"\nFINISHED RUN FOR\n {flightargs}\n\n")
            return fr.summary()

        except Exception as e:
            print(f"\n\nUNKNOWN EXCEPTION DURING FLIGHT{flightargs}\nORIGINAL ERROR MESSAGE:\n\n{e}\n\n")
            raise
    def run_single(self,a):
        """
        Execute a single flight
        """
        # convert to tuple
        config = (
                a["Range"],
                a["Payload"],
                a["Powerplant"],
                a["Cell"],
                a["Cell Specific Energy"],
                a["Cell Specific Power"],
                a["Base Phi"],
                a["Mission Name"],
            )
        self.run_and_plot(config)

    def run_parallel(self, arg_list, ooi):
        """
        Execute all the flight sims in parallel
        """
        print(LOGO)
        configs_to_run = self._unpack_arg_list(arg_list)
        num_threads = multiprocessing.cpu_count()

        with multiprocessing.Pool(processes=num_threads) as pool:
            results = pool.map(self.run_and_plot, configs_to_run)
        output_data = self._compile_flights(results)
        print("EVALUATING INPUT ARGUMENT LIST")
        # print(arg_list)
        self.correlate_flights(output_data, arg_list, ooi)

    def run_config(self, arg_list, ooi=None):
        """Determine if it should run in parallel or not"""
        j = 1
        for i in arg_list:
            j = max(len(i), j)
        if j > 1:
            if ooi is None:
                ooi=[]
            self.run_parallel(arg_list, ooi)
        else:
            self.run_single(arg_list)

    def _compile_flights(self, dd):
        """
        Collect and compile the data of the various
        flights files into a dictionary of lists
        """
        data = defaultdict(list)
        for item in dd:
            for key, value in item.items():
                data[key].append(value)
        return data

    def _determine_ioi(self, arg_list):
        """
        ioi - inputs of interest
        grabs the dictionary key of all the inputs that were passed
        as a range of values so that the plots can be made over them
        """
        ioi = []
        for k, v in arg_list.items():
            if len(v) > 1:
                ioi.append(k)
        return ioi

    def correlate_flights(self, data, arg_list, ooi):
        """
        Plot the data that is obtained across flights, such as relation
        between battery size and range or payload, etc by reading all the
        JSON files that were generated and plotting their data.
        It receives the list of outputs that are interesting to plot (ooi)
        because there are dozens of possible outputs, most useless
        it receives the list of inputs originally given to the code
        because otherwise the inputs of interest (ioi) for the outputs
        to be plotted against would need to be rebuilt from the jsons,
        which adds completely needless overhead. Its not very elegant,
        but it works fine
        """
        # dataset = self._compile_flights()
        ioi = self._determine_ioi(arg_list)

        n = len(ioi)
        if n == 0:
            return

        if n == 1:
            # plot the outputs against the singe ioi both as bar plots and as scatter plots
            ioi = ioi[0]
            plots.multiplot_1(data, ioi, ooi,self.extra_d)

        elif n == 2:
            # plot both as heatmaps and scatter plots
            ioi = (ioi[0], ioi[1])
            plots.multiplot_2(data, ioi, ooi,self.extra_d)

        else:
            # implement 3D viz plots one day?
            print("Too many inputs to plot over!")
