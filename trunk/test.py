import PhlyGreen as pg
import sys
import numpy as np
import matplotlib.pyplot as plt
import time
import cProfile

#ISA = pg.Utilities.Atmosphere()

start_time = time.time()

# Creating subsystem instances
powertrain = pg.Systems.Powertrain.Powertrain(None)
structures = pg.Systems.Structures.Structures(None)
aerodynamics = pg.Systems.Aerodynamics.Aerodynamics(None)
performance = pg.Performance.Performance(None)
mission = pg.Mission.Mission(None)
weight = pg.Weight.Weight(None)
constraint = pg.Constraint.Constraint(None)


# # Creating mediator and associating with subsystems
myaircraft = pg.Aircraft(powertrain, structures, aerodynamics, performance, mission, weight, constraint)



# # Associating subsystems with the mediator
powertrain.aircraft = myaircraft
structures.aircraft = myaircraft
aerodynamics.aircraft = myaircraft
mission.aircraft = myaircraft
performance.aircraft = myaircraft
weight.aircraft = myaircraft
constraint.aircraft = myaircraft

aerodynamics.set_quadratic_polar(11,0.8)



# -----------------------------------------------------------------#
# Indeces of flight phases:
# 1: Cruise
# 2: Take off
# 3: Climb
# 4: Turn
# 5: Ceiling
# 6: Acceleration -----> Speed: Average speed during acceleration, calculated using M1 and M2
# 7: Landing 
# -----------------------------------------------------------------#

ConstraintsInput = {'speed': np.array([0.46, 70, 59*1.4, 0.3, 0.41, 0.35, 59.]) ,
                    'speedtype': ['Mach','TAS','TAS','Mach','Mach','Mach','TAS']   ,
                    'beta': np.array([0.9,1.,0.95, 0.9, 0.8, 0.9, None])   ,
                    'altitude': np.array([5450., 100., 2000., 5486.4, 7600., 5486.4, 500.]),
                    'load factor': np.array([1., None, 1., 1.1, 1., 1., None]),
                    'DISA': 0, 
                    'kTO': 1.2,
                    'sTO': 1000,
                    'Climb Gradient': 0.021,
                    'ht': 0.5,
                    'M1': 0.3,
                    'M2': 0.4,
                    'DTAcceleration': 180}

MissionInput = {'Range Mission': 459,
                'Range Diversion': 100,
                'Beta start': 0.95,
                'Payload Weight': (5255),
                'Crew Weight': (95*3)}

# MissionStages = {'ConstantRateClimb': {'CB': 0.021, 'Speed': 1.4*59, 'StartAltitude': 2000, 'EndAltitude': 5450},
#                  'ConstantRateDescent': {'CB': -0.021, 'Speed': 1.4*59, 'StartAltitude': 5450, 'EndAltitude': 2000},
#                  'ConstantMachCruise': {'Mach': 0.41, 'Altitude': 5450}}

MissionStages = {'Climb1': {'type': 'ConstantRateClimb', 'input': {'CB': 0.01, 'Speed': 1.4*59, 'StartAltitude': 2000, 'EndAltitude': 3000}},
                 'Climb2': {'type': 'ConstantRateClimb', 'input': {'CB': 0.005, 'Speed': 1.4*59, 'StartAltitude': 3000, 'EndAltitude': 3200}},
                 'Climb3': {'type': 'ConstantRateClimb', 'input': {'CB': 0.04, 'Speed': 1.4*59, 'StartAltitude': 3200, 'EndAltitude': 5450}},
                 'Descent1': {'type': 'ConstantRateDescent', 'input':{'CB': -0.026, 'Speed': 1.4*59, 'StartAltitude': 5450, 'EndAltitude': 4000}},
                 'Descent2': {'type': 'ConstantRateDescent', 'input':{'CB': -0.021, 'Speed': 1.4*59, 'StartAltitude': 4000, 'EndAltitude': 2000}},
                 'Cruise': {'type': 'ConstantMachCruise', 'input':{ 'Mach': 0.41, 'Altitude': 5450}}}

DiversionStages = {'Climb1': {'type': 'ConstantRateClimb', 'input': {'CB': 0.01, 'Speed': 1.4*59, 'StartAltitude': 2000, 'EndAltitude': 2500}},
                 'Climb2': {'type': 'ConstantRateClimb', 'input': {'CB': 0.04, 'Speed': 1.4*59, 'StartAltitude': 2500, 'EndAltitude': 3100}},
                 'Descent1': {'type': 'ConstantRateDescent', 'input':{'CB': -0.026, 'Speed': 1.4*59, 'StartAltitude': 3100, 'EndAltitude': 2300}},
                 'Descent2': {'type': 'ConstantRateDescent', 'input':{'CB': -0.021, 'Speed': 1.4*59, 'StartAltitude': 2300, 'EndAltitude': 2000}},
                 'Cruise': {'type': 'ConstantMachCruise', 'input':{ 'Mach': 0.3, 'Altitude': 3100}}}

