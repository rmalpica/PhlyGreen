logo="""
#############################################
# ____     __          ___                  #
#/\  _`\  /\ \        /\_ \                 #
#\ \ \L\ \ \ \ \___    \//\ \     __  __    #
# \ \ ,__/ \ \  _ `\    \ \ \   /\ \/\ \    #
#  \ \ \/   \ \ \ \ \    \_\ \_ \ \ \_\ \   #
#   \ \_\    \ \_\ \_\   /\____\ \/`____ \  #
# ___\/_/     \/_/\/_/   \/____/  `/___/> \ #
#/\  _`\                             /\___/ #
#\ \ \L\_\   _ __     __      __     \/__/  #
# \ \ \L_L  /\`'__\ /'__`\  /'__`\ /' _ `\  #
#  \ \ \/, \ \ \ \/ /\  __/ /\ __/ /\ \/\ \ #
#   \ \____/ \ \_\ \ \____\ \ \__\ \ \_\ \_\#
#    \/___/   \/_/  \/____/ \/____/ \/_/\/_/#
#                                           #
#############################################
"""
from datetime import datetime
import sys
sys.path.insert(0,'../')
import PhlyGreen as pg
import numpy as np
import matplotlib.pyplot as plt

import seaborn as sns
import pandas as pd
import matplotlib
matplotlib.use('agg')


argRange   = int(sys.argv[1])
argPayload = int(sys.argv[2])
argProfile = sys.argv[3]
argCell    = sys.argv[4]

print(logo)
current_date = datetime.now()
print(current_date.isoformat())
print("starting with configuration:")
print("Range = ",argRange,"km | ","Payload = ",argPayload,"kg | ",argProfile,"powerplant | ",argCell,"cell model")
print("-------------------------------------------------------------------------------------------")
print()
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

ConstraintsInput = {'DISA': 0.,
                    'Cruise': {'Speed': 0.34, 'Speed Type':'Mach', 'Beta': 0.95, 'Altitude': 3000.},
                    'AEO Climb': {'Speed': 130, 'Speed Type':'KCAS', 'Beta': 0.97, 'Altitude': 2000., 'ROC': 8},
                    'OEI Climb': {'Speed': 1.2*34.5, 'Speed Type': 'TAS', 'Beta': 1., 'Altitude': 0., 'Climb Gradient': 0.021},
                    'Take Off': {'Speed': 90, 'Speed Type': 'TAS', 'Beta': 1., 'Altitude': 100., 'kTO': 1.2, 'sTO': 950},
                    'Landing':{'Speed': 59., 'Speed Type': 'TAS', 'Altitude': 500.},
                    'Turn':{'Speed': 130, 'Speed Type': 'KCAS', 'Beta': 0.9, 'Altitude': 3000, 'Load Factor': 1.1},
                    'Ceiling':{'Speed': 0.5, 'Beta': 0.8, 'Altitude': 3500, 'HT': 0.5},
                    'Acceleration':{'Mach 1': 0.3, 'Mach 2':0.4, 'DT': 180, 'Altitude': 2800, 'Beta': 0.9}}

MissionInput = {'Range Mission': argRange/1.852,  #nautical miles but the input comes in km #TODO
                'Range Diversion': 145,  #nautical miles
                'Beta start': 0.97,
                'Minimum SOC': 0.2,
                'Payload Weight': argPayload-500 ,  #Kg #TODO
                'Crew Weight': 500}  #Kg

MissionStages = {
                 'Takeoff':
                    {'Supplied Power Ratio':{'phi': 0.1}},

                 'Climb1': {'type': 'ConstantRateClimb', 'input': 
                    {'CB': 0.16, 'Speed': 77, 'StartAltitude': 100, 'EndAltitude': 560}, 
                    'Supplied Power Ratio':{'phi_start': 0.1, 'phi_end':0.1 }},

                 'Climb2': {'type': 'ConstantRateClimb', 'input': 
                    {'CB': 0.08, 'Speed': 120, 'StartAltitude': 560, 'EndAltitude': 1690}, 
                    'Supplied Power Ratio':{'phi_start': 0.1, 'phi_end':0.1 }},

                 'Climb3': {'type': 'ConstantRateClimb', 'input': 
                    {'CB': 0.07, 'Speed': 125, 'StartAltitude': 1690, 'EndAltitude': 3000}, 
                    'Supplied Power Ratio':{'phi_start': 0.1, 'phi_end': 0.1 }},

                 'Cruise': {'type': 'ConstantMachCruise', 'input': 
                    { 'Mach': 0.4, 'Altitude': 3000}, 
                   'Supplied Power Ratio':{'phi_start': 0.1, 'phi_end':0.1 }},

                 'Descent1': {'type': 'ConstantRateDescent', 'input':
                    {'CB': -0.04, 'Speed': 90, 'StartAltitude': 3000, 'EndAltitude': 200}, 
                    'Supplied Power Ratio':{'phi_start': 0.1, 'phi_end': 0.1  }}}


