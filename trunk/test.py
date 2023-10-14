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




WTOoS = np.linspace(1, 8000, num=100)
PW = np.linspace(1, 300, num=100)


# -----------------------------------------------------------------#
# Indeces of flight phases:
# 1: Cruise
# 2: Take off
# 3: Climb
# 4: Turn
# -----------------------------------------------------------------#

ConstraintsInput = {'speed': np.array([0.41, 70, 59*1.4, 0.3]) ,
                    'speedtype': ['Mach','TAS','TAS','Mach']   ,
                    'beta': np.array([0.9,1.,0.95, 0.9])   ,
                    'altitude': np.array([5450.,100.,2000.,5486.4]) ,
                    }




performance.EvaluateConstraints(ConstraintsInput, WTOoS, 0, 1.2, 1000, 0.021)

# CROCIERA = performance.PoWTO(CARICHI, 0.9, 0, 1, 5450, 0, 0.41, 'Mach')
# CLIMB = performance.PoWTO(CARICHI, 0.95, 0.021*1.4*59, 1, 2000, 0, 1.4*59, 'TAS')
# VIRATA = performance.PoWTO(CARICHI, 0.9, 0, 1.1, 5486.4, 0, 0.3, 'Mach')
# DECOLLO_H = performance.TakeOff(CARICHI, 1., 100, 1.2, 1000, 15, 70, 'TAS')
# DECOLLO_C = performance.TakeOff(CARICHI, 1., 100, 1.2, 1000, -15, 70, 'TAS')
# LANDING = aerodynamics.ClMax*59**2*pg.Utilities.Atmosphere.atmosphere.RHOstd(500,0)
# CEILING = performance.PoWTO(CARICHI, 0.8, 0.5, 1, 7600, 0, speed, speedtype)
# DECOLLO_TORENBEEK = performance.TakeOff_TORENBEEK(PW, 100 , 1000, 1.15, 10.7, 1.25, 0.02, 70, 'TAS', 0)
#print('PIPPO: ', DECOLLO_TORENBEEK)



# Plotting
plt.plot(WTOoS,performance.PWCruise, label='Cruise')
plt.plot(WTOoS,performance.PWTakeOff, label='Take Off')
plt.plot(WTOoS,performance.PWClimb, label='Climb')
plt.plot(WTOoS,performance.PWTurn, label='Turn')
plt.ylim([0, 300])
plt.legend()
plt.grid(visible=True)



# # Using the mediator to perform aircraft design
# myaircraft.design_aircraft()

# Performing some operations...

