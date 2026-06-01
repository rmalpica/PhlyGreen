import sys
import os
sys.path.insert(0,'../')
import PhlyGreen as pg
import sys
import os
import numpy as np
import matplotlib.pyplot as plt
import scienceplots

plt.style.use(['science','ieee','high-vis'])


def AircraftDesign(input,battery_class):

    powertrain = pg.Systems.Powertrain.Powertrain(None)
    structures = pg.Systems.Structures.Structures(None)
    aerodynamics = pg.Systems.Aerodynamics.Aerodynamics(None)
    performance = pg.Performance.Performance(None)
    mission = pg.Mission.Mission(None)
    weight = pg.Weight.Weight(None)
    constraint = pg.Constraint.Constraint(None)
    welltowake = pg.WellToWake.WellToWake(None)
    battery = pg.Systems.Battery.Battery(None)
    climateimpact = pg.ClimateImpact.ClimateImpact(None)

    myaircraft = pg.Aircraft(powertrain, structures, aerodynamics, performance, mission, weight, constraint, welltowake, battery, climateimpact)

    powertrain.aircraft = myaircraft
    structures.aircraft = myaircraft
    aerodynamics.aircraft = myaircraft
    mission.aircraft = myaircraft
    performance.aircraft = myaircraft
    weight.aircraft = myaircraft
    constraint.aircraft = myaircraft
    welltowake.aircraft = myaircraft
    battery.aircraft = myaircraft

            
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
            'Beta start': 0.985,
            'Payload Weight': 4560,  #Kg
            'Crew Weight': 500}  #Kg

    AerodynamicsInput = {'NumericalPolar': {'type': 'ATR42'},
                'Take Off Cl': 1.9,
                    'Landing Cl': 1.9,
                    'Minimum Cl': 0.20,
                    'Cd0': 0.017}

    MissionStages = {'Takeoff': {'Supplied Power Ratio':{'phi': 0}},
                'Climb1': {'type': 'ConstantRateClimb', 'input': {'CB': 0.12, 'Speed': 77, 'StartAltitude': 100, 'EndAltitude': 1500}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }},
                'Climb2': {'type': 'ConstantRateClimb', 'input': {'CB': 0.06, 'Speed': 110, 'StartAltitude': 1500, 'EndAltitude': 4500}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }},
                'Climb3': {'type': 'ConstantRateClimb', 'input': {'CB': 0.05, 'Speed': 110, 'StartAltitude': 4500, 'EndAltitude': 8000}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }},
                'Cruise': {'type': 'ConstantMachCruise', 'input':{ 'Mach': 0.45, 'Altitude': 8000}, 'Supplied Power Ratio':{'phi_start': input, 'phi_end':input}},
                'Descent1': {'type': 'ConstantRateDescent', 'input':{'CB': -0.04, 'Speed': 90, 'StartAltitude': 8000, 'EndAltitude': 200}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }}}

    DiversionStages = {'Climb1': {'type': 'ConstantRateClimb', 'input': {'CB': 0.06, 'Speed': 110, 'StartAltitude': 200, 'EndAltitude': 3100}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }},
                'Cruise': {'type': 'ConstantMachCruise', 'input':{ 'Mach': 0.2, 'Altitude': 3100}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0}},
                'Descent1': {'type': 'ConstantRateDescent', 'input':{'CB': -0.04, 'Speed': 90, 'StartAltitude': 3100, 'EndAltitude': 200}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }}}

    EnergyInput = {'Ef': 43.5*10**6,
                'Contingency Fuel': 130,
                'Eta Gas Turbine Model': 'PW127',
                #'Eta Gas Turbine': 0.22,
                'Eta Gearbox': 0.96,
                'Eta Propulsive Model': 'constant',
                'Eta Propulsive': 0.75,
                'Specific Power Powertrain': [3900,7700],  # W/Kg
                'Eta Electric Motor 1': 0.96,    #for serial config
                'Eta Electric Motor 2': 0.96,    #for serial config
                'Eta Electric Motor': 0.98,      #for parallel config
                'Specific Power PMAD': [2200,2200,2200],
                'PowertoWeight Powertrain': [150,33],
                'PowertoWeight PMAD': 0,
                'Eta PMAD': 0.99,
                }

    CellInput = {'Class': "II",
                'Model':'Finger-Cell-Thermal',
                'SpecificPower': 8000,
                'SpecificEnergy': 1500,
                'Minimum SOC': 0.2,
                'Pack Voltage':800,
                'Initial temperature': 25,
                'Max operative temperature':50,
                'Ebat': 1000 * 3600, # PhlyGreen uses this input only if Class == 'I'
                'pbat': 1000}

                
    WellToTankInput = {'Eta Charge': 1.,
                        'Eta Grid': 0.95,
                        'Eta Extraction': 1.,
                        'Eta Production': 1.,
                        'Eta Transportation': 0.25}

    # print('-----------------------------------------')


    myaircraft.Configuration = 'Hybrid'
    myaircraft.HybridType = 'Parallel'
    myaircraft.AircraftType = 'ATR'
    myaircraft.weight.Class = 'I'
    from FLOPS_input import FLOPS_input
    myaircraft.FLOPSInput = FLOPS_input

    myaircraft.DesignAircraft(AerodynamicsInput,ConstraintsInput,MissionInput,EnergyInput,MissionStages,DiversionStages,WellToTankInput=WellToTankInput,CellInput=CellInput,PrintOutput=False)

    print('MTOM: ', myaircraft.weight.WTO)
    #print('Source Energy: ', myaircraft.welltowake.SourceEnergy/1.e6, ' MJ')

    return(myaircraft.weight.WBat)

PHI = np.arange(0,1.1,0.1)
WBAT1 = [] 
WBAT2 = [] 

for phi in PHI:
    wbat1 = AircraftDesign(phi,'I')
    WBAT1.append(wbat1)
    wbat2 = AircraftDesign(phi,'II')
    WBAT2.append(wbat2)

plt.figure(figsize=(3,2.2))
plt.plot(PHI,WBAT1)
plt.plot(PHI,WBAT2)
plt.savefig('wbat.png', dpi=600, bbox_inches='tight')
plt.close()