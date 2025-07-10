import PhlyGreen as pg
import numpy as np
from scipy.optimize import brenth 
import copy

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

def simulate_offdesign_mission(phi_vec, sized_aircraft, newrange, payload, fidelity='I', verbose=False):
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
    if(verbose): print('simulate mission with phi_vec: ', phi_vec)
    if(verbose): print('Battery fidelity: ', fidelity)

    aircraft = copy.deepcopy(sized_aircraft)

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

    # Define Class I limitations on power and energy
    facPwr = 1.0
    soc_min = 0.2

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
            if(verbose): print("No valid sub-interval found where the function crosses zero.")
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
                if(verbose): print("No valid sub-interval found where the function crosses zero.")
                return 1e10, 0, True
            else:
                a, b = brackets[0]
                if(verbose): print(f"Using bracket: [{a}, {b}]") 
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
        if (soc_end < soc_min): 
            if(verbose): print(f"Class I ERROR: not enough battery energy on-board. SOC_min={soc_end:.2f}")
            return 1e10, 0, True

        elif (newbatteryPower > facPwr*batteryPower):
            if(verbose): print(f"Class I ERROR: battery not capable of providing peak power ({facPwr*100:.2f}%). Peak is {100*newbatteryPower/batteryPower:.2f} %. ")
            return 1e10, 0, True

    if(verbose): print("Battery energy consumed [%]: ", 100*(newbatteryEnergy/batteryEnergy))

    if(verbose): print("Battery peak power absorption wrt design [%]: ", 100*(newbatteryPower/batteryPower))

    if(verbose): print("Fuel burn: ", fuel_burn)
    if(verbose): print("SOC @ landing: ", soc_end)

    return fuel_burn, soc_end, False

def sim_offdesign_wrapped(args):
    phi_raw, aircraft, typical_range, payload, fidelity, soc_min = args
    phi = np.clip(phi_raw, 0.0, 1.0)

    try:
        fuel, soc_end, vio = simulate_offdesign_mission(phi, aircraft, typical_range, payload, fidelity)
    except Exception as e:
        #print(f"Simulation failed for phi={phi}: {e}")
        return (1e10, phi, False, 1e4)  # dummy values

    penalty = 0.0
    if soc_end < soc_min:
        penalty += 1e4 * (soc_min - soc_end)**2
    if vio:
        penalty += 1e4

    total = fuel + penalty
    return (total, phi, penalty == 0.0, fuel)