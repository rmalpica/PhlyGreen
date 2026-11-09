"""Compute every number quoted in the powertrain manual and write it to data/powertrain_data.json.

Run from anywhere with the phlygreen environment:
    python manuals/powertrain/scripts/compute_data.py

The reference configurations are those of trunk/examples/common.py. Each block below fills
one entry of the ``data`` dictionary; make_figures.py reads the JSON file and draws the
figures. Nothing here changes the package.
"""

import json
import os
import sys
import time
import warnings

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MANUAL = os.path.dirname(HERE)
TRUNK = os.path.abspath(os.path.join(MANUAL, "..", "..", "trunk"))
sys.path.insert(0, os.path.join(TRUNK, "examples"))   # common.py
sys.path.insert(0, HERE)                              # example_new_architecture.py

import PhlyGreen as pg
from PhlyGreen.Systems.Powertrain.graph import (traditional_graph, parallel_hybrid_graph,
                                                serial_hybrid_graph, fuelcell_battery_graph)
from PhlyGreen.Systems.Powertrain.efficiency import (MotorEfficiencyModel, OperatingPoint,
                                                     ConstantEfficiency)
from common import (traditional_config, hybrid_config, hydrogen_config,
                    fuelcell_battery_config, turbofan_config)
import example_new_architecture as newarch

warnings.simplefilter("ignore")
data = {}
timing = {}
t_start = time.time()


def designed(config):
    """Build an aircraft and run the full design for ``config``."""
    aircraft = pg.build_aircraft()
    aircraft.configure(config)
    return aircraft


def configured(config):
    """Build an aircraft and read the inputs without designing (powertrain ready)."""
    aircraft = pg.build_aircraft()
    aircraft.configure(config, design=False)
    return aircraft


def as_list(x):
    return [float(v) for v in np.asarray(x).ravel()]


# ------------------------------------------------------------------------------------------
# 1. Reference efficiencies, read from the configured powertrains of common.py
# ------------------------------------------------------------------------------------------
t0 = time.time()
pt_par = configured(hybrid_config('I', 'Parallel')).powertrain
pt_ser = configured(hybrid_config('I', 'Serial')).powertrain
pt_trad = configured(traditional_config()).powertrain
# The code has no default fuel-cell efficiency for the graph ('Eta Fuel Cell' has no default
# and the fuel-cell missions use the physics model); 0.5 is an illustrative value set here.
ETA_FC_GRAPH = 0.5
fcb_cfg = fuelcell_battery_config()
fcb_cfg.energy.eta_fuel_cell = ETA_FC_GRAPH
pt_fcb = configured(fcb_cfg).powertrain
ETA = {
    'gt': pt_par.eta('gas_turbine'), 'gb': pt_par.eta('gearbox'),
    'pp': pt_par.eta('propeller'), 'pm': pt_par.eta('pmad'),
    'em': pt_par.eta('electric_motor'), 'em1': pt_ser.EtaEM1, 'em2': pt_ser.EtaEM2,
    'ser_generator': pt_ser.eta('generator'), 'ser_electric_motor': pt_ser.eta('electric_motor'),
}
# Efficiencies the Powertrain object holds for the fuel-cell + battery configuration
# (read by Powertrain.PowerRatioFuelCellBattery), next to the inputs of the config.
data['fcb_powertrain_eta'] = {
    'fuel_cell': pt_fcb.eta('fuel_cell'), 'pmad': pt_fcb.eta('pmad'),
    'electric_motor': pt_fcb.eta('electric_motor'), 'gearbox': pt_fcb.eta('gearbox'),
    'propeller': pt_fcb.eta('propeller'),
    'config_eta_pmad': fcb_cfg.energy.eta_pmad,
    'config_eta_electric_motor': fcb_cfg.energy.eta_electric_motor,
    'config_eta_propulsive': fcb_cfg.energy.eta_propulsive,
}
ETA_FC = {'fc': ETA_FC_GRAPH, 'pm': fcb_cfg.energy.eta_pmad,
          'em': fcb_cfg.energy.eta_electric_motor, 'gb': fcb_cfg.energy.eta_gearbox,
          'pp': fcb_cfg.energy.eta_propulsive}
data['eta'] = ETA
data['eta_fc_graph'] = ETA_FC

