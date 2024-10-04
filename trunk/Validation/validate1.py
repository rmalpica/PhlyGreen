#main script for running the other scripts in an ordered manner
import FlightSweeps
import PlotJSONs

# This will configure run and plot everything relating to a single sweep
def runAndPlotAll(aL,runName):
    #first configure the name of the output directories
    FlightSweeps.Configure('Logs',runName)

    FlightSweeps.main(aL['ArchList'],aL['MissionList'],aL['RangesList'],aL['PayloadsList'],aL['CellsList'],aL['PhisList'])
    print('----------------------\nPlotting')
    PlotJSONs.plotFlights(FlightSweeps.json_directory,runName+"-Plots")
    # Then collect the JSON files and make a json of the design space
    # which contains the inputs and outputs of every design so that
    # plots of inputs vs outputs can be made for the sweeps to compare
    # different configurations
    print('----------------------\nExtras')
    PlotJSONs.scanDesigns(FlightSweeps.json_directory,runName+"-designspace.json")
    PlotJSONs.extraPlots(runName+"-designspace.json",runName+"-PlotsExtra")

# This will configure run and plot just the individual flights of a sweep.
# Useful for running multiple different missions to validate
def runAndPlotMost(aL,runName):
    FlightSweeps.Configure('Logs',runName)
    FlightSweeps.main(aL['ArchList'],aL['MissionList'],aL['RangesList'],aL['PayloadsList'],aL['CellsList'],aL['PhisList'])
    PlotJSONs.plotFlights(FlightSweeps.jsondir,runName+"-Plots")

# FlightSweeps.main runs everything needed to sweep the parameters given
# run multiple times with different lists to sweep different things
# it runs a nested loop of all the different combinations given
# its preferrable to sweep the Phi Range and Payload one at a time, to avoid wasting time
# on hundreds of pointless combinations
# in Traditional configuration, the cells and the phis are ignored

aL={'ArchList'     :{'Hybrid','Traditional'},
    'MissionList'  :{'FelixFinger'},
    'CellsList'    :{'FELIX_FINGER'},
    'RangesList'   :{396},
    'PayloadsList' :{550},
    'PhisList'     :{0.1}}
runAndPlotAll(aL,'Sweep1')


