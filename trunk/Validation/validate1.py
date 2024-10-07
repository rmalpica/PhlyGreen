#main script for running sweeps in an ordered manner
import FlightSweeps
import PlotJSONs
import os
# This will configure run and plot everything relating to a single sweep
def runAndPlotAll(aL,runName,varsOfInterest):
    if len(varsOfInterest['In']) != 2:
        raise ValueError("Must provide two values to plot against")

    #first configure the output directories
    FlightSweeps.Configure(runName)
    dirJSONs = FlightSweeps.json_directory
    dirPlots = os.path.join(FlightSweeps.dirOutput,"Plots")
    dirExtraPlots= os.path.join(FlightSweeps.dirOutput,'Extras','Plots')
    jsonExtras=os.path.join(FlightSweeps.dirOutput,'Extras','designspace.json')
    os.makedirs(dirPlots,exist_ok=True)
    os.makedirs(dirExtraPlots,exist_ok=True)

    # FlightSweeps.main runs everything needed to sweep the parameters given
    # run multiple times with different lists to sweep different things
    # it runs a nested loop of all the different combinations given
    # its preferrable to sweep the Phi Range and Payload one at a time, to avoid wasting time
    # on hundreds of pointless combinations
    # in Traditional configuration, the cells and the phis are ignored
    FlightSweeps.main(aL['ArchList'],aL['MissionList'],aL['RangesList'],aL['PayloadsList'],aL['CellsList'],aL['PhisList'])

    # plot all the flight simulations that were written to json files
    print('----------------------\nPlotting')
    PlotJSONs.plotFlights(dirJSONs,dirPlots)

    # Then collect the JSON files and make a json of the design space
    # which contains the inputs and outputs of every design so that
    # plots of inputs vs outputs can be made for the sweeps to compare
    # different configurations
    print('----------------------\nExtras')
    PlotJSONs.scanDesigns(dirJSONs,jsonExtras)
    PlotJSONs.extraPlots(jsonExtras,varsOfInterest,dirExtraPlots)

# This will configure run and plot just the individual flights of a sweep.
# Useful for running multiple different missions to validate
#def runAndPlotMost(aL,runName):
#    FlightSweeps.Configure('Logs',runName)
#    FlightSweeps.main(aL['ArchList'],aL['MissionList'],aL['RangesList'],aL['PayloadsList'],aL['CellsList'],aL['PhisList'])
#    PlotJSONs.plotFlights(dirJSONs,dirPlots)
#    PlotJSONs.scanDesigns(FlightSweeps.json_directory,runName+"-designspace.json")


#=========================================================================================#
# write script here using the functions above

# define the list of parameters to sweep over
aL={'ArchList'     :{'Hybrid','Traditional'},
    'MissionList'  :{'FelixFinger'},
    'CellsList'    :{'FELIX_FINGER'},
    'RangesList'   :{600,1200,1800,2400},
    'PayloadsList' :{1500},
    'PhisList'     :{0.1,0.2,0.3,0.4,0.5}}
#runAndPlotMost(aL,'test')
# define which values from the output json should be multiplotted,
# and which should be considered the TWO inputs that were swept
# the names here are passed to the plotter so they have to be the keys found on the output json
varsOfInterest={'In':['Range','Base Phi'],
                'To Plot':['Structure Mass',
                           'Wing Surface',
                           'Battery Mass',
                           'Takeoff Weight',
                           'Climb Cruise Battery PP'
                          ]}

runAndPlotAll(aL,'TheTest',varsOfInterest)