# ------------------------------------------------------------------------------------------
# 2. Power-ratio vectors of the four graphs at phi = 0 and phi = 0.3
# ------------------------------------------------------------------------------------------
def solve_all(phi):
    return {
        'traditional': traditional_graph(ETA['gt'], ETA['gb'], ETA['pp']).solution(),
        'parallel': parallel_hybrid_graph(ETA['gt'], ETA['gb'], ETA['pm'], ETA['em'],
                                          ETA['pp'], phi).solution(),
        'serial': serial_hybrid_graph(ETA['gt'], ETA['em1'], ETA['pm'], ETA['em2'],
                                      ETA['gb'], ETA['pp'], phi).solution(),
        'fuelcell_battery': fuelcell_battery_graph(ETA_FC['fc'], ETA_FC['pm'], ETA_FC['em'],
                                                   ETA_FC['gb'], ETA_FC['pp'], phi).solution(),
    }

data['ratios'] = {f"{phi:.1f}": {k: {v: float(abs(x)) for v, x in sol.items()}
                                 for k, sol in solve_all(phi).items()}
                  for phi in (0.0, 0.3)}

# The Powertrain methods return the same vectors (np.abs of the graph solution).
data['powertrain_methods_phi03'] = {
    'Traditional': as_list(pt_trad.Traditional(0.0, 100.0, 1e6)),
    'Hybrid_parallel': as_list(pt_par.Hybrid(0.3, 0.0, 100.0, 1e6)),
    'Hybrid_serial': as_list(pt_ser.Hybrid(0.3, 0.0, 100.0, 1e6)),
    'PowerRatioFuelCellBattery': as_list(pt_fcb.PowerRatioFuelCellBattery(0.3, 0.0, 100.0, 1e6)),
}

# ------------------------------------------------------------------------------------------
# 3. Sweep of phi for the three hybrid graphs
# ------------------------------------------------------------------------------------------
phis = np.round(np.linspace(0.0, 0.9, 19), 3)
sweep = {'phi': as_list(phis), 'parallel': {}, 'serial': {}, 'fuelcell_battery': {}}
for name in ('parallel', 'serial', 'fuelcell_battery'):
    rows = [solve_all(float(p))[name] for p in phis]
    for var in rows[0]:
        sweep[name][var] = [float(abs(r[var])) for r in rows]
data['phi_sweep'] = sweep
timing['graphs'] = time.time() - t0

# ------------------------------------------------------------------------------------------
# 4. Graph solvers against the legacy hand-coded matrices
# ------------------------------------------------------------------------------------------
t0 = time.time()
alts, vels, pwrs = [0.0, 4000.0, 8000.0], [80.0, 120.0, 160.0], [1.0e5, 1.0e6]
equiv_phis = [0.0, 0.1, 0.3, 0.5, 0.8]
max_diff = {'Traditional': 0.0, 'Parallel': 0.0, 'Serial': 0.0}
n_points = {'Traditional': 0, 'Parallel': 0, 'Serial': 0}
for a in alts:
    for v in vels:
        for p in pwrs:
            d = np.max(np.abs(pt_trad.Traditional(a, v, p) - pt_trad._traditional_legacy(a, v, p)))
            max_diff['Traditional'] = max(max_diff['Traditional'], float(d))
            n_points['Traditional'] += 1
            for phi in equiv_phis:
                for key, pt in (('Parallel', pt_par), ('Serial', pt_ser)):
                    d = np.max(np.abs(pt.Hybrid(phi, a, v, p) - pt._hybrid_legacy(phi, a, v, p)))
                    max_diff[key] = max(max_diff[key], float(d))
                    n_points[key] += 1
data['equivalence'] = {'max_abs_diff': max_diff, 'n_points': n_points,
                       'phis': equiv_phis}
timing['equivalence'] = time.time() - t0

# ------------------------------------------------------------------------------------------
# 5. Reference designs: powertrain masses and ratings
# ------------------------------------------------------------------------------------------
def get(obj, name):
    """Attribute value, or None when the attribute is missing or its property raises."""
    try:
        value = getattr(obj, name)
    except Exception:
        return None
    if value is None:
        return None
    return float(value)


