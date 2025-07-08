import sys
import PhlyGreen as pg
import numpy as np
from scipy.optimize import brenth 
import matplotlib.pyplot as plt
import cma
import pandas as pd
import copy
import multiprocessing as mp


def funcOffD(Wf, aircraft, WPayload, OEW, wbattery):
     #print(f"Trying Wf = {Wf:.6f}")
     run = aircraft.mission.EvaluateMission(OEW + WPayload+ Wf + wbattery)
     newfuel = run[0]/aircraft.weight.ef
     if newfuel == 0: 
          print(run[1])
          return np.nan
     result = Wf - newfuel
     #print(f"               -> funcOffD = {result:.6f}")
     return result

def simulate_offdesign_mission(phi_vec, aircraft, newrange, payload, fidelity='I'):
    """
    Runs the typical-mission performance/energy model.

    Parameters
    ----------
    phi_vec : array_like, shape (4,)
        [phi_TO, phi_CL, phi_CR0, phi_CR1]
    Returns
    -------
    fuel_burn : float         # kg
    soc_end   : float         # [-]
    violated  : bool          # True if any TLAR or power limit fails *during* the mission
    """
    print('simulate mission with phi_vec: ', phi_vec)
    print('Battery fidelity: ', fidelity)

    #phiTO = phi_vec[0]
    phiTO = aircraft.mission.profile.MissionStages['Takeoff']['Supplied Power Ratio']['phi']
    phiCL = phi_vec[0]
    phiCR0 = phi_vec[1]
    phiCR1 = phi_vec[1] #constant cruise phi
    #phiCR1 = phi_vec[2] #constant cruise phi

    # Grab info on nominal mission and sizing
    wfuel = aircraft.weight.Wf 
    OEW = aircraft.weight.WPT + aircraft.weight.WStructure + aircraft.weight.WCrew + aircraft.weight.final_reserve
    wbattery = aircraft.weight.WBat
    batteryEnergy = aircraft.mission.EBat[-1]/(1-aircraft.battery.SOC_min)
    batteryPower = max(aircraft.mission.TO_PBat,aircraft.mission.Max_PBat)

    # Define new (off-design) mission
    newmission = pg.Mission.Mission(aircraft)
    aircraft.mission = newmission

    WPayload = payload

    MissionInput = {'Range Mission': newrange,  #nautical miles
                    'Range Diversion': 220,  #nautical miles
                    'Beta start': 0.985,
                    'Payload Weight': WPayload,  #Kg
                    'Crew Weight': 500}  #Kg

    MissionStages = {'Takeoff': {'Supplied Power Ratio':{'phi': phiTO}},
                     'Climb1': {'type': 'ConstantRateClimb', 'input': {'CB': 0.12, 'Speed': 77, 'StartAltitude': 100, 'EndAltitude': 1500}, 'Supplied Power Ratio':{'phi_start': 0., 'phi_end':0. }},
                     'Climb2': {'type': 'ConstantRateClimb', 'input': {'CB': 0.06, 'Speed': 110, 'StartAltitude': 1500, 'EndAltitude': 4500}, 'Supplied Power Ratio':{'phi_start': phiCL, 'phi_end':phiCL }},
                     'Climb3': {'type': 'ConstantRateClimb', 'input': {'CB': 0.05, 'Speed': 110, 'StartAltitude': 4500, 'EndAltitude': 6000}, 'Supplied Power Ratio':{'phi_start': phiCL, 'phi_end':phiCL}},
                     'Cruise': {'type': 'ConstantMachCruise', 'input':{ 'Mach': 0.45, 'Altitude': 6000}, 'Supplied Power Ratio':{'phi_start': phiCR0, 'phi_end':phiCR1}},
                     'Descent1': {'type': 'ConstantRateDescent', 'input':{'CB': -0.05, 'Speed': 90, 'StartAltitude': 6000, 'EndAltitude': 200}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }}}

    DiversionStages = {'Climb1': {'type': 'ConstantRateClimb', 'input': {'CB': 0.06, 'Speed': 110, 'StartAltitude': 200, 'EndAltitude': 3100}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }},
                     'Cruise': {'type': 'ConstantMachCruise', 'input':{ 'Mach': 0.2, 'Altitude': 3100}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0}},
                     'Descent1': {'type': 'ConstantRateDescent', 'input':{'CB': -0.04, 'Speed': 90, 'StartAltitude': 3100, 'EndAltitude': 200}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }}}

    aircraft.MissionInput = MissionInput
    aircraft.MissionStages = MissionStages
    aircraft.DiversionStages = DiversionStages

    aircraft.mission.InitializeProfile()
    aircraft.mission.SetInput()
    aircraft.battery.BatteryClass = fidelity
    aircraft.mission.size_battery_pack = False

    # Take care of class II battery with some tricks to deal with unfeasible solutions

    if fidelity == 'II':

        # bracket fuel interval
        N = 50
        Wfs = np.linspace(0, wfuel, N)
        allfuel = []
        for fuelw in Wfs: 
            wf = funcOffD(fuelw, aircraft, WPayload, OEW, wbattery)
            if np.isnan(wf):
                break
            allfuel.append(wf)
            if wf > 0: break

        if len(allfuel) < 2:
            print("No valid sub-interval found where the function crosses zero.")
            return 1e10, 0, True
        else:
            brackets = []

            for i in range(len(allfuel) - 1):
                v0 = allfuel[i]
                v1 = allfuel[i + 1]
                if np.isnan(v0) or np.isnan(v1):
                    continue
                if v0 * v1 < 0:
                    brackets.append((Wfs[i], Wfs[i + 1]))

            if not brackets:
                print("No valid sub-interval found where the function crosses zero.")
                return 1e10, 0, True
            else:
                a, b = brackets[0]
                print(f"Using bracket: [{a}, {b}]") 
    else:
        a, b = 0, wfuel

    # refine search
    newwfuel=brenth(funcOffD, a, b , args=(aircraft, WPayload, OEW, wbattery), xtol=0.01)  #newfuel is the fuel on board for the typical mission including diversion
    newbatteryEnergy = aircraft.mission.EBat[-1]
    newbatteryPower = max(aircraft.mission.TO_PBat,aircraft.mission.Max_PBat)

    times = np.array([])
    Ef    = np.array([])
    for array in aircraft.mission.integral_solution: #or equivalently: newmission.integral_solution
        times = np.concatenate([times, array.t])
        Ef    = np.concatenate([Ef   , array.y[0]])

    fuel_burn = Ef[np.where(times==aircraft.mission.profile.Breaks[5])[0][0]]/aircraft.weight.ef #index 5 corresponds to 6th profile break (end of descent)

    if fidelity == 'II':
        soc_end = aircraft.battery.SOC
    else:
        soc_end = 1.0 - (newbatteryEnergy/batteryEnergy) 
        if (soc_end < 0.2): 
            print("Class I ERROR: not enough battery energy on-board")
            return 1e10, 0, True

        elif (newbatteryPower > batteryPower):
            print("CLass I ERROR: battery not capable of providing peak power")
            return 1e10, 0, True

    print("Battery energy consumed [%]: ", 100*(newbatteryEnergy/batteryEnergy))

    print("Battery peak power absorption wrt design [%]: ", 100*(newbatteryPower/batteryPower))

    print("Fuel burn: ", fuel_burn)
    print("SOC @ landing: ", soc_end)

    return fuel_burn, soc_end, False

