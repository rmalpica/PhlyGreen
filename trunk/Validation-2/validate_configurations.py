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
        # extra_d = aux.make_cat_dir(self.out_d, "EXTRA")  # EXTRA DIRECTORY

    def _unpack_arg_list(self, a):
        """
        Unpack the arguments list using itertools.product()
        to avoid having 7 nested loops.
        The parameters are ordered like this because this is
        the order they are input into the mission inputs of
        the aircraft class
        """
        configs = []
        if "Traditional" in a["ArchList"]:
            configs += product(
                a["RangesList"],
                a["PayloadsList"],
                ["Traditional"],
                [a["CellsList"][0]],  # use the first cell and phi to prevent the aircraft
                [a["PhisList"][0]],  # setup code from breaking due to not having these values
                a["MissionList"],
            )

        if "Hybrid" in a["ArchList"]:
            configs += product(
                a["RangesList"],
                a["PayloadsList"],
                ["Hybrid"],
                a["CellsList"],
                a["PhisList"],
                a["MissionList"],
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
            return

        # organize all the data if the flight is valid, and then plot it
        fr.process_data()
        aux.dump_json(fr.results(), flight_json)
        flight_plots_dir = aux.make_cat_dir(self.plots_d, fr.arg_str)
        plots.plot_flight(fr.outputs, flight_plots_dir)

        # also plot profiling data
        plots.perf_profile(fr.perf_profiling, flight_plots_dir)

    def run_parallel(self, arg_list):
        """
        Execute all the flight sims in parallel
        """
        print(LOGO)
        configs_to_run = self._unpack_arg_list(arg_list)
        num_threads = multiprocessing.cpu_count()
        with multiprocessing.Pool(processes=num_threads) as pool:
            pool.map(self.run_and_plot, configs_to_run)

    def _compile_flights(self):
        """
        Collect and compile the data of the various
        flights from their json files into a dictionary
        """
        # This works by loading each json into a dictionary, removing whats useless,
        # flattening the dictionary and then loading it to a list of the flattened dictionaries
        # then this list is converted into a dictionary of lists, rather than a list of dictionaries
        # This is a very jank way to do this and should be a lot better
        data = defaultdict(list)
        for json_f in Path(self.json_d).glob("*.json"):  # returns every json file in directory
            d = aux.load_json(json_f)
            del d["Outputs"]
            del d["Inputs"]["Mission Profile"]
            # optional: save the performance profiling
            d["Parameters"]["Total Iterations"] = d["Meta Performance"]["Total Iterations"]
            del d["Meta Performance"]

            for item in d:
                for key , value in item.items():
                    data[key].append(value)

        return data

    def correlate_flights(self,voi):
        """
        Plot the data that is obtained across flights, such as
        relation between battery size and range or payload, etc
        """
        dataset = self._compile_flights()
        #TODO make this detect which input parameters are being swept over and use those as the X Y axis
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
