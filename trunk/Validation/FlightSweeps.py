logo="""
-------------------------------------------------
    ____  __    __      ______
   / __ \/ /_  / /_  __/ ____/_______  ___  ____
  / /_/ / __ \/ / / / / / __/ ___/ _ \/ _ \/ __ \ 
 / ____/ / / / / /_/ / /_/ / /  /  __/  __/ / / /
/_/   /_/ /_/_/\__, /\____/_/   \___/\___/_/ /_/
              /____/
-------------------------------------------------
"""
from datetime import datetime
import time
import sys
sys.path.insert(0,'../')
import PhlyGreen as pg
import numpy as np
import json
import flight_profiles
import write_log

#get all the inputs from the command line or shell script
# argRange   - range in nautical miles
# argPayload - payload in kg
# argArch    - 'Hybrid' vs 'Traditional' architecture
# argCell    - name of the cell model to use, see Cell_Models.py
# argPhi     - base hybridization ratio to use, actual effect depends on flight profile chosen
# argMission - mission profile to follow, look in flight_profiles.py

def CalculateFlight(argArch, argMission, argRange, argPayload, argCell, argPhi):
    argRange   = float(argRange)
    argPayload = float(argPayload)
    argPhi     = float(argPhi)
    #set up some strings and prints to terminal to help organize what is going on when the code is ran
    args = (str(argRange) + '-' + str(argPayload) + '-' + str(argArch) + '-' + str(argCell) + '-' + str(argPhi) + '-' + str(argMission))
    print(logo)
    print()
    current_date = datetime.now()
    print(current_date.isoformat())
    print("starting with configuration:")
    print( argArch," powerplant |  Mission Profile: ",argMission)
    if argArch == 'Hybrid':
        print( argCell,"cell model | phi = ",argPhi)
    print("Range = ",argRange,"km | ","Payload = ",argPayload,"kg")
    print("--------------------------------------------------")
    print()

    #setup just to initialize everything
    powertrain = pg.Systems.Powertrain.Powertrain(None)
    structures = pg.Systems.Structures.Structures(None)
    aerodynamics = pg.Systems.Aerodynamics.Aerodynamics(None)
    performance = pg.Performance.Performance(None)
    mission = pg.Mission.Mission(None)
    weight = pg.Weight.Weight(None)
    constraint = pg.Constraint.Constraint(None)
    welltowake = pg.WellToWake.WellToWake(None)
    battery = pg.Systems.Battery.Battery(None)

    myaircraft = pg.Aircraft(powertrain, structures, aerodynamics, performance, mission, weight, constraint, welltowake, battery)

    powertrain.aircraft = myaircraft
    structures.aircraft = myaircraft
    aerodynamics.aircraft = myaircraft
    mission.aircraft = myaircraft
    performance.aircraft = myaircraft
    weight.aircraft = myaircraft
    constraint.aircraft = myaircraft
    welltowake.aircraft = myaircraft
    battery.aircraft = myaircraft

    print('Configuring mission')
    # here it actually defines all the mission inputs from the file containing all the profiles
    # done this way to allow for quick sweeps of common settings like payload and Phi while allowing
    # different mission flight profiles without having to copy paste them 100 times
    flight_profile=flight_profiles.MissionParameters(argRange,argPayload,argArch,argCell,argPhi,argMission)

    myaircraft.ConstraintsInput  = flight_profile['ConstraintsInput']
    myaircraft.AerodynamicsInput = flight_profile['AerodynamicsInput']
    myaircraft.MissionInput      = flight_profile['MissionInput']
    myaircraft.MissionStages     = flight_profile['MissionStages']
    myaircraft.DiversionStages   = flight_profile['DiversionStages']
    myaircraft.EnergyInput       = flight_profile['EnergyInput']

    myaircraft.CellModel = argCell
    myaircraft.Configuration = argArch
    myaircraft.HybridType = 'Parallel'
    myaircraft.AircraftType = 'ATR'

    # Initialize Constraint Analysis
    myaircraft.constraint.SetInput()
    # Initialize Mission profile and Analysis
    myaircraft.mission.InitializeProfile()
    myaircraft.mission.SetInput()
    # Initialize Aerodynamics subsystem
    myaircraft.aerodynamics.SetInput()
    # Initialize Powertrain
    myaircraft.powertrain.SetInput()
    # Initialize Weight Estimator
    myaircraft.weight.SetInput()
    #Initialize Battery Configurator
    myaircraft.battery.SetInput()

    print('Starting weight estimation')
    #run the actual maths that configures the aircraft
    myaircraft.constraint.FindDesignPoint()
    myaircraft.weight.WeightEstimation()

    #do the battery heating calculations if the aircraft is hybrid
    if argArch == 'Hybrid' :
        print('Starting heat calculations')
        battery_heating_data = myaircraft.battery.BatteryHeating(myaircraft.mission.CurrentvsTime)
        # save heating data to dictionary
        heatdata = {
                    'Time': battery_heating_data[0].tolist(), # these two are np arrays
                    'Heat': battery_heating_data[1].tolist(), # they are converted to be put in the json
                    'Temperature': battery_heating_data[2],
                    'dTdt': battery_heating_data[3]}
    else:
        heatdata ={}

    print('Gathering outputs')

    myaircraft.WingSurface = myaircraft.weight.WTO / myaircraft.DesignWTOoS * 9.81

    if argArch == 'Hybrid' : 
        times = np.array([])
        Ef    = np.array([])
        Ebat  = np.array([])
        beta  = np.array([])
        soc   = np.array([])
        for array in mission.integral_solution:
            times = np.concatenate([times, array.t])
            Ef    = np.concatenate([Ef   , array.y[0]])
            Ebat  = np.concatenate([Ebat , array.y[1]])
            beta  = np.concatenate([beta , array.y[2]])
            soc   = np.concatenate([soc  , array.y[3]])

        energydata={
                    'time':times.tolist(),
                    'fuel energy':Ef.tolist(),
                    'battery energy':Ebat.tolist(),
                    'beta':beta.tolist(),
                    'soc':soc.tolist()}

        phi = [mission.profile.SuppliedPowerRatio(t) for t in times]
        # add one here for battery power over time
        # add another for efficiency over time maybe also

        power_propulsive=[(myaircraft.weight.WTO/1000) * myaircraft.performance.PoWTO(myaircraft.DesignWTOoS,beta[t],
                                myaircraft.mission.profile.PowerExcess(times[t]),
                                1,
                                myaircraft.mission.profile.Altitude(times[t]),
                                myaircraft.mission.DISA,
                                myaircraft.mission.profile.Velocity(times[t]),
                                'TAS') for t in range(len(times))]

        results={
                'battery heating':heatdata,
                'energies':energydata,
                'power':power_propulsive,
                'altitude':mission.profile.Altitude(times).tolist(),
                'phi':phi}
    else: #remove references to the battery in traditional powerplant because the variables dont exist in the code
        times = np.array([])
        Ef    = np.array([])
        beta  = np.array([])
        for array in mission.integral_solution:
            times = np.concatenate([times, array.t])
            Ef    = np.concatenate([Ef   , array.y[0]])
            beta  = np.concatenate([beta , array.y[1]])

        energydata={
                    'time':times.tolist(),
                    'fuel energy':Ef.tolist(),
                    'beta':beta.tolist()}

        power_propulsive=[(myaircraft.weight.WTO/1000) * myaircraft.performance.PoWTO(myaircraft.DesignWTOoS,beta[t],
                                myaircraft.mission.profile.PowerExcess(times[t]),
                                1,
                                myaircraft.mission.profile.Altitude(times[t]),
                                myaircraft.mission.DISA,
                                myaircraft.mission.profile.Velocity(times[t]),
                                'TAS') for t in range(len(times))]
        results={
                'energies':energydata,
                'power':power_propulsive,
                'altitude':mission.profile.Altitude(times).tolist()}

    print('Writting output files')

    textfn = (args+ "_log.txt")
    write_log.printLog(myaircraft,textfn) #calls function to print the log txt file with the relevant  data

    #now the json
    inputsdict = {'inputs':{
                            'Powerplant':argArch,
                            'Range':argRange,
                            'Payload':argPayload,
                            'Cell':argCell,
                            'base Phi':argPhi,
                            'Mission Profile':flight_profile}}
    outputsdict = {'outputs':results}
    dicts=[inputsdict,outputsdict]

    jsonfn=(args+".json") #json file name
    with open(jsonfn, "w") as json_file:
        json.dump(dicts, json_file, indent=4)  # indent for readable formatting