DiversionStages = {
                   'Climb1': {'type': 'ConstantRateClimb', 'input': 
                        {'CB': 0.08, 'Speed': 110, 'StartAltitude': 200, 'EndAltitude': 1000}, 
                        'Supplied Power Ratio':{'phi_start': 0.10, 'phi_end':0.1  }},

                   'Cruise': {'type': 'ConstantMachCruise', 'input':
                        { 'Mach': 0.35, 'Altitude': 1000}, 
                        'Supplied Power Ratio':{'phi_start': 0.1, 'phi_end':0.1 }},

                   'Descent1': {'type': 'ConstantRateDescent', 'input':
                        {'CB': -0.04, 'Speed': 90, 'StartAltitude': 1000, 'EndAltitude': 200}, 
                        'Supplied Power Ratio':{'phi_start': 0.1, 'phi_end':0.1}}}

EnergyInput = {'Ef': 43.5*10**6,
                   'Contingency Fuel': 130,
                   'Eta Gas Turbine': 0.22,
                   'Eta Gearbox': 0.96,
                   'Eta Propulsive': 0.9,
                   'Eta Electric Motor 1': 0.96,    #for serial config
                   'Eta Electric Motor 2': 0.96,    #for serial config
                   'Eta Electric Motor': 0.98,      #for parallel config
                   'Eta PMAD': 0.99,
                   'Specific Power Powertrain': [3900,7700],
                   'Specific Power PMAD': [2200,2200,2200],
                   'PowertoWeight Battery': 35, 
                   'PowertoWeight Powertrain': [150,33],
                   'PowertoWeight PMAD': 0
                   }

CellModel = argCell # 'FELIX_FINGER' #TODO

AerodynamicsInput = {'AnalyticPolar': {'type': 'Quadratic', 'input': {'AR': 11, 'e_osw': 0.8}},
                    'Take Off Cl': 1.9,
                     'Landing Cl': 1.9,
                     'Minimum Cl': 0.20,
                     'Cd0': 0.017}

myaircraft.ConstraintsInput = ConstraintsInput
myaircraft.AerodynamicsInput = AerodynamicsInput
myaircraft.MissionInput = MissionInput
myaircraft.MissionStages = MissionStages
myaircraft.DiversionStages = DiversionStages
myaircraft.EnergyInput = EnergyInput
myaircraft.CellModel = CellModel

myaircraft.Configuration = argProfile #'Traditional' #TODO
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

myaircraft.constraint.FindDesignPoint()
print('----------------------------------------')
print('Design W/S: ',myaircraft.DesignWTOoS)
print('Design P/W: ',myaircraft.DesignPW)
print('----------------------------------------')

myaircraft.weight.WeightEstimation()

myaircraft.WingSurface = myaircraft.weight.WTO / myaircraft.DesignWTOoS * 9.81

print()
if myaircraft.Configuration == 'Traditional':

    print('Fuel mass (trip + altn) [Kg]: ', myaircraft.weight.Wf)
    print('Block Fuel mass [Kg]:         ', myaircraft.weight.Wf + myaircraft.weight.final_reserve)
    print('Structure [Kg]:               ', myaircraft.weight.WStructure)
    print('Powertrain mass [Kg]:         ',myaircraft.weight.WPT)
    print('Empty Weight [Kg]:            ', myaircraft.weight.WPT + myaircraft.weight.WStructure + myaircraft.weight.WCrew)
    print('Zero Fuel Weight [Kg]:        ', myaircraft.weight.WPT + myaircraft.weight.WStructure + myaircraft.weight.WCrew + myaircraft.weight.WPayload)
    print('----------------------------------------')
    print('Takeoff Weight: ', myaircraft.weight.WTO)
    if myaircraft.WellToTankInput is not None:
        print('Source Energy: ', myaircraft.welltowake.SourceEnergy/1.e6,' MJ')
        print('Psi: ', myaircraft.welltowake.Psi)
    print('Wing Surface: ', myaircraft.WingSurface, ' m^2')
    print('TakeOff engine shaft peak power [kW]:      ', myaircraft.mission.TO_PP/1000.)
    print('Climb/cruise engine shaft peak power [kW]: ', myaircraft.mission.Max_PEng/1000.)

    print('-------------Sizing Phase--------------')
    print('Sizing phase for thermal powertrain ', 'Climb/Cruise peak power' if myaircraft.mission.Max_PEng > myaircraft.mission.TO_PP else 'Takeoff peak power'  )

