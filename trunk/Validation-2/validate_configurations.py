# main script for running sweeps in an ordered manner
import os
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


def run_all(arg_list, batch_name, vars_of_interest=None):
    """
    Coordinate the whole process of running the multiple flights
    and plotting the data that is relevant across them
    """
    print(LOGO)

    def unpack_arg_list(a):
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

    def run_and_plot(flightargs):
        """Run and plot a single flight"""
        print("BEGIN RUN")
        fr = FlightRun(flightargs)

        flight_json = os.path.join(json_d, fr.arg_str + ".json")

        converged = fr.run_and_validate()

        # exit at this point if the flight did not converge,
        # writing the json with the inputs and empty outputs
        if not converged:
            aux.dump_json(fr.results(), flight_json)
            return

        # organize all the data if the flight is valid, and then plot it
        fr.process_data()
        aux.dump_json(fr.results(), flight_json)
        flight_plots_dir = aux.make_cat_dir(plots_d, fr.arg_str)
        plots.plot_flight(fr.outputs, flight_plots_dir)

    # Start by defining the directories
    print("SETTING DIRECTORIES")
    out_d = aux.make_cat_dir("Outputs", batch_name)  # OUTPUT DIRECTORY
    json_d = aux.make_cat_dir(out_d, "JSON")  # JSON DIRECTORY
    plots_d = aux.make_cat_dir(out_d, "FLIGHT_PLOTS")  # PLOTS DIRECTORY
    # extra_d = aux.make_cat_dir(out_d, "EXTRA")  # EXTRA DIRECTORY

    # unpack the arguments list that was received into a list of possible configurations
    print("UNPACKING")
    configs_to_run = unpack_arg_list(arg_list)
    print(f"UNPACKED:{configs_to_run}")
    # use map() to iteratively process every config with the run_and_plot() function
    for config in configs_to_run:
        run_and_plot(config)


# TODO:
#     MAKE THIS SCRIPT ABLE TO COMPUTE LOOSE ARGUMENT INTO PLOTS
#     IMPLEMENT MULTI PROCESSING OF THE FLIGHTS FROM LISTS OF ARGUMENTS
#     IMPLEMENT THE CROSS REF GRAPHS AND HEATMAPS