def optimise_phi_T_cma(aircraft, typical_range, payload, fidelity,
                       x0guess=(0.3, 0.2),
                       lower_bounds = [0.0, 0.0],
                       upper_bounds = [1.0, 1.0],
                       delta = 1,
                       maxiter = 50,
                       popsize = 6
                       ):
    
    soc_min = aircraft.battery.SOC_min

    best_phi = None
    best_fuel = float('inf')

    # Penalized objective function
    def obj(phi_raw):
        nonlocal best_phi, best_fuel
        phi = np.clip(phi_raw, lower_bounds, upper_bounds)
        try:
            fuel, soc_end, vio = simulate_offdesign_mission(phi, aircraft, typical_range, payload, fidelity)
        except:
            return 1e10  # failsafe for simulation errors

        # Constraint violation penalty
        penalty = 0.0
        if soc_end < soc_min:
            penalty += 1e4 * (soc_min - soc_end) ** 2
        if vio:
            penalty += 1e4

        total = fuel + penalty

        # Track best feasible solution
        if penalty == 0.0 and fuel < best_fuel:
            best_phi = phi.copy()
            best_fuel = fuel

        return total

    x0 = np.array(x0guess)
    sigma0 = delta / 4 #0.2

    es = cma.CMAEvolutionStrategy(x0, sigma0, {
        'bounds': [lower_bounds, upper_bounds],
        'popsize': popsize,
        'maxiter': maxiter,
        'verb_disp': 1,
    })

    fitness_history = []
    while not es.stop():
        candidates = es.ask()
        fitness = [obj(c) for c in candidates]
        es.tell(candidates, fitness)
        fitness_history.append(min(fitness))  # store best of this generation

    if best_phi is None:
        print("No feasible solution found — all violated constraints.")
        return None, None

    print('Best feasible phi:', best_phi)
    print('Fuel burn:', best_fuel)

    fig, ax = plt.subplots(figsize=(3.5,3))
    ax.plot(fitness_history)
    ax.grid(visible=True)
    ax.set_xlabel("Generation")
    ax.set_ylabel("Best fitness - Fuel burn [kg]")
    ax.set_ylim([0., 500])
    ax.set_title("High-fidelity CMA convergence")
    fig.savefig(f'CMA_fitness_fidelity_{fidelity}.png', dpi=800, transparent=False, bbox_inches='tight')

    return best_phi, best_fuel



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


    payload = myaircraft.weight.WPayload
    typical_range = 250
    fidelity = 'I'

    sized_aircraft = copy.deepcopy(myaircraft)

    best_phi, fuelatlanding = optimise_phi_T_cma(sized_aircraft, typical_range, payload, fidelity,
                       x0guess=(phi_CL1, phi_CR0),
                       delta = 1,
                       maxiter = 100,
                       popsize = 6
                       )
    
    print('best solution with Low-Fidelity: ', best_phi, fuelatlanding)

    fidelity = 'II'
    sized_aircraft = copy.deepcopy(myaircraft)

    delta = 0.1 #this tells how far the optimizer will look from the low-fi best solution
    phi_low =  best_phi
    lower_bounds = np.clip(phi_low - delta, 0.0, 1.0)
    upper_bounds = np.clip(phi_low + delta, 0.0, 1.0)

    best_phi, fuelatlanding = optimise_phi_T_cma(sized_aircraft, typical_range, payload, fidelity,
                       x0guess=phi_low,
                       lower_bounds = lower_bounds,
                       upper_bounds = upper_bounds,
                       delta = delta,
                       maxiter = 5,
                       popsize = 3
                       )
    
    print('best solution with High-Fidelity: ', best_phi, fuelatlanding)
    
if __name__ == "__main__":
    main()
