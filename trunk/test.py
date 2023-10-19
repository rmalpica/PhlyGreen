import PhlyGreen as pg
import sys
import PhlyGreen.Utilities.Atmosphere as ISA
import numpy as np
import matplotlib.pyplot as plt

#ISA = pg.Utilities.Atmosphere()



# Creating subsystem instances
powertrain = pg.Systems.Powertrain.Powertrain(None)
structures = pg.Systems.Structures.Structures(None)
aerodynamics = pg.Systems.Aerodynamics.Aerodynamics(None)
performance = pg.Performance.Performance(None)
mission = pg.Mission.Mission(None)
weight = pg.Weight.Weight(None)


# # Creating mediator and associating with subsystems
myaircraft = pg.Aircraft(powertrain, structures, aerodynamics, performance, mission, weight)



# # Associating subsystems with the mediator
powertrain.aircraft = myaircraft
structures.aircraft = myaircraft
# aerodynamics.aircraft = myaircraft
mission.aircraft = myaircraft
performance.aircraft = myaircraft
weight.aircraft = myaircraft

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
                'Diversion altitude': 3100,
                'Diversion Mach': 0.3,
                'Payload Weight': (5255),
                'Crew Weight': (95*3)}

TechnologyInput = {'Ef': 43.5*10**6,
                   'Eta Gas Turbine': 0.3,
                   'Eta Gearbox': 0.96,
                   'Eta Propulsive': 0.9,
                   'Specific Power Powertrain': 3600,
                   'PowertoWeight Powertrain': 177
                   }

myaircraft.ReadInput(ConstraintsInput,MissionInput,TechnologyInput)

# powertrain.Traditional()

performance.FindDesignPoint()
# mission.EvaluateMission(18000)

WTO = weight.WeightEstimation()[-1]
print('WTO: ',WTO)
print('Superficie alare: ', WTO / performance.DesignWTOoS * 9.81)
             
#----------------------------------------------- PLOT -------------------------------------------------#                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           

fig, ax1 = plt.subplots()

color = 'tab:red'
ax1.set_xlabel('Time (min)')
ax1.set_ylabel('E [J]')
ax1.plot(mission.t/60, mission.Ef, color=color, label='E')
ax1.tick_params(axis='y')
plt.legend()

ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis

color = 'tab:blue'
ax2.set_ylabel('beta')  # we already handled the x-label with ax1
ax2.plot(mission.t/60, mission.Beta, color=color, label='beta')
ax2.tick_params(axis='y')

fig.tight_layout()  # otherwise the right y-label is slightly clipped
ax1.legend()
ax2.legend()
ax1.grid(visible=True)
plt.show()
plt.clf()

#------------------------------------------------------------------------------------------------------#

plt.plot(performance.WTOoS,performance.PWCruise, label='Cruise')
plt.plot(performance.WTOoS,performance.PWTakeOff, label='Take Off')
plt.plot(performance.WTOoS,performance.PWClimb, label='Climb')
plt.plot(performance.WTOoS,performance.PWTurn, label='Turn')
plt.plot(performance.WTOoS,performance.PWCeiling, label='Ceiling')
plt.plot(performance.WTOoS,performance.PWAcceleration, label='Acceleration')
plt.plot(performance.WTOoSLanding, performance.PWLanding, label='Landing')
plt.plot(performance.DesignWTOoS, performance.DesignPW, marker='o', markersize = 10, markerfacecolor = 'red', markeredgecolor = 'black')
# plt.plot(performance.WTOoSTorenbeek, performance.PWTorenbeek, label='Torenbeek')
plt.ylim([0, 300])
plt.xlim([0, 7000])
plt.legend()
plt.grid(visible=True)
plt.xlabel('$W_{TO}/S$')
plt.ylabel('$P/W_{TO}$')
# plt.clf()



# plt.plot(mission.t/60,mission.Altitude(mission.t))


# # Using the mediator to perform aircraft design
# myaircraft.design_aircraft()

# Performing some operations...

