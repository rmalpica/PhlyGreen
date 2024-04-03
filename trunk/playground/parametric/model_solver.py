import numpy as np
import sys


#sys.path.insert(0, '../')
import PhlyGreen as pg

def model_solver(parameters):
    
    print('Starting with aircraft design ...')
    # ebat, phi_start, phi_end = parameters
    phi_start = phi_end = parameters[0]
    etaFuel = parameters[1]
    wttCO2 = parameters[2]
    gridCO2 = parameters[3] 
    ebat = 1000
    print('ebat: %f, phi(CRZ): %f, etaFuel: %f, wttCO2: %f, gridCO2: %f' %(ebat, phi_start, etaFuel, wttCO2, gridCO2))

    WellToTankInput = {'Eta Charge': 0.95,
                       'Eta Grid': 1.,
                       'Eta Extraction': 1.,
                       'Eta Production': 1.,
                       'Eta Transportation': etaFuel}

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

    MissionStages = {'Takeoff': {'Supplied Power Ratio':{'phi': 0.0}},
                     'Climb1': {'type': 'ConstantRateClimb', 'input': {'CB': 0.12, 'Speed': 77, 'StartAltitude': 100, 'EndAltitude': 1500}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }},
                     'Climb2': {'type': 'ConstantRateClimb', 'input': {'CB': 0.06, 'Speed': 110, 'StartAltitude': 1500, 'EndAltitude': 4500}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }},
                     'Climb3': {'type': 'ConstantRateClimb', 'input': {'CB': 0.05, 'Speed': 110, 'StartAltitude': 4500, 'EndAltitude': 8000}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }},
                     'Cruise': {'type': 'ConstantMachCruise', 'input':{ 'Mach': 0.45, 'Altitude': 8000}, 'Supplied Power Ratio':{'phi_start': phi_start, 'phi_end': phi_end }},
                     'Descent1': {'type': 'ConstantRateDescent', 'input':{'CB': -0.04, 'Speed': 90, 'StartAltitude': 8000, 'EndAltitude': 200}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }}}
    DiversionStages = {'Climb1': {'type': 'ConstantRateClimb', 'input': {'CB': 0.06, 'Speed': 110, 'StartAltitude': 200, 'EndAltitude': 3100}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }},
                     'Cruise': {'type': 'ConstantMachCruise', 'input':{ 'Mach': 0.2, 'Altitude': 3100}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0}},
                     'Descent1': {'type': 'ConstantRateDescent', 'input':{'CB': -0.04, 'Speed': 90, 'StartAltitude': 3100, 'EndAltitude': 200}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }}}

    AerodynamicsInput = {'NumericalPolar': {'type': 'ATR42'},
                    'Take Off Cl': 1.9,
                     'Landing Cl': 1.9,
                     'Minimum Cl': 0.20,
                     'Cd0': 0.017}

    EnergyInput = {'Ef': 43.5*10**6,
                   'Contingency Fuel': 130,
                   'Ebat': ebat * 3600,
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


    powertrain = pg.Systems.Powertrain.Powertrain(None)
    structures = pg.Systems.Structures.Structures(None)
    aerodynamics = pg.Systems.Aerodynamics.Aerodynamics(None)
    performance = pg.Performance.Performance(None)
    mission = pg.Mission.Mission(None)
    weight = pg.Weight.Weight(None)
    constraint = pg.Constraint.Constraint(None)
    welltowake = pg.WellToWake.WellToWake(None)


    # # Creating mediator and associating with subsystems
    myaircraft = pg.Aircraft(powertrain, structures, aerodynamics, performance, mission, weight, constraint, welltowake)



    # # Associating subsystems with the mediator
    powertrain.aircraft = myaircraft
    structures.aircraft = myaircraft
    aerodynamics.aircraft = myaircraft
    mission.aircraft = myaircraft
    performance.aircraft = myaircraft
    weight.aircraft = myaircraft
    constraint.aircraft = myaircraft
    welltowake.aircraft = myaircraft


    #myaircraft.Configuration = 'Traditional'
    myaircraft.Configuration = 'Hybrid'
    myaircraft.HybridType = 'Parallel'
    myaircraft.AircraftType = 'ATR'
    myaircraft.DesignAircraft(AerodynamicsInput,ConstraintsInput,MissionInput,EnergyInput,MissionStages,DiversionStages,WellToTankInput=WellToTankInput,PrintOutput=False)

    SourceBattery = myaircraft.weight.TotalEnergies[1] * 1e-6 / myaircraft.welltowake.EtaSourceToBattery
    wtwCO2 = (wttCO2*43.5*myaircraft.weight.Wf) + SourceBattery*gridCO2 + myaircraft.weight.Wf*3.14  #WtW CO2


    print('Done ...')
    output = np.append(parameters,[myaircraft.weight.WTO,myaircraft.welltowake.SourceEnergy,myaircraft.welltowake.Psi,myaircraft.WingSurface,myaircraft.weight.WBat,myaircraft.weight.Wf+myaircraft.weight.final_reserve,myaircraft.weight.WPT,myaircraft.powertrain.WThermal, myaircraft.powertrain.WElectric, wtwCO2]).flatten()

    return output 