def design_record(aircraft):
    pt, m, w = aircraft.powertrain, aircraft.mission, aircraft.weight
    rec = {
        'WTO': get(w, 'WTO'), 'WPT': get(w, 'WPT'), 'Wf': get(w, 'Wf'), 'WBat': get(w, 'WBat'),
        'WStructure': get(w, 'WStructure'), 'DesignPW': get(aircraft, 'DesignPW'),
        'WThermal': get(pt, 'WThermal'), 'WElectric': get(pt, 'WElectric'),
        'WMotor': get(pt, 'WMotor'), 'WPMAD': get(pt, 'WPMAD'),
        'WGenerator': get(pt, 'WGenerator'), 'engineRating': get(pt, 'engineRating'),
        'Max_PEng': get(m, 'Max_PEng'), 'Max_PEng_alt': get(m, 'Max_PEng_alt'),
        'TO_PP': get(m, 'TO_PP'), 'Max_PBat': get(m, 'Max_PBat'), 'TO_PBat': get(m, 'TO_PBat'),
        'Max_PMotor': get(m, 'Max_PMotor'), 'TO_PMotor': get(m, 'TO_PMotor'),
        'Max_PBus': get(m, 'Max_PBus'), 'TO_PBus': get(m, 'TO_PBus'),
        'closure_WPT': float(w.powertrain_in_closure(w.WPT)),
    }
    if aircraft.Configuration in ('Traditional', 'Hybrid'):
        lapse = pt.PowerLapse(m.Max_PEng_alt, 0)
        rec['PowerLapse_at_peak'] = float(lapse)
        rec['Max_PEng_lapsed'] = float(m.Max_PEng / lapse)
    if aircraft.Configuration in ('Hydrogen', 'FuelCellBattery'):
        fc = aircraft.fuelcell
        rec['fc_weight_total'] = get(w, 'WPT')
        rec['fc_stack_bop_pmad'] = get(w, 'WThermal')      # set by FuelCell._size_stack
        rec['fc_motor'] = get(w, 'WElectric')               # set by FuelCell._size_stack
        # FuelCell._size_stack: M_EM = P_drive_elec * EtaPM / sp_motor and
        # M_PM = (P_drive_elec + P_aux_tms) / sp_pmad, so the PMAD follows from the motor.
        P_drive_elec = w.WElectric * pt.SPowerPT[1] / fc.EtaPM
        rec['fc_P_drive_elec'] = float(P_drive_elec)
        rec['fc_pmad'] = float((P_drive_elec + fc.P_aux_tms) / pt.pmad_specific_power())
        rec['fc_stack_bop'] = float(w.WThermal - rec['fc_pmad'])
        rec['fc_P_rated'] = float(fc.P_fc_rated)
        rec['Max_PDrive'] = get(m, 'Max_PDrive')
        rec['fc_eta_downstream'] = float(fc.EtaEM * fc.EtaPM * fc.EtaGB * fc.EtaProp)
    if aircraft.Configuration == 'Turbofan':
        rec['thrust_cases'] = {k: float(v) for k, v in pt._thrust_sizing_cases.items()}
        rec['engine_thrust_to_weight'] = float(pt.engine_thrust_to_weight)
        rec['turbofan_design_thrust'] = float(pt.turbofan_design_thrust)
        rec['gearbox_eta'] = pt.efficiency['gearbox'].value
        rec['propeller_eta'] = pt.efficiency['propeller'].value
    return rec


designs = {}
reference = [('Traditional', traditional_config()),
             ('Parallel', hybrid_config('I', 'Parallel')),
             ('Serial', hybrid_config('I', 'Serial')),
             ('Hydrogen', hydrogen_config()),
             ('FuelCellBattery', fuelcell_battery_config()),
             ('Turbofan', turbofan_config())]
aircraft_by_name = {}
for name, cfg in reference:
    t0 = time.time()
    ac = designed(cfg)
    designs[name] = design_record(ac)
    timing['design_' + name] = time.time() - t0
    aircraft_by_name[name] = ac
    print(f"designed {name:16s} WTO = {designs[name]['WTO']:9.1f} kg  "
          f"({timing['design_' + name]:.1f} s)", flush=True)
data['designs'] = designs
report = aircraft_by_name['Turbofan'].powertrain.report_turbofan_sizing(warn=False)
data['turbofan_report'] = {'sizing_case': report['sizing_case'],
                           'required_SLS_thrust': float(report['required_SLS_thrust']),
                           'nominal': float(report['nominal']),
                           'nominal_ratio': float(report['nominal_ratio'])}

