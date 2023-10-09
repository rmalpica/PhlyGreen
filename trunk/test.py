import PhlyGreen as pg

# Creating subsystem instances
powertrain = pg.Systems.Powertrain.Powertrain(None)
structures = pg.Systems.Structures.Structures(None)
aerodynamics = pg.Systems.Aerodynamics.Aerodynamics(None)

performance = pg.Performance.Performance(None)
mission = pg.Mission.Mission(None)

# Creating mediator and associating with subsystems
myaircraft = pg.Aircraft(powertrain, structures, aerodynamics, performance, mission)

# Associating subsystems with the mediator
powertrain.aircraft = myaircraft
structures.aircraft = myaircraft
aerodynamics.aircraft = myaircraft
performance.aircraft = myaircraft
mission.aircraft = myaircraft


# Using the mediator to perform aircraft design
myaircraft.design_aircraft()

# Performing some operations...

