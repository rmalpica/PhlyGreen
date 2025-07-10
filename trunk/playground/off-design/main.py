import sys
import PhlyGreen as pg
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
import os
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from optFunctions import coarse_to_fine_parallel_search, optimise_phi_T_cma, is_close 
from plotFunctions import plot_cma_diagnostics

def main():
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
    climateimpact.aircraft = myaircraft

    phi_TO = 0.0
    phi_CL0= 0.0
    phi_CL1 = 0.2 
    phi_CR0 = 0.1
    phi_CR1 = 0.0

    ConstraintsInput = {'DISA': 0.,
                        'Cruise': {'Speed': 0.5, 'Speed Type':'Mach', 'Beta': 0.95, 'Altitude': 8000.},
                        'AEO Climb': {'Speed': 210, 'Speed Type':'KCAS', 'Beta': 0.97, 'Altitude': 6000., 'ROC': 5},
                        'OEI Climb': {'Speed': 1.2*34.5, 'Speed Type': 'TAS', 'Beta': 1., 'Altitude': 0., 'Climb Gradient': 0.021},
                        'Take Off': {'Speed': 90, 'Speed Type': 'TAS', 'Beta': 1., 'Altitude': 100., 'kTO': 1.2, 'sTO': 950},
                        'Landing':{'Speed': 59., 'Speed Type': 'TAS', 'Altitude': 500.},
                        'Turn':{'Speed': 210, 'Speed Type': 'KCAS', 'Beta': 0.9, 'Altitude': 5000, 'Load Factor': 1.1},
                        'Ceiling':{'Speed': 0.5, 'Beta': 0.8, 'Altitude': 9500, 'HT': 0.5},
                        'Acceleration':{'Mach 1': 0.3, 'Mach 2':0.4, 'DT': 180, 'Altitude': 6000, 'Beta': 0.9}}

    MissionInput = {'Range Mission': 750,  #nautical miles
                    'Range Diversion': 220,  #nautical miles
                    'Beta start': 0.97,
                    'Payload Weight': 4560,  #Kg
                    'Crew Weight': 500}  #Kg

    MissionStages = {'Takeoff': {'Supplied Power Ratio':{'phi': phi_TO}},
                    'Climb1': {'type': 'ConstantRateClimb', 'input': {'CB': 0.16, 'Speed': 77, 'StartAltitude': 100, 'EndAltitude': 1500}, 'Supplied Power Ratio':{'phi_start': phi_CL0, 'phi_end':phi_CL0}},
                     'Climb2': {'type': 'ConstantRateClimb', 'input': {'CB': 0.08, 'Speed': 120, 'StartAltitude': 1500, 'EndAltitude': 4500}, 'Supplied Power Ratio':{'phi_start': phi_CL0, 'phi_end':phi_CL0 }},
                     'Climb3': {'type': 'ConstantRateClimb', 'input': {'CB': 0.07, 'Speed': 125, 'StartAltitude': 4500, 'EndAltitude': 8000}, 'Supplied Power Ratio':{'phi_start': phi_CL0, 'phi_end':phi_CL1 }},
                     'Cruise': {'type': 'ConstantMachCruise', 'input':{ 'Mach': 0.4, 'Altitude': 8000}, 'Supplied Power Ratio':{'phi_start': phi_CR0, 'phi_end':phi_CR1}},
                     'Descent1': {'type': 'ConstantRateDescent', 'input':{'CB': -0.05, 'Speed': 90, 'StartAltitude': 8000, 'EndAltitude': 200}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }}}

    DiversionStages = {'Climb1': {'type': 'ConstantRateClimb', 'input': {'CB': 0.08, 'Speed': 110, 'StartAltitude': 200, 'EndAltitude': 3100}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }},
                     'Cruise': {'type': 'ConstantMachCruise', 'input':{ 'Mach': 0.35, 'Altitude': 3100}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0}},
                     'Descent1': {'type': 'ConstantRateDescent', 'input':{'CB': -0.04, 'Speed': 90, 'StartAltitude': 3100, 'EndAltitude': 200}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }}}


    EnergyInput = {'Ef': 43.5*10**6,
                       'Contingency Fuel': 130,
                       'Ebat': 700 * 3600,
                       'pbat': 1000,
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

    CellInput = {
        'Class': "II",
        'Model':'Finger-Cell-Thermal',
        'SpecificPower': 8000,
        'SpecificEnergy': 1500,
        'Minimum SOC': 0.2,
        'Pack Voltage':800,
        'Initial temperature': 25,
        'Max operative temperature':50,
        'Ebat': 1000 * 3600, # PhlyGreen uses this input only if Class == 'I'
        'pbat': 1000
        }

    AerodynamicsInput = {'AnalyticPolar': {'type': 'Quadratic', 'input': {'AR': 11, 'e_osw': 0.8}},
                        'Take Off Cl': 1.9,
                         'Landing Cl': 1.9,
                         'Minimum Cl': 0.20,
                         'Cd0': 0.017}


    WellToTankInput = {'Eta Charge': 0.95,
                       'Eta Grid': 1.,
                       'Eta Extraction': 1.,
                       'Eta Production': 1.,
                       'Eta Transportation': 0.25}

    ClimateImpactInput = {'H': 100, 'N':1.6e7, 'Y':30, 'EINOx_model':'Filippone', 'WTW_CO2': 8.30e-3, 'Grid_CO2': 9.36e-2}

    myaircraft.ConstraintsInput = ConstraintsInput
    myaircraft.AerodynamicsInput = AerodynamicsInput
    myaircraft.MissionInput = MissionInput
    myaircraft.MissionStages = MissionStages
    myaircraft.DiversionStages = DiversionStages
    myaircraft.EnergyInput = EnergyInput
    myaircraft.CellInput = CellInput
    myaircraft.WellToTankInput = WellToTankInput
    myaircraft.ClimateImpactInput = ClimateImpactInput

    myaircraft.Configuration = 'Hybrid'
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
    myaircraft.weight.Class = 'I'

    myaircraft.weight.SetInput()

    #Initialize Battery Configurator
    myaircraft.battery.SetInput()

    #Initialized Well to Tank
    myaircraft.welltowake.SetInput()

    # Initialize Climate Impace Estimator
    myaircraft.climateimpact.SetInput()

    myaircraft.constraint.FindDesignPoint()
    print('----------------------------------------')
    print('Design W/S: ',myaircraft.DesignWTOoS)
    print('Design P/W: ',myaircraft.DesignPW)
    print('----------------------------------------')

    plt.plot(myaircraft.constraint.WTOoS,myaircraft.constraint.PWCruise, label='Cruise')
    plt.plot(myaircraft.constraint.WTOoS,myaircraft.constraint.PWTakeOff, label='Take Off')
    plt.plot(myaircraft.constraint.WTOoS,myaircraft.constraint.PWAEOClimb, label='Climb')
    plt.plot(myaircraft.constraint.WTOoS,myaircraft.constraint.PWOEIClimb, label='Climb OEI')
    plt.plot(myaircraft.constraint.WTOoS,myaircraft.constraint.PWTurn, label='Turn')
    plt.plot(myaircraft.constraint.WTOoS,myaircraft.constraint.PWCeiling, label='Ceiling')
    plt.plot(myaircraft.constraint.WTOoS,myaircraft.constraint.PWAcceleration, label='Acceleration')
    plt.plot(myaircraft.constraint.WTOoSLanding,myaircraft. constraint.PWLanding, label='Landing')
    plt.plot(myaircraft.DesignWTOoS, myaircraft.DesignPW, marker='o', markersize = 10, markerfacecolor = 'red', markeredgecolor = 'black')
    # plt.plot(performance.WTOoSTorenbeek, performance.PWTorenbeek, label='Torenbeek')
    plt.ylim([0, 300])
    plt.xlim([0, 7000])
    plt.legend()
    plt.grid(visible=True)
    plt.xlabel('$W_{TO}/S$')
    plt.ylabel('$P/W_{TO}$')
    plt.savefig('constraint_diagram.png', dpi=800, transparent=False)

    myaircraft.weight.WeightEstimation()

    myaircraft.WingSurface = myaircraft.weight.WTO / myaircraft.DesignWTOoS * 9.81

    if (myaircraft.Configuration == 'Hybrid' and WellToTankInput is not None):
        myaircraft.welltowake.EvaluateSource()

    myaircraft.Print_Aircraft_Design_Summary()

    myaircraft.MissionType = 'Continue'
    myaircraft.climateimpact.calculate_mission_emissions()
    print(myaircraft.climateimpact.mission_emissions)

    myaircraft.climateimpact.ATR()

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


    toplot = np.array(mission.plottingVars)
    soc   = toplot[:, 1]
    v_oc  = toplot[:, 2]
    v_out = toplot[:, 3]
    curr  = toplot[:, 4]
    temp  = toplot[:, 5]
    atemp = toplot[:, 6]
    alt   = toplot[:, 7]

    fig, ax = plt.subplots(figsize=(3.5,3))
    ax.plot(times/60,[mission.profile.SuppliedPowerRatio(t) for t in times], 'b')
    #plt.plot(myaircraft.mission.profile.Breaks,np.ones(6)*0.05, '*')
    ax.grid(visible=True)
    ax.set_xlabel('t [min]')
    ax.set_ylabel('Phi')
    fig.savefig('phi.png', dpi=800, transparent=False, bbox_inches='tight')

    fig, ax = plt.subplots(figsize=(3.5,3))
    ax.plot(times/60,soc, 'b')
    ax.grid(visible=True)
    ax.set_xlabel('t [min]')
    ax.set_ylabel('State Of Charge')
    fig.savefig('soc.png', dpi=800, transparent=False, bbox_inches='tight')

    fig, ax = plt.subplots(figsize=(3.5,3)) 
    ax.plot(times/60,[myaircraft.performance.PoWTO(myaircraft.DesignWTOoS,beta[t],myaircraft.mission.profile.PowerExcess(times[t]),1,myaircraft.mission.profile.Altitude(times[t]),myaircraft.mission.DISA,myaircraft.mission.profile.Velocity(times[t]),'TAS') for t in range(len(times))], 'b')
    ax.grid(visible=True)
    ax.set_xlabel('t [min]')
    ax.set_ylabel('Pp/W')
    fig.savefig('PoverW.png', dpi=800, transparent=False, bbox_inches='tight')

    fig, ax = plt.subplots(figsize=(3.5,3))
    ax.plot(times/60,[(myaircraft.weight.WTO/1000) * myaircraft.performance.PoWTO(myaircraft.DesignWTOoS,beta[t],myaircraft.mission.profile.PowerExcess(times[t]),1,myaircraft.mission.profile.Altitude(times[t]),myaircraft.mission.DISA,myaircraft.mission.profile.Velocity(times[t]),'TAS') for t in range(len(times))], 'b')
    ax.grid(visible=True)
    ax.set_xlabel('t [min]')
    ax.set_ylabel('Pp [kW]')
    fig.savefig('Pp.png', dpi=800, transparent=False, bbox_inches='tight')

    fig, ax = plt.subplots(figsize=(3.5,3))
    ax.plot(times,Ef, 'b')
    #ax.plot(myaircraft.mission.profile.Breaks,np.ones(6)*0.05, '*')
    ax.grid(visible=True)
    ax.set_xlabel('t [min]')
    ax.set_ylabel('Efuel')
    fig.savefig('Efuel.png', dpi=800, transparent=False, bbox_inches='tight')

    fig, ax = plt.subplots(figsize=(3.5,3))
    ax.plot(times,beta, 'b')
    #ax.plot(myaircraft.mission.profile.Breaks,np.ones(6)*0.05, '*')
    ax.grid(visible=True)
    ax.set_xlabel('t [min]')
    ax.set_ylabel('beta')
    fig.savefig('beta.png', dpi=800, transparent=False, bbox_inches='tight')


    # Now run off-design mission to find the optimal phi strategy that minimizes fuel burn
    payload = myaircraft.weight.WPayload
    typical_range = 250

    # Best way so far: grid search with class II battery
    lo_phi, lo_fuel = coarse_to_fine_parallel_search(
    aircraft=myaircraft,
    typical_range=250,
    payload=myaircraft.weight.WPayload,
    fidelity='II',
    soc_min=myaircraft.battery.SOC_min,
    total_budget=300
    )

    print('\nBest solution found with High-Fidelity:')
    print('Best phi:', lo_phi)
    print('Fuel burn:', lo_fuel)

    sys.exit() 

    # Previous Best way: grid search with class I battery, then refine with class II battery using CMA with class I optimum as first guess
    fidelity = 'I'

    lo_phi, lo_fuel = coarse_to_fine_parallel_search(
    aircraft=myaircraft,
    typical_range=250,
    payload=myaircraft.weight.WPayload,
    fidelity='I',
    soc_min=myaircraft.battery.SOC_min,
    total_budget=300
    )

    print('\nBest solution found with Low-Fidelity:')
    print('Best phi:', lo_phi)
    print('Fuel burn:', lo_fuel) 

    # --- HIGH-FIDELITY OPTIMIZATION ---
    fidelity = 'II'
    print(f"Running High-Fidelity optimization for guess: {lo_phi}")

    phi_low = lo_phi
    delta = 0.15
    lower_bounds, upper_bounds = adaptive_bounds(phi_low, delta=delta, asym_scale=2.0)

    hi_phi, hi_fuel, hi_fit_hist, hi_scat_hist = optimise_phi_T_cma(
        myaircraft, typical_range, payload, fidelity,
        x0guess=phi_low,
        lower_bounds=lower_bounds,
        upper_bounds=upper_bounds,
        delta=delta,
        maxiter=5,
        popsize=os.cpu_count()
    )
    plot_cma_diagnostics(hi_fit_hist, hi_scat_hist, fidelity, 999)

    # Final output
    print('\nBest solution found with High-Fidelity:')
    print('Best phi:', hi_phi)
    print('Fuel burn:', hi_fuel) 

    sys.exit()

    # What follows is a more expensive way of doing it: CMA also for the class I, run on many initial guesses to avoid minima with very high phi.
    
    # Draw a contour map of fuel burn on a grid of phiCL-phiCRZ
    print('Evaluating ang plotting a contour map of fuel burn on a grid of phiCL-phiCRZ with fidelity I')
    plot_fuel_contour(myaircraft, typical_range, payload, fidelity, resolution=40)

    # Deal with multiple minima by running multiple first guesses and selecting the best of the bests
    initial_guesses = [
        (0.5, 0.5),   # Balanced
        (phi_CL1, phi_CR0),   # Nominal-like
        (0.0, 0.7),   # Electric cruise only
    ]

    best_overall_phi = None
    best_overall_fuel = float('inf')

    previous_hi_fi_points = []  # to store phi vectors already explored at hi-fi

    for idx, x0 in enumerate(initial_guesses):
        # --- LOW-FIDELITY OPTIMIZATION ---
        fidelity = 'I'
        print(f"Running Low-Fidelity optimization for guess #{idx}: {x0}")
        lo_phi, lo_fuel, lo_fit_hist, lo_scat_hist = optimise_phi_T_cma(
            myaircraft, typical_range, payload, fidelity,
            x0guess=x0,
            delta=1,
            maxiter=100,
            popsize=os.cpu_count(),
            tolx = 5e-3
        )
        plot_cma_diagnostics(lo_fit_hist, lo_scat_hist, fidelity, idx)

        if lo_phi is None:
            continue  # skip failed low-fi

        # Check if this low-fidelity optimum is near any previously evaluated hi-fi point
        too_close = any(is_close(lo_phi, prev_phi) for prev_phi in previous_hi_fi_points)

        if too_close:
            print(f"Skipping High-Fidelity optimization for guess #{idx} — similar to previous one.")
            continue

        # --- HIGH-FIDELITY OPTIMIZATION ---
        fidelity = 'II'
        print(f"Running High-Fidelity optimization for guess #{idx}: {lo_phi}")

        phi_low = lo_phi
        delta = 0.15
        lower_bounds, upper_bounds = adaptive_bounds(phi_low, delta=delta, asym_scale=2.0)

        hi_phi, hi_fuel, hi_fit_hist, hi_scat_hist = optimise_phi_T_cma(
            myaircraft, typical_range, payload, fidelity,
            x0guess=phi_low,
            lower_bounds=lower_bounds,
            upper_bounds=upper_bounds,
            delta=delta,
            maxiter=5,
            popsize=os.cpu_count()
        )
        plot_cma_diagnostics(hi_fit_hist, hi_scat_hist, fidelity, idx)

        if hi_phi is not None:
            previous_hi_fi_points.append(hi_phi)
            if hi_fuel < best_overall_fuel:
                best_overall_phi = hi_phi
                best_overall_fuel = hi_fuel

    # Final output
    print('\nBest solution found with High-Fidelity:')
    print('Best phi:', best_overall_phi)
    print('Fuel burn:', best_overall_fuel) 

    



if __name__ == "__main__":
    main()