# ------------------------------------------------------------------------------------------
# 6. Power ratios along the mission of the parallel and serial designs
# ------------------------------------------------------------------------------------------
def mission_ratios(aircraft):
    """Time, altitude, phi, propulsive power and the Hybrid power-ratio vector at every
    accepted integration point of the design mission (Class-I battery: y[2] is Beta)."""
    m, prof, perf, pt = aircraft.mission, aircraft.mission.profile, aircraft.performance, aircraft.powertrain
    WTO, WS, DISA = aircraft.weight.WTO, aircraft.DesignWTOoS, m.DISA
    t = np.concatenate([s.t for s in m.integral_solution])
    beta = np.concatenate([s.y[2] for s in m.integral_solution])
    alt = np.array([float(prof.Altitude(x)) for x in t])
    vel = np.array([float(prof.Velocity(x)) for x in t])
    phi = np.array([float(prof.SuppliedPowerRatio(x)) for x in t])
    pp = np.array([WTO * perf.PoWTO(WS, beta[i], float(prof.PowerExcess(t[i])), 1, alt[i],
                                    DISA, vel[i], 'TAS') for i in range(len(t))])
    ratios = np.array([pt.Hybrid(phi[i], alt[i], vel[i], pp[i]) for i in range(len(t))])
    return {'t': as_list(t), 'alt': as_list(alt), 'phi': as_list(phi), 'PP': as_list(pp),
            'ratios': [as_list(r) for r in ratios.T],
            'mission_end_time': float(prof.MissionTime)}   # end of the design mission (diversion follows)

t0 = time.time()
data['mission'] = {'Parallel': mission_ratios(aircraft_by_name['Parallel']),
                   'Serial': mission_ratios(aircraft_by_name['Serial'])}
timing['mission_ratios'] = time.time() - t0

# ------------------------------------------------------------------------------------------
# 7. Design sweep over the cruise phi (end of the linear cruise ramp)
# ------------------------------------------------------------------------------------------
t0 = time.time()
phi_ends = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
design_sweep = {'phi_end': phi_ends, 'Parallel': [], 'Serial': []}
for hybrid_type in ('Parallel', 'Serial'):
    for phi_end in phi_ends:
        cfg = hybrid_config('I', hybrid_type)
        for seg in cfg.mission_stages.segments:
            if seg.name == 'Cruise':
                seg.phi_end = phi_end
        design_sweep[hybrid_type].append(design_record(designed(cfg)))
data['design_sweep'] = design_sweep
timing['design_sweep'] = time.time() - t0

# ------------------------------------------------------------------------------------------
# 8. Class-II electric motor (d-q model) in the parallel graph
# ------------------------------------------------------------------------------------------
t0 = time.time()
motor = MotorEfficiencyModel(design_kw=2000, design_v=800, design_rpm=1200)
powers = np.linspace(1.0e5, 3.0e6, 30)
eta_motor = [float(motor.eta(OperatingPoint(power=float(p), rpm=1200.0))) for p in powers]
pt_par.em_model = motor
pbat_smart = [float(pt_par.Hybrid(0.3, 8000.0, 120.0, float(p))[5]) for p in powers]
pt_par.em_model = None
pbat_const = float(pt_par.Hybrid(0.3, 8000.0, 120.0, 1.0e6)[5])
pt_par.em_model = ConstantEfficiency(pt_par.EtaEM)
pbat_const_model = float(pt_par.Hybrid(0.3, 8000.0, 120.0, 1.0e6)[5])
pt_par.em_model = None
pt_par.em_model = motor
motor_shaft_ratio = [float(pt_par.Hybrid(0.3, 8000.0, 120.0, float(p))[2]) for p in powers]
pt_par.em_model = None
data['motor'] = {'power': as_list(powers), 'eta': eta_motor, 'pbat_ratio_smart': pbat_smart,
                 'motor_shaft_ratio_smart': motor_shaft_ratio,
                 'pbat_ratio_const': pbat_const, 'pbat_ratio_const_model': pbat_const_model,
                 'design_efficiency': float(motor.motor.design_efficiency),
                 'mass_one_motor': float(motor.weight()),
                 'eta_at_1MW': float(motor.eta(OperatingPoint(power=1e6, rpm=1200.0))),
                 'pbat_low_3e5': float(pbat_smart[0]),
                 'pbat_high_3e6': float(pbat_smart[-1])}