# function for printing "fail" in the outputs if no solution is found
def DidNotConverge(argArch, argMission, argRange, argPayload, argCell, argPhi):
    print("----------------")
    print("DID NOT CONVERGE")
    print("----------------")
    args = (str(argRange) + '-' + str(argPayload) + '-' + str(argArch) + '-' + str(argCell) + '-' + str(argPhi) + '-' + str(argMission))
    
    textfn = (args+ "_log.txt") #txt file name
    write_log.failLog(textfn)   #calls function to print fail to the log

    jsonfn=(args+".json") #json file name
    with open(jsonfn, "w") as json_file:
        json.dump(['fail'], json_file, indent=4)  # indent for readable formatting

#more compact way of doing the timing and the trying of the calculation
def tryFlight(Arch,Mission,Range,Payload,Cell,Phi):
    timestart = time.time() #for execution timing purposes
    try:
        CalculateFlight(Arch,Mission,Range,Payload,Cell,Phi)
    except:
        DidNotConverge(Arch,Mission,Range,Payload,Cell,Phi)
    print("Done. Took %5.2f seconds" % (time.time()-timestart))

# main loop that sweeps the parameters given
def main(ArchList,MissionList,RangesList,PayloadsList,CellsList,PhisList):

    # to present the user with an idea of how long this is going to take
    iterations=len(MissionList)*len(RangesList)*len(PayloadsList)
    if 'Hybrid' in ArchList:
        iterations += len(MissionList)*len(RangesList)*len(PayloadsList)*len(CellsList)*len(PhisList) 
    i=0
    #start nested loops that execute the parameter sweep
    for Arch in ArchList:
        for Mission in MissionList:
            for Range in RangesList:
                for Payload in PayloadsList:
                    if Arch == 'Hybrid': #only sweep the battery parameters if the battery is actually used
                        for Cell in CellsList:
                            for Phi in PhisList:
                                tryFlight(Arch,Mission,Range,Payload,Cell,Phi)
                                i+=1
                                print("Iteration ",i," of ",iterations)
                    else:
                        Cell='FELIX_FINGER' # TODO update the code so that it runs with None as inputs for
                        Phi=0.1             # cell and phi if using traditional architecture
                        CalculateFlight(Arch,Mission,Range,Payload,Cell,Phi)
                        i+=1
                        print("Iteration ",i," of ",iterations)

#full sized lists for actually running this 
#ArchList     ={'Hybrid','Traditional'}
#MissionList  ={'FelixFinger'} #'ATR_Flight' - reconfigure and add later
#CellsList    ={'SAMSUNG_LIR18650','FELIX_FINGER'}
#PhisList     ={ 0.1, 0.2, 0.3, 0.5}
#RangesList   ={396, 1280 , 2361}
#PayloadsList ={550, 1330, 1960}

# smaller lists just for testing
ArchList     ={'Hybrid','Traditional'}
MissionList  ={'FelixFinger'} #'ATR_Flight' - reconfigure and add later
CellsList    ={'SAMSUNG_LIR18650','FELIX_FINGER'}
PhisList     ={ 0.1, 0.5}
RangesList   ={396, 2361}
PayloadsList ={550, 1960}

# actually run the function if the script is called directly
# otherwise a separate script can be made that only contains the lists and then calls the main function
# which could be easier for a user to define inputs that way

main(ArchList,MissionList,RangesList,PayloadsList,CellsList,PhisList)

# a script could also be made to independently call tryFlight() to do a parametric sweep in any other way