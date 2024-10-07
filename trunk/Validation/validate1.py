#main script for running sweeps in an ordered manner
import FlightSweeps
import PlotJSONs
import os

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

# define the list of parameters to sweep over
# its best to only sweep one of the numerical values at a time to avoid having hundreds
# of pointless mission combinations at once that are unmanageable

aL={'ArchList'     :{'Hybrid','Traditional'},
    'MissionList'  :{'FelixFinger'},
    'CellsList'    :[{'Energy':1500,'Power':6000}], # the old code doesnt support cells, needs battery energy density in watts hour per kg and power in watts per kg instead
    'RangesList'   :{600,2100},
    'PayloadsList' :{1200},
    'PhisList'     :{0.1,0.3,0.5}}

# define which values from the output json should be multiplotted,
# and which should be considered the TWO inputs that were swept
# the names here are passed to the plotter so they have to be the keys found on the output json
varsOfInterest={'In':['Range','Base Phi'], # lets see how range affects the design at different phi values
                'To Plot':['Structure Mass',
                           'Wing Surface',
                           'Battery Mass',
                           'Takeoff Weight',
                           'Climb Cruise Battery PP'
                          ]}
# specify the list and name to use, specify a non empty varsOfInterest in order to run the extra plots
runAndPlot(aL,'Sweep1',varsOfInterest=varsOfInterest)


#################
aL={'ArchList'     :{'Hybrid','Traditional'},
    'MissionList'  :{'FelixFinger'},
    'CellsList'    :[{'Energy':1500,'Power':6000}], # the old code doesnt support cells, needs battery energy density in watts hour per kg and power in watts per kg instead
    'RangesList'   :{1800},
    'PayloadsList' :{1200,2400},
    'PhisList'     :{0.1,0.3,0.5}}

varsOfInterest={'In':['Payload','Base Phi'], # now do different payloads instead
                'To Plot':['Structure Mass',
                           'Wing Surface',
                           'Battery Mass',
                           'Takeoff Weight',
                           'Climb Cruise Battery PP'
                          ]}

runAndPlot(aL,'Sweep2',varsOfInterest=varsOfInterest)


#################
aL={'ArchList'     :{'Hybrid','Traditional'},
    'MissionList'  :{'FelixFinger'},
    'CellsList'    :[{'Energy':1500,'Power':6000},{'Energy':250,'Power':1000}], # the old code doesnt support cells, needs battery energy density in watts hour per kg and power in watts per kg instead
    'RangesList'   :{600,2100},
    'PayloadsList' :{1200,2400},
    'PhisList'     :{0.1,0.5}}

runAndPlot(aL,'Sweep3')