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


# # Creating mediator and associating with subsystems
myaircraft = pg.Aircraft(powertrain, structures, aerodynamics, performance, mission)



# # Associating subsystems with the mediator
# powertrain.aircraft = myaircraft
# structures.aircraft = myaircraft
# aerodynamics.aircraft = myaircraft
# mission.aircraft = myaircraft
performance.aircraft = myaircraft

aerodynamics.set_quadratic_polar(10,0.8)




WTOoS = np.linspace(1, 7000, num=100)
PW = np.linspace(1, 300, num=100)


# -----------------------------------------------------------------#
# Indeces of flight phases:
# 1: Cruise
# 2: Take off
# 3: Climb
# 4: Turn
# 5: Ceiling
# 6: Acceleration -----> Speed: Average speed during acceleration
# 7: Landing 
# -----------------------------------------------------------------#

ConstraintsInput = {'speed': np.array([0.41, 70, 59*1.4, 0.3, 0.41, 0.35, 59.]) ,
                    'speedtype': ['Mach','TAS','TAS','Mach','Mach','Mach','TAS']   ,
                    'beta': np.array([0.9,1.,0.95, 0.9, 0.8, 0.9, 0.])   ,
                    'altitude': np.array([5450.,100.,2000.,5486.4,7600.,5486.4, 500.]) ,
                    }


PsAcceleration = 2.28

performance.FindDesignPoint(ConstraintsInput, WTOoS, 0, 1.2, 1000, 0.021, 0.5, PsAcceleration)


# Plotting
plt.plot(WTOoS,performance.PWCruise, label='Cruise')
plt.plot(WTOoS,performance.PWTakeOff, label='Take Off')
plt.plot(WTOoS,performance.PWClimb, label='Climb')
plt.plot(WTOoS,performance.PWTurn, label='Turn')
plt.plot(WTOoS,performance.PWCeiling, label='Ceiling')
plt.plot(WTOoS,performance.PWAcceleration, label='Acceleration')
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



# # Using the mediator to perform aircraft design
# myaircraft.design_aircraft()

# Performing some operations...