else:
    print('Fuel mass (trip + altn) [Kg]: ', myaircraft.weight.Wf)
    print('Block Fuel mass [Kg]:         ', myaircraft.weight.Wf + myaircraft.weight.final_reserve)
    print('Battery mass [Kg]:            ', myaircraft.weight.WBat)
    print('Structure [Kg]:               ', myaircraft.weight.WStructure)
    print('Powertrain mass [Kg]:         ',myaircraft.weight.WPT)
    print('Empty Weight [Kg]:            ', myaircraft.weight.WPT + myaircraft.weight.WStructure + myaircraft.weight.WCrew + myaircraft.weight.WBat)
    print('Zero Fuel Weight [Kg]:        ', myaircraft.weight.WPT + myaircraft.weight.WStructure + myaircraft.weight.WCrew + myaircraft.weight.WBat + myaircraft.weight.WPayload)
    print('----------------------------------------')
    print('Takeoff Weight: ', myaircraft.weight.WTO)
    if myaircraft.WellToTankInput is not None:
        print('Source Energy: ', myaircraft.welltowake.SourceEnergy/1.e6,' MJ')
        print('Psi: ', myaircraft.welltowake.Psi)
    print('Wing Surface: ', myaircraft.WingSurface, ' m^2')
    print('TakeOff engine shaft peak power [kW]:      ', myaircraft.mission.TO_PP/1000.)
    print('Climb/cruise engine shaft peak power [kW]: ', myaircraft.mission.Max_PEng/1000.)
    print('TakeOff battery peak power [kW]:           ', myaircraft.mission.TO_PBat/1000.)
    print('Climb/cruise battery peak power [kW]:      ', myaircraft.mission.Max_PBat/1000.)
    print()
    print('-------------Battery Specs-------------')
    print('Battery Pack Energy [kWh]:           ', myaircraft.battery.pack_energy/3600000)
    print('Battery Pack Max Power [kW]:         ', myaircraft.battery.pack_power_max/1000)
    print('Battery Pack Specific Energy [Wh/kg]:',(myaircraft.battery.pack_energy/3600)/myaircraft.weight.WBat)
    print('Battery Pack Specific Power [kW/kg]: ',(myaircraft.battery.pack_power_max/1000)/myaircraft.weight.WBat)
    print()
    print('-------------Sizing Phase--------------')

    #print('Sizing phase for battery: ', 'Cruise energy' if myaircraft.battery.energy_or_power == 'energy' else 'Cruise peak power' if myaircraft.weight.TOPwr_or_CruisePwr == 'cruise' else 'Takeoff peak power'  ) #uncomment when i add a mechanism for seeing which constraint drove what thing in the battery sizing
    print('Sizing phase for thermal powertrain: ', 'Climb/Cruise peak power' if myaircraft.mission.Max_PEng > myaircraft.mission.TO_PP else 'Takeoff peak power'  )
    # print('Sizing phase for electric powertrain ', 'Climb/Cruise peak power' if myaircraft.mission.Max_PBat > myaircraft.mission.TO_PBat else 'Takeoff peak power'  )
print()
print("-------------------------------")
print("Quick reference for comparison:")
print()

print('Mission Range  [km]: ', myaircraft.mission.profile.MissionRange/1000)
print('Total Payload  [kg]: ', myaircraft.weight.WPayload + myaircraft.weight.WCrew)
print('Takeoff Weight [kg]: ', myaircraft.weight.WTO)
if not (myaircraft.Configuration == 'Traditional'):
    print()
    print('-------------Battery Pack Specs-------------')
    print('Specific Energy [Wh/kg]: ',(myaircraft.battery.pack_energy/3600)/myaircraft.weight.WBat)
    print('Specific Power  [kW/kg]: ',(myaircraft.battery.pack_power_max/1000)/myaircraft.weight.WBat)


# begin thermal stuff

fTime = []
fHeat = []
# clean up repeated and unsorted data points
tosort=myaircraft.mission.CurrentvsTime
sortedarr=tosort[np.argsort(tosort[:, 0])]

for i in range(len(sortedarr)): 
    if sortedarr[i,0] != sortedarr[i-1,0]:
        fTime += [sortedarr[i,0]]
        fHeat += [myaircraft.battery.Curr2Heat(sortedarr[i,1])]


