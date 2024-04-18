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
welltowake = pg.WellToWake.WellToWake(None)
climateimpact = pg.ClimateImpact.ClimateImpact(None)


# # Creating mediator and associating with subsystems
myaircraft = pg.Aircraft(powertrain, structures, aerodynamics, performance, mission, weight, constraint, welltowake = welltowake, climateimpact = climateimpact)



# # Associating subsystems with the mediator
powertrain.aircraft = myaircraft
structures.aircraft = myaircraft
aerodynamics.aircraft = myaircraft
mission.aircraft = myaircraft
performance.aircraft = myaircraft
weight.aircraft = myaircraft
constraint.aircraft = myaircraft
welltowake.aircraft = myaircraft
climateimpact.aircraft = myaircraft

#aerodynamics.set_quadratic_polar(11,0.8)



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

ConstraintsInput = {'Cruise': {'Speed': 0.4, 'Speed Type':'Mach', 'Beta': 0.95, 'Altitude': 8000.},
         'AEO Climb': {'Speed': 170, 'Speed Type':'KCAS', 'Beta': 0.97, 'Altitude': 6000., 'ROC': 5},
         'OEI Climb': {'Speed': 104*1.2, 'Speed Type': 'KCAS', 'Beta': 1., 'Altitude': 0., 'Climb Gradient': 0.021},
         'Take Off': {'Speed': 140, 'Speed Type': 'KCAS', 'Beta': 0.985, 'Altitude': 100., 'kTO': 1.2, 'sTO': 950},
         'Landing':{'Speed': 104., 'Speed Type': 'KCAS', 'Altitude': 0.},
         'Turn':{'Speed': 210, 'Speed Type': 'KCAS', 'Beta': 0.9, 'Altitude': 5000, 'Load Factor': 1.1},
         'Ceiling':{'Speed': 0.5, 'Beta': 0.8, 'Altitude': 9500, 'HT': 0.5},
         'Acceleration':{'Mach 1': 0.3, 'Mach 2':0.4, 'DT': 180, 'Altitude': 6000, 'Beta': 0.9},
         'DISA': 0}    

MissionInput = {'Range Mission': 750,  #nautical miles
                'Range Diversion': 220,  #nautical miles
                'Time Loiter': 30, #Minutes
                'Beta start': 0.97,
                'Payload Weight': 4560,  #Kg
                'Crew Weight': 500}  #Kg

MissionStages = {'Takeoff': {'Supplied Power Ratio':{'phi': 0.0}},
                     'Climb1': {'type': 'OptimumClimb', 'input': {'CB': 0.12, 'Speed': 77, 'StartAltitude': 100, 'EndAltitude': 1500}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.1 }},
                     'Climb2': {'type': 'OptimumClimb', 'input': {'CB': 0.06, 'Speed': 110, 'StartAltitude': 1500, 'EndAltitude': 4500}, 'Supplied Power Ratio':{'phi_start': 0.1, 'phi_end':0.2 }},
                     'Climb3': {'type': 'OptimumClimb', 'input': {'CB': 0.05, 'Speed': 110, 'StartAltitude': 4500, 'EndAltitude': 8000}, 'Supplied Power Ratio':{'phi_start': 0.2, 'phi_end':0.3 }},
                     'Cruise': {'type': 'DiscretizedCruise', 'input':{ 'Mach': 0.45, 'Altitude': 8000}, 'Supplied Power Ratio':{'phi_start': 0.5, 'phi_end': 0.2}},
                     'Descent1': {'type': 'OptimumDescent', 'input':{'CB': -0.04, 'Speed': 90, 'StartAltitude': 8000, 'EndAltitude': 200}, 'Supplied Power Ratio':{'phi_start': 0.3, 'phi_end':0.0 }}}

DiversionStages = {'Climb1': {'type': 'OptimumClimb', 'input': {'CB': 0.06, 'Speed': 110, 'StartAltitude': 200, 'EndAltitude': 3100}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }},
                     'Cruise': {'type': 'DiscretizedCruise', 'input':{ 'Mach': 0.2, 'Altitude': 3100}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0}},
                     'Descent1': {'type': 'OptimumDescent', 'input':{'CB': -0.04, 'Speed': 90, 'StartAltitude': 3100, 'EndAltitude': 200}, 'Supplied Power Ratio':{'phi_start': 0.2, 'phi_end':0.5 }}}

