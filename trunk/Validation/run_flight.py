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
timestart = time.time() #for execution timing purposes

#get all the inputs from the command line or shell script
argRange   = float(sys.argv[1])
argPayload = float(sys.argv[2])
argProfile = sys.argv[3]
argCell    = sys.argv[4]
argPhi     = float(sys.argv[5])
argMission = sys.argv[6]

#set up some strings and prints to terminal to help organize what is going on when the code is ran
args = (sys.argv[1]+'-'+sys.argv[2]+'-'+sys.argv[3]+'-'+sys.argv[4]+'-'+sys.argv[5]+'-'+sys.argv[6])
print(logo)
current_date = datetime.now()
print(current_date.isoformat())
print("starting with configuration:")
print("Range = ",argRange,"km | ","Payload = ",argPayload,"kg | ",argProfile,"powerplant | ",argCell,"cell model | phi = ",argPhi, " | Mission Profile: ",argMission)
print("----------------------------------------------------------------------------------------------------------")
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
flight_profile=flight_profiles.MissionParameters(argRange,argPayload,argProfile,argCell,argPhi,argMission)

myaircraft.ConstraintsInput  = flight_profile['ConstraintsInput']
myaircraft.AerodynamicsInput = flight_profile['AerodynamicsInput']
myaircraft.MissionInput      = flight_profile['MissionInput']
myaircraft.MissionStages     = flight_profile['MissionStages']
myaircraft.DiversionStages   = flight_profile['DiversionStages']
myaircraft.EnergyInput       = flight_profile['EnergyInput']

myaircraft.CellModel = argCell
myaircraft.Configuration = argProfile
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
if argProfile == 'Hybrid' :
    print('Starting heat calculations')
    battery_heating_data = myaircraft.battery.BatteryHeating(myaircraft.mission.CurrentvsTime)
    # save heating data to dictionary
    heatdata = {
        'Time': battery_heating_data[0].tolist(), # these two are np arrays
        'Heat': battery_heating_data[1].tolist(), # they are converted to be put in the json
        'Temperature': battery_heating_data[2],
        'dTdt': battery_heating_data[3]
    }
else:
    heatdata ={}


print('Gathering outputs')
#calculations to print later
myaircraft.WingSurface = myaircraft.weight.WTO / myaircraft.DesignWTOoS * 9.81

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
    'soc':soc.tolist()
}

#power_to_weight=[myaircraft.performance.PoWTO(myaircraft.DesignWTOoS,beta[t],
#                              myaircraft.mission.profile.PowerExcess(times[t]),
#                              1,
#                              myaircraft.mission.profile.Altitude(times[t]),
#                              myaircraft.mission.DISA,
#                              myaircraft.mission.profile.Velocity(times[t])
#                              ,'TAS') for t in range(len(times))]

power_propulsive=[(myaircraft.weight.WTO/1000) * myaircraft.performance.PoWTO(myaircraft.DesignWTOoS,beta[t],
                              myaircraft.mission.profile.PowerExcess(times[t]),
                              1,
                              myaircraft.mission.profile.Altitude(times[t]),
                              myaircraft.mission.DISA,
                              myaircraft.mission.profile.Velocity(times[t]),
                              'TAS') for t in range(len(times))]
phi = [mission.profile.SuppliedPowerRatio(t) for t in times]

results={
    'battery heating':heatdata,
    'energies':energydata,
    'power':power_propulsive,
    'altitude':mission.profile.Altitude(times).tolist(),
    'phi':phi
}

print('Writting output files')

textfn = (args+ "_log.txt")
write_log.printLog(myaircraft,textfn) #calls function to print the log txt file with the interesting data

#now the json
inputsdict = {'inputs':flight_profile}
outputsdict = {'outputs':results}
dicts=[inputsdict,outputsdict]

jsonfn=(args+".json") #json file name
with open(jsonfn, "w") as json_file:
    json.dump(dicts, json_file, indent=4)  # indent for readable formatting

print("Done. Took ",time.time()-timestart," seconds")