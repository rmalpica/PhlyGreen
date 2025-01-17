"""main script for running sweeps in an ordered manner"""

import os
import multiprocessing
from pathlib import Path
from collections import defaultdict
from itertools import product
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

    def _unpack_arg_list(self, a):
        """
        Unpack the arguments list using itertools.product()
        to avoid having 7 nested loops.
        The parameters are ordered like this because this is
        the order they are input into the mission inputs of
        the aircraft class.
        To avoid creating dozens of repeated Traditional
        configurations (iterations of Cell and Phi) this is
        done to unpack the arguments first instead of simply
        using starmap() on the processing stage.
        """
        configs = []
        if "Traditional" in a["Powerplant"]:
            configs += product(
                a["Range"],
                a["Payload"],
                ["Traditional"],
                [a["Cell"][0]],  # use the first cell and phi to prevent the aircraft
                [a["Base Phi"][0]],  # setup code from breaking due to not having these values
                a["Mission Name"],
            )

        if "Hybrid" in a["Powerplant"]:
            configs += product(
                a["Range"],
                a["Payload"],
                ["Hybrid"],
                a["Cell"],
                a["Base Phi"],
                a["Mission Name"],
            )

        return configs

    def run_and_plot(self, flightargs):
        """Run and plot a single flight"""
        print("BEGIN RUN")
        fr = FlightRun(flightargs)

        flight_json = os.path.join(self.json_d, fr.arg_str + ".json")

        converged = fr.run_and_validate()

        # exit at this point if the flight did not converge,
        # writing the json with the inputs and empty outputs
        if not converged:
            aux.dump_json(fr.results(), flight_json)
            return None

        # organize all the data if the flight is valid, and then plot it
        fr.process_data()
        aux.dump_json(fr.results(), flight_json)
        flight_plots_dir = aux.make_cat_dir(self.plots_d, fr.arg_str)
        plots.plot_flight(fr.outputs, flight_plots_dir)

        # also plot profiling data
        plots.perf_profile(fr.perf_profiling, flight_plots_dir)
        return fr.summary()

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

        self.correlate_flights(output_data, arg_list, ooi)

    def _compile_flights(self,dd):
        """
        Collect and compile the data of the various
        flights files into a dictionary of lists
        """
        data = defaultdict(list)
        # for d in dd:
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

        # TODO make this detect which input parameters are being swept over and use those as the X Y axis
        # for example, if only the range and payload change in the input args list, make the scatter plots plus the heatmaps
        # but if it detects that only one value is changing, like the cell, or the phi, or the architecture, make bar plots instead
        # if three or more are swept return an error
        # the previous code could only do stuff like a chart of weight vs range for different payloads, and it would break the different
        # missions and profiles and architectures into folders. No more. it goes all in the same folder, you specify up to two things to sweep
        # theres no logic to handling more than that in this part of the code anyway.
        # for key, _ in dataset.items():
        #     Z = dataset
        # plots.multiPlot


# TODO:
#     IMPLEMENT THE CROSS REF GRAPHS AND HEATMAPS