timing['motor'] = time.time() - t0

# Power passed to the efficiency models: the total propulsive power. At the cruise point
# above, the gas-turbine shaft and motor shaft powers per unit propulsive power are:
r = data['ratios']['0.3']['parallel']
data['operating_point_power'] = {'Pgt_over_Pp_parallel_phi03': r['Pgt'],
                                 'Pmotor_over_Pp_parallel_phi03': r['Pgb'],
                                 'Pgt_over_Pp_traditional': data['ratios']['0.0']['traditional']['Pgt'],
                                 # share of Pp delivered by the motor branch: eta_gb*eta_pp*Pgb
                                 'parallel_motor_share_phi03': r['Pgb'] * ETA['gb'] * ETA['pp']}

# Battery terminal power per unit Pp at phi = 0.3: the graph (phi = Pbat/(Pfc + Pbat)) and the
# FuelCellBattery mission (battery covers phi * Pp through the chain
# eta_em*eta_pm*eta_gb*eta_pp, Mission._fc_battery_eta_elec) use the same convention.
chain = ETA_FC['em'] * ETA_FC['pm'] * ETA_FC['gb'] * ETA_FC['pp']
data['fc_phi_conventions_phi03'] = {'graph_Pbat': data['ratios']['0.3']['fuelcell_battery']['Pbat'],
                                    'mission_Pbat': 0.3 / chain, 'electric_chain': chain}

# ------------------------------------------------------------------------------------------
# 9. Turbofan: the single overall-efficiency node
# ------------------------------------------------------------------------------------------
t0 = time.time()
tf = aircraft_by_name['Turbofan']
pt_tf = tf.powertrain
prof = tf.mission.profile
t_cruise = None
for sol in tf.mission.integral_solution:            # first accepted point flown at cruise Mach
    for k, tk in enumerate(sol.t):
        if abs(float(prof.PowerExcess(tk))) < 1e-9 and float(prof.Altitude(tk)) > 9000.0:
            t_cruise, beta_cruise = float(tk), float(sol.y[1][k])
            break
    if t_cruise is not None:
        break
alt_c, vel_c = float(prof.Altitude(t_cruise)), float(prof.Velocity(t_cruise))
pp_c = tf.weight.WTO * tf.performance.PoWTO(tf.DesignWTOoS, beta_cruise, 0.0, 1, alt_c,
                                            tf.mission.DISA, vel_c, 'TAS')
pr_c = pt_tf.Traditional(alt_c, vel_c, pp_c)
eta_o = pt_tf.eta('gas_turbine', alt_c, vel_c, pp_c)
lhv = tf.weight.ef
data['turbofan_point'] = {'alt': alt_c, 'vel': vel_c, 'PP': float(pp_c), 'thrust': float(pp_c / vel_c),
                          'eta_o': float(eta_o), 'PRatio': as_list(pr_c),
                          'PRatio0_times_eta_o': float(pr_c[0] * eta_o),
                          'tsfc_g_per_kN_s': float(vel_c / (eta_o * lhv) * 1e6),
                          'LHV': float(lhv)}
timing['turbofan_point'] = time.time() - t0

# ------------------------------------------------------------------------------------------
# 10. Worked example: the partial turbo-electric architecture
# ------------------------------------------------------------------------------------------
eta_new = dict(eta_gt=0.22, eta_gb=0.96, eta_pp=0.9, eta_gen=0.96, eta_pm=0.99,
               eta_em=0.96, eta_fan=0.9)
new = {}
for xi in (0.0, 0.2, 0.5):
    sol = newarch.partial_turboelectric_graph(xi=xi, **eta_new).solution()
    new[f"{xi:.1f}"] = {'solution': {k: float(v) for k, v in sol.items()},
                        'closed_form_Pf': float(newarch.fuel_ratio_closed_form(xi=xi, **eta_new))}
data['new_architecture'] = new

timing['total'] = time.time() - t_start
data['timing_s'] = timing

out = os.path.join(MANUAL, 'data', 'powertrain_data.json')
with open(out, 'w') as f:
    json.dump(data, f, indent=1)
print(f"wrote {out}  (total {timing['total']:.1f} s)")