#print(fHeat)
#print(fTime)
#fTime = myaircraft.mission.CurrentvsTime[:,0]
#fHeat = myaircraft.battery.Curr2Heat(myaircraft.mission.CurrentvsTime[:,1])

#print(myaircraft.mission.CurrentvsTime)

#C = 8.85 * 1130      # mass times specific heat capacity = heat capacity
#R = 1/(0.208 * 1000) # 1/(wall area times convection coef) = thermal resistance of the walls
#Ti = 300 # ambient temperature in kelvin
#T = Ti   # initial temperature starts at ambient
#dTdt = 0 #T derivative being initialized
#P_t = []
#T_t = []
#dTdt_t = []

#for i in range(len(fHeat)-1):
#    dt=fTime[i+1]-fTime[i]
#    P=fHeat[i]
##    dTdt = P/C + (Ti-T)/(R*C) 
 #   T = T+dTdt*dt
 #   T_t += [T]
#    dTdt_t += [dTdt]

data = pd.DataFrame({
    'Time': fTime[:-1],
    'Heat': fHeat[:-1],
    #'Temp': T_t,
    #'dTdt': dTdt_t
})


#sns.scatterplot(data=data, x='Time', y='Temp', label='Temp', color='red')
#plt.savefig('Temp.png')
#plt.clf()

#sns.scatterplot(data=data, x='Time', y='Heat', label='Heat', color='red')
#plt.savefig('Heat.png')
#plt.clf()

#sns.scatterplot(data=data, x='Time', y='dTdt', label='dTdt', color='red')
#plt.savefig('dTdt.png')
#plt.clf()

def interpolate(x,y,samples): # here it returns the current power given a certain time, for now we assume its linear for everything
    t = np.linspace(x[0],x[-1],samples)
    f_t = [] #np.empty(samples)
    debug = [] #np.empty(samples)
    for i in range(samples):
        for j in range(len(x)):
            if x[j] == t[i]:
                f_t += [y[j]]
                #debug = np.vstack([debug,[x[j],t[i],y[j],f_t[i]]])
                debug.append([x[j],t[i],y[j],f_t[i]])
                break
            elif x[j] > t[i]:
                f_t += [y[j-1] + (y[j] - y[j-1]) * (t[i] - x[j-1]) / (x[j]-x[j-1])]
                #debug = np.vstack([debug,[x[j],t[i],y[j],f_t[i]]])
                debug.append([x[j],t[i],y[j],f_t[i]])
                break
    debug=np.array(debug)
    return t, f_t, debug


samples=500000
#lin_time = np.linspace(fTime[0], fTime[-1], samples)
#lin_heat = np.interp(lin_time, fTime, fHeat)
lin_time,lin_heat, debug = interpolate(fTime,fHeat,samples)


C = 8.85 * 1130    # mass times specific heat capacity = heat capacity
R = 1/(0.208 * 100) # 1/(wall area times convection coef) = thermal resistance of the walls
Ti = 300 # ambient temperature in kelvin
T = Ti   # initial temperature starts at ambient
dTdt = 0 #T derivative being initialized
P_t = []
T_t = []
dTdt_t = []

for i in range(samples-1):
    dt=lin_time[i+1]-lin_time[i]
    P=lin_heat[i]
    dTdt = P/C + (Ti-T)/(R*C) 
    T = T+dTdt*dt
    T_t += [T]
    dTdt_t += [dTdt]

datalin = pd.DataFrame({
    'Time': lin_time[:-1],
    'Heat': lin_heat[:-1],
    'Temp': T_t,
    'dTdt': dTdt_t
})


sns.lineplot(data=datalin, x='Time', y='Temp', label='lin_Temp', color='green')
plt.savefig(sys.argv[1]+'lin_Temp.png')
plt.clf()

sns.lineplot(data=datalin, x='Time', y='Heat', label='interpolated', color='green')
sns.scatterplot(data=data, x='Time', y='Heat', label='original', color='red')
plt.savefig(sys.argv[1]+'interpheat.png')
plt.clf()

sns.lineplot(data=datalin, x='Time', y='dTdt', label='lin_dTdt', color='green')
plt.savefig(sys.argv[1]+'lin_dTdt.png')
plt.clf()

print('----------------------debug prints----------------------')
print()
print('time_og , time_interp , power_og , power_interp')
print(np.matrix(debug))
print()
print()
print('time_og , power_og')
print(np.matrix(np.column_stack((fTime, fHeat))))
