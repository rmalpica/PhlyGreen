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

def justPlot(aL,runName,varsOfInterest={}):
     # First configure the output directories
    FlightSweeps.Configure(runName)
    dirJSONs = FlightSweeps.json_directory
    dirPlots = os.path.join(FlightSweeps.dirOutput,"Plots")
    os.makedirs(dirPlots,exist_ok=True)

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

aL={'ArchList'     :{'Hybrid','Traditional'},
    'MissionList'  :{'Mission-FelixFinger',"HybridCruiseOnly","HybridTOClimbOnly","HybridCruiseHighAltitude","HybridTOClimbHighAltitude"},
    'CellsList'    :{'FELIX_FINGER'},
    'RangesList'   :{750,1000,1250,1500,1750,1850,2000},
    'PayloadsList' :{600,900,1200},
    'PhisList'     :{0.3}}

varsOfInterest={'In':['Range','Payload'], 
                'To Plot':[ 'Fuel Mass',
                            'Block Fuel Mass',
                            'Structure Mass',
                            'Powertrain Mass',
                            'Empty Weight',
                            'Zero Fuel Weight',
                            'Takeoff Weight',
                            'Wing Surface',
                            'TakeOff Engine Shaft PP',
                            'Climb Cruise Engine Shaft PP',
                            'Battery Mass',
                            'Empty Weight',
                            'Zero Fuel Weight',
                            'Takeoff Weight',
                            'TakeOff Battery PP',
                            'Climb Cruise Battery PP',
                            'Battery Pack Energy',
                            'Battery Pack Max Power',
                            'Battery Pack Specific Energy',
                            'Battery Pack Specific Power',
                            'Battery P number',
                            'Battery S number',
                            'Battery Pack Charge',
                            'Battery Pack Max Current',
                            'Battery Pack Resistance'
                          ]}

#runAndPlot(aL,'Range-v-PayloadXTREME',varsOfInterest=varsOfInterest)
justPlot(aL,'Range-v-PayloadXTREME',varsOfInterest=varsOfInterest)

aL={'ArchList'     :{'Hybrid','Traditional'},
    'MissionList'  :{'Mission-FelixFinger',"HybridCruiseOnly","HybridTOClimbOnly","HybridCruiseHighAltitude","HybridTOClimbHighAltitude"},
    'CellsList'    :{'FELIX_FINGER'},
    'RangesList'   :{1250},
    'PayloadsList' :{600,700,800,900,1000,1100,1200},
    'PhisList'     :{0.05,0.1,0.2,0.3,0.4,0.5,1}}

varsOfInterest={'In':['Range','Base Phi'], 
                'To Plot':[ 'Fuel Mass',
                            'Block Fuel Mass',
                            'Structure Mass',
                            'Powertrain Mass',
                            'Empty Weight',
                            'Zero Fuel Weight',
                            'Takeoff Weight',
                            'Wing Surface',
                            'TakeOff Engine Shaft PP',
                            'Climb Cruise Engine Shaft PP',
                            'Battery Mass',
                            'Empty Weight',
                            'Zero Fuel Weight',
                            'Takeoff Weight',
                            'TakeOff Battery PP',
                            'Climb Cruise Battery PP',
                            'Battery Pack Energy',
                            'Battery Pack Max Power',
                            'Battery Pack Specific Energy',
                            'Battery Pack Specific Power',
                            'Battery P number',
                            'Battery S number',
                            'Battery Pack Charge',
                            'Battery Pack Max Current',
                            'Battery Pack Resistance'
                          ]}
                          
#runAndPlot(aL,'Phi-v-PayloadXTREME',varsOfInterest=varsOfInterest)
justPlot(aL,'Phi-v-PayloadXTREME',varsOfInterest=varsOfInterest)



