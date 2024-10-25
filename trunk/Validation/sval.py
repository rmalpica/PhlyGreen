#main script for running sweeps in an ordered manner
import FlightSweeps
import PlotJSONs
import os
import numpy as np
import time

# This will configure run and plot everything relating to a single sweep
# receives:
# - argument list
# - name under which the data should be saved
# - optional variables to be plotted in extra plots
def runAndPlot(aL,runName,varsOfInterest={}):

    # First configure the output directories
    FlightSweeps.Configure(runName)
    dirJSONs = FlightSweeps.json_directory
    dirPlots = os.path.join(FlightSweeps.dirOutput,"Plots")
    os.makedirs(dirPlots,exist_ok=True)

    # FlightSweeps.main runs everything needed to sweep the parameters given
    # it runs a nested loop of all the different combinations given
    # in Traditional configuration, the cells and the phis are ignored
    FlightSweeps.main(aL['ArchList'],aL['MissionList'],aL['RangesList'],aL['PayloadsList'],aL['CellsList'],aL['PhisList'])

    # plot all the flight simulations that were written to json files
    print('----------------------\nPlotting')
    PlotJSONs.plotFlights(dirJSONs,dirPlots)

    # begin the extra multi variable plots if said variables are passed as input
    if varsOfInterest!={}:
        print('----------------------\nExtras')

        if len(varsOfInterest['In']) != 2:
            raise ValueError("Must provide two values to plot against")

        # create the directories used
        dirExtraPlots= os.path.join(FlightSweeps.dirOutput,'Extras','Plots')
        jsonExtras=os.path.join(FlightSweeps.dirOutput,'Extras','designspace.json')
        os.makedirs(dirExtraPlots,exist_ok=True)
        
        # scan the json files to create a list of the flights and their parameters
        PlotJSONs.scanDesigns(dirJSONs,jsonExtras)

        # use that list to plot what was requested
        PlotJSONs.extraPlots(jsonExtras,varsOfInterest,dirExtraPlots)

#=========================================================================================#
# write script here using the function above

aL={'ArchList'     :{'Hybrid'},
    'MissionList'  :{'Mission-FelixFinger'},
    'CellsList'    :{'FELIX_FINGER'},
    'RangesList'   :{1200},
    'PayloadsList' :{1200},
    'PhisList'     :{0.3}}

varsOfInterest={}

t = time.time()
runAndPlot(aL,'SingleValidation',varsOfInterest=varsOfInterest)
print(time.time()-t)