TechnologyInput = {'Ef': 43.5*10**6,
                   'Ebat': 750 * 3600,
                   'pbat': 1000,
                   'Eta Gas Turbine': 0.3,
                   'Eta Gearbox': 0.96,
                   'Eta Propulsive': 0.9,
                   'Eta Electric Motor 1': 0.96,
                   'Eta Electric Motor 2': 0.96,
                   'Eta Electric Motor': 0.96,
                   'Eta PMAD': 0.99,
                   'Specific Power Powertrain': [3600,7700],
                   'Specific Power PMAD': [2200,2200,2200],
                   'PowertoWeight Battery': 35, 
                   'PowertoWeight Powertrain': [150,33],
                   'PowertoWeight PMAD': 0,
                   # 'Supplied Power Ratio': [[0.4, 0.2],[0.1, 0.05],[0.2, 0.1],[0.4, 0.2],[0.1, 0.05],[0.2, 0.1]]
                    'Supplied Power Ratio': [[0.2, 0.1],[0.05, 0.01],[0.1, 0.05],[0.2, 0.1],[0.05, 0.01],[0.1, 0.05]]
                   }


myaircraft.Configuration = 'Traditional'
myaircraft.HybridType = 'Parallel'
myaircraft.DesignAircraft(ConstraintsInput,MissionInput,TechnologyInput,MissionStages,DiversionStages)

             
# cProfile.run('weight.WeightEstimation()')
#----------------------------------------------- PLOT -------------------------------------------------#                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           

# fig, ax1 = plt.subplots()

# color = 'tab:red'
# ax1.set_xlabel('Time (min)')
# ax1.set_ylabel('E [J]')
# ax1.plot(mission.t/60, mission.Ef, color=color, label='E Fuel')
# ax1.plot(mission.t/60, mission.EBat, color='tab:green', label='E Battery')
# ax1.tick_params(axis='y')
# plt.legend()

# ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis

# color = 'tab:blue'
# ax2.set_ylabel('beta')  # we already handled the x-label with ax1
# ax2.plot(mission.t/60, mission.Beta, color=color, label='beta')
# ax2.tick_params(axis='y')

# fig.tight_layout()  # otherwise the right y-label is slightly clipped
# ax1.legend()
# ax2.legend()
# ax1.grid(visible=True)
# plt.show()
# plt.clf()

#------------------------------------------------------------------------------------------------------#

plt.plot(constraint.WTOoS,constraint.PWCruise, label='Cruise')
plt.plot(constraint.WTOoS,constraint.PWTakeOff, label='Take Off')
plt.plot(constraint.WTOoS,constraint.PWClimb, label='Climb')
plt.plot(constraint.WTOoS,constraint.PWTurn, label='Turn')
plt.plot(constraint.WTOoS,constraint.PWCeiling, label='Ceiling')
plt.plot(constraint.WTOoS,constraint.PWAcceleration, label='Acceleration')
plt.plot(constraint.WTOoSLanding, constraint.PWLanding, label='Landing')
plt.plot(constraint.DesignWTOoS, constraint.DesignPW, marker='o', markersize = 10, markerfacecolor = 'red', markeredgecolor = 'black')
# plt.plot(performance.WTOoSTorenbeek, performance.PWTorenbeek, label='Torenbeek')
plt.ylim([0, 300])
plt.xlim([0, 7000])
plt.legend()
plt.grid(visible=True)
plt.xlabel('$W_{TO}/S$')
plt.ylabel('$P/W_{TO}$')
# plt.clf()

# times = np.linspace(0,mission.profile.MissionTime2,num = 1000)

# plt.plot(times/60,mission.profile.SuppliedPowerRatio(times))
# plt.grid(visible=True)
# plt.xlabel('t [min]')
# plt.ylabel('Altitude [m]')
# plt.clf()

# plt.plot(times,mission.profile.PowerExcess(times))
# plt.grid(visible=True)
# plt.clf()

# plt.plot(times,mission.profile.Velocity2(times))
# plt.grid(visible=True)

# # Using the mediator to perform aircraft design
# myaircraft.design_aircraft()

# Performing some operations...

end_time = time.time()
execution_time =  end_time - start_time
print("Execution time:",execution_time)