# LoiterStages = {'Cruise': {'type': 'ConstantMachCruise', 'input': {'Mach': 0.16, 'Altitude': 500}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }}}  

AerodynamicsInput = {'AnalyticPolar': {'type': 'Quadratic', 'input': {'AR': 11, 'e_osw': 0.8}},
                    'Take Off Cl': 1.9,
                     'Landing Cl': 1.9,
                     'Minimum Cl': 0.20,
                     'Cd0': 0.017}

ClimateImpactInput = {'H': 100, 'N':1.6e7, 'Y':30, 'EINOx_model':'Filippone'}

# EnergyInput = {'Ef': 43.5*10**6,
#                    'Contingency Fuel': 130,
#                    'Ebat': 1000 * 3600,
#                    'pbat': 1000,
#                    'Eta Gas Turbine': 0.22,
#                    'Eta Gearbox': 0.96,
#                    'Eta Propulsive': 0.9,
#                    'Eta Electric Motor 1': 0.96,    #for serial config
#                    'Eta Electric Motor 2': 0.96,    #for serial config
#                    'Eta Electric Motor': 0.98,      #for parallel config
#                    'Eta PMAD': 0.99,
#                    'Specific Power Powertrain': [3900,7700],
#                    'Specific Power PMAD': [2200,2200,2200],
#                    'PowertoWeight Battery': 35, 
#                    'PowertoWeight Powertrain': [150,33],
#                    'PowertoWeight PMAD': 0
#                    }


EnergyInput = {'Ef': 43.5*10**6,
                   'Contingency Fuel': 130,
                   'Ebat': 1000 * 3600,
                   'pbat': 1000,
                   'Eta Gas Turbine Model': 'constant',
                   'Eta Gas Turbine': 0.22,
                   'Eta Gearbox': 0.96,
                   'Eta Propulsive Model': 'constant',
                   'Eta Propulsive': 0.75,
                   'Eta Electric Motor 1': 0.96,
                   'Eta Electric Motor 2': 0.96,
                   'Eta Electric Motor': 0.98,
                   'Eta PMAD': 0.99,
                   'Specific Power Powertrain': [3900,7700],
                   'Specific Power PMAD': [2200,2200,2200],
                   'PowertoWeight Battery': 35, 
                   'PowertoWeight Powertrain': [150,33],
                   'PowertoWeight PMAD': 0}

WellToTankInput = {'Eta Charge': 0.95,
                   'Eta Grid': 1.,
                   'Eta Extraction': 1.,
                   'Eta Production': 1.,
                   'Eta Transportation': 0.25}

myaircraft.Configuration = 'Hybrid'
myaircraft.HybridType = 'Parallel'
myaircraft.AircraftType = 'ATR'
myaircraft.MissionType = 'Discrete'

myaircraft.DesignAircraft(AerodynamicsInput,ConstraintsInput,MissionInput,EnergyInput,MissionStages,DiversionStages, WellToTankInput=WellToTankInput, ClimateImpactInput = ClimateImpactInput, PrintOutput=True)


myaircraft.climateimpact.calculate_mission_emissions()
print(myaircraft.climateimpact.mission_emissions)

# myaircraft.climateimpact.plot_forcing()
# print(myaircraft.climateimpact.media_pesata_quote/0.30)
# print(myaircraft.climateimpact.s_o3s(myaircraft.climateimpact.media_pesata_quote))
# print(np.interp(myaircraft.climateimpact.media_pesata_quote,myaircraft.climateimpact.Altitudes_for_forcing,myaircraft.climateimpact.s_o3s_data))

myaircraft.climateimpact.ATR()

end_time = time.time()
execution_time =  end_time - start_time
print("Execution time:",execution_time)

#sys.exit()

# plt.plot(myaircraft.weight.WTO_vector,myaircraft.weight.Vector) 
# plt.grid(visible=True)
# plt.show()
             
# cProfile.run('weight.WeightEstimation()')
#----------------------------------------------- PLOT -------------------------------------------------#                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           

