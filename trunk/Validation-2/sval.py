# main script for running sweeps in an ordered manner
import os
from run_flight import FlightRun
import extras as ex
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
DIRECTORY_OUT = None
DIRECTORY_JSON = None
DIRECTORY_PLOTS = None
DIRECTORY_EXTRA = None


def configure_directories(batch_name):
    """
    Configures the globals so that the
    directory names are accessible everywhere
    """
    global DIRECTORY_OUT
    global DIRECTORY_JSON
    global DIRECTORY_PLOTS
    global DIRECTORY_EXTRA
    DIRECTORY_OUT = ex.make_cat_dir("Outputs", batch_name)
    DIRECTORY_JSON = ex.make_cat_dir(DIRECTORY_OUT, "JSON")
    DIRECTORY_PLOTS = ex.make_cat_dir(DIRECTORY_OUT, "PLOTS")
    DIRECTORY_EXTRA = ex.make_cat_dir(DIRECTORY_OUT, "EXTRA")


def run_and_plot(flightargs):
    """Run and plot a single flight"""
    fr = FlightRun(flightargs)

    flight_json = os.path.join(DIRECTORY_JSON, fr.arg_str + ".json")

    converged = fr.run_and_validate()

    # exit at this point if the flight did not converge,
    # writing the json with the inputs and empty outputs
    if not converged:
        ex.dump_json(fr.results(), flight_json)
        return

    # organize all the data if the flight is valid, and then plot it
    fr.process_data()
    ex.dump_json(fr.results(), flight_json)
    flight_plots_dir = ex.make_cat_dir(DIRECTORY_PLOTS, fr.arg_str)
    plots.plot_flight(fr.outputs, flight_plots_dir)


def run_all(arg_list, batch_name, vars_of_interest=None):
    """coordinate the whole process of running the multiple flights"""
    print(LOGO)

TODO:
    MAKE THIS SCRIPT ABLE TO COMPUTE LOOSE ARGUMENT INTO PLOTS
    IMPLEMENT MULTI PROCESSING OF THE FLIGHTS FROM LISTS OF ARGUMENTS
    IMPLEMENT THE CROSS REF GRAPHS AND HEATMAPS