#fig, ax1 = plt.subplots()
#
#color = 'tab:red'
#ax1.set_xlabel('Time (min)')
#ax1.set_ylabel('E [J]')
#ax1.plot(mission.t/60, mission.Ef, color=color, label='E Fuel')
#ax1.plot(mission.t/60, mission.EBat, color='tab:green', label='E Battery')
#ax1.tick_params(axis='y')
#plt.legend()
#
#ax2 = ax1.twinx()  # instantiate a second axes that shares the same x-axis
#
#color = 'tab:blue'
#ax2.set_ylabel('beta')  # we already handled the x-label with ax1
#ax2.plot(mission.t/60, mission.Beta, color=color, label='beta')
#ax2.tick_params(axis='y')
#
#fig.tight_layout()  # otherwise the right y-label is slightly clipped
#ax1.legend()
#ax2.legend()
#ax1.grid(visible=True)
#plt.show()
#plt.clf()

#------------------------------------------------------------------------------------------------------#

# plt.plot(myaircraft.constraint.WTOoS,myaircraft.constraint.PWCruise, label='Cruise')
# plt.plot(myaircraft.constraint.WTOoS,myaircraft.constraint.PWTakeOff, label='Take Off')
# plt.plot(myaircraft.constraint.WTOoS,myaircraft.constraint.PWAEOClimb, label='Climb')
# plt.plot(myaircraft.constraint.WTOoS,myaircraft.constraint.PWOEIClimb, label='Climb OEI')
# plt.plot(myaircraft.constraint.WTOoS,myaircraft.constraint.PWTurn, label='Turn')
# plt.plot(myaircraft.constraint.WTOoS,myaircraft.constraint.PWCeiling, label='Ceiling')
# plt.plot(myaircraft.constraint.WTOoS,myaircraft.constraint.PWAcceleration, label='Acceleration')
# plt.plot(myaircraft.constraint.WTOoSLanding,myaircraft. constraint.PWLanding, label='Landing')
# plt.plot(myaircraft.DesignWTOoS, myaircraft.DesignPW, marker='o', markersize = 10, markerfacecolor = 'red', markeredgecolor = 'black')
# # plt.plot(performance.WTOoSTorenbeek, performance.PWTorenbeek, label='Torenbeek')
# plt.ylim([0, 300])
# plt.xlim([0, 7000])
# plt.legend()
# plt.grid(visible=True)
# plt.xlabel('$W_{TO}/S$')
# plt.ylabel('$P/W_{TO}$')
# plt.show()

# plt.plot(myaircraft.mission.profile.DiscretizedTime,[myaircraft.mission.profile.SuppliedPowerRatio(t) for t in myaircraft.mission.profile.DiscretizedTime])
# plt.show()

# plt.plot(myaircraft.mission.profile.DiscretizedTime, myaircraft.mission.EBat_values)
# plt.show()

# plt.plot(myaircraft.mission.profile.DiscretizedTime, myaircraft.mission.EF_values)
# plt.plot(myaircraft.mission.profile.Breaks, 7e10*np.ones(len(myaircraft.mission.profile.Breaks)), marker='o', markersize = 10, markerfacecolor = 'red', markeredgecolor = 'black')
# plt.show()

plt.plot(myaircraft.mission.profile.DiscretizedTime,myaircraft.mission.profile.DiscretizedAltitudes)
plt.plot(myaircraft.mission.profile.DiscretizedTime,[myaircraft.mission.profile.SuppliedPowerRatio(t)*10000 for t in myaircraft.mission.profile.DiscretizedTime])
plt.plot(myaircraft.mission.profile.Breaks, 2000*np.ones(len(myaircraft.mission.profile.Breaks)), marker='o', markersize = 10, markerfacecolor = 'red', markeredgecolor = 'black')
plt.grid(visible=True)
plt.xlabel('t [min]')
plt.ylabel('Altitude [m]')
plt.show()


# plt.plot(myaircraft.mission.profile.DiscretizedTime/60,[myaircraft.mission.profile.SuppliedPowerRatio(t) for t in myaircraft.mission.profile.DiscretizedTime])
# plt.grid(visible=True)
# plt.xlabel('t [min]')
# plt.ylabel('Velocity [m/s]')
# plt.show()

# print(myaircraft.mission.profile.DiscretizedTime)
# print([myaircraft.mission.profile.SuppliedPowerRatio(t) for t in myaircraft.mission.profile.DiscretizedTime])
# print(myaircraft.mission.profile.SuppliedPowerRatio(myaircraft.mission.profile.times[-1]))