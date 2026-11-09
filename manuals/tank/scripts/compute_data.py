"""Run the PhlyGreen designs and tank studies behind the hydrogen-tank manual.

Every number quoted in the manual comes from ../data/tank_data.json, written by this script.
It runs:

* three full aircraft designs from ``examples/common.py``:
  - ``hydrogen_config()``: hydrogen fuel-cell aircraft, gravimetric-index tank (H2-GI);
  - ``hydrogen_config(tank=True)``: the same aircraft with the cryogenic LH2 tank (H2-T),
    re-flown with ``mission.track_tank = True`` to record the tank history;
  - ``fuelcell_battery_config(tank=True)``: the fuel-cell + battery aircraft with the LH2
    tank (FCB-T), re-flown with ``mission.track_tank = True`` as well;
* full-design sweeps: maximum tank diameter and maximum tank pressure (LH2 tank), and the
  gravimetric index (no tank);
* stand-alone ``LH2_Tank`` studies: capacity, diameter and number-of-tanks sweeps (with the
  default cap of 4 tanks on the automatic split and without a cap), the heat
  leak versus ambient temperature and number of MLI layers, a parked tank (no draw), a
  heavy draw (heater), and the H2-T mission feed replayed on tank variants.

Tank variants with other database parameters are added to the in-memory ``TANK_Database``
dictionary under new keys. The file ``TANK_Database.py`` is not modified.

Runtime: about 10 minutes (each full design takes 25-50 s).
"""

import json
import os
import sys
import time
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
TRUNK = os.path.abspath(os.path.join(HERE, "..", "..", "..", "trunk"))
DATA = os.path.abspath(os.path.join(HERE, "..", "data"))
sys.path.insert(0, os.path.join(TRUNK, "examples"))

import numpy as np                                                   # noqa: E402
import CoolProp                                                      # noqa: E402
import CoolProp.CoolProp as CP                                       # noqa: E402
import PhlyGreen as pg                                               # noqa: E402
from PhlyGreen import postprocess                                    # noqa: E402
from PhlyGreen.Systems.Tank import LH2_Tank, TANK_Database, get_isa_atmosphere   # noqa: E402
from common import hydrogen_config, fuelcell_battery_config         # noqa: E402

warnings.simplefilter("ignore")

REFERENCE_MODEL = "Svensson_Default"
REFERENCE_DMAX = 2.4          # TankConfig.max_diameter of examples/common.py [m]


class TankOnlyAircraft:
    """Stand-in aircraft for stand-alone tanks: LH2_Tank only reads ``TankInput``.

    ``max_tanks='default'`` leaves out 'Max Number of Tanks', so the default cap of
    ``Tank.DEFAULT_MAX_NUMBER_OF_TANKS`` applies; ``None`` removes the cap.
    """

    def __init__(self, max_diameter, number_of_tanks, tank_model, max_tanks='default'):
        self.TankInput = {'Max Diameter': max_diameter,
                          'Number of Tanks': number_of_tanks,
                          'Tank Model': tank_model}
        if max_tanks != 'default':
            self.TankInput['Max Number of Tanks'] = max_tanks


def make_tank(capacity_kg, max_diameter=REFERENCE_DMAX, number_of_tanks=1,
              tank_model=REFERENCE_MODEL, allow_auto_split=True, max_tanks='default'):
    aircraft = TankOnlyAircraft(max_diameter, number_of_tanks, tank_model, max_tanks)
    return LH2_Tank(capacity_kg=capacity_kg, aircraft=aircraft,
                    allow_auto_split=allow_auto_split)


def safe_geometry(*args, **kwargs):
    """``tank_geometry(make_tank(...))``, or the error message when the sizing raises."""
    try:
        return tank_geometry(make_tank(*args, **kwargs))
    except ValueError as err:
        return {"error": str(err)}


def add_database_variant(key, **changes):
    """Copy the reference database entry, change some parameters, store it under ``key``."""
    params = dict(TANK_Database[REFERENCE_MODEL])
    params.update(changes)
    TANK_Database[key] = params
    return key


def tank_geometry(tank):
    """Geometry and mass breakdown of a sized tank (per tank unless stated)."""
    structure = tank.mass_inner + tank.mass_outer
    if tank.shape == "Cylinder":
        accessory_factor = (tank.accessory_mass_factor + 0.15
                            + 0.20 * tank.L_cyl / tank.r_inner)
    else:
        accessory_factor = tank.accessory_mass_factor
    return {
        "shape": tank.shape,
        "n_tanks": int(tank.n_tanks),
        "capacity_total": float(tank.m_tot_capacity),
        "capacity_single": float(tank.capacity_single),
        "V_internal": float(tank.V_internal),
        "r_inner": float(tank.r_inner),
        "L_cyl": float(tank.L_cyl),
        "r_outer": float(tank.r_outer),
        "D_outer": float(tank.D_outer),
        "area_inner": float(tank.area_inner_tot),
        "t_wall_sphere": float(tank.t_wall_sphere),
        "t_wall_cyl": float(tank.t_wall_cyl),
        "t_wall_outer_sphere": float(tank.t_wall_outer_sphere),
        "t_wall_outer_cyl": float(tank.t_wall_outer_cyl),
        "mass_inner": float(tank.mass_inner),
        "mass_outer": float(tank.mass_outer),
        "accessory_factor": float(accessory_factor),
        "mass_accessory": float(structure * (accessory_factor - 1.0)),
        "mass_insulation": float(tank.mass_insulation),
        "mass_single_empty": float(tank.mass_single_empty),
        "mass_system_empty": float(tank.mass_system_empty),
        "gravimetric_index": float(tank.gravimetric_index),
        "P_min": float(tank.P_min),
        "P_max": float(tank.P_max),
    }


def weights(aircraft):
    w = aircraft.weight
    r = aircraft.results()
    return {
        "WTO": float(w.WTO),
        "WStructure": float(w.WStructure),
        "WPT": float(w.WPT),
        "WH2_Fuel": float(w.WH2_Fuel),
        "final_reserve": float(w.final_reserve),
        "WTank": float(w.WTank),
        "WHeat_Exchanger": float(w.WHeat_Exchanger),
        "WBat": float(getattr(w, "WBat", 0.0) or 0.0),
        "WPayload": float(w.WPayload),
        "WCrew": float(w.WCrew),
        "stored_h2": float(w.WH2_Fuel + w.final_reserve),
        "system_gi": float((w.WH2_Fuel + w.final_reserve)
                           / (w.WH2_Fuel + w.final_reserve + w.WTank)),
        "results_tank_mass": float(r.tank_mass),
        "results_hex_mass": float(r.hex_mass),
        "results_empty_weight": float(r.empty_weight),
        "results_Wf": float(r.Wf),
        "results_final_reserve": float(r.final_reserve),
    }


def history_arrays(history):
    return {key: [float(v) for v in history[key]] for key in history}


def history_summary(tank, history):
    t = np.array(history['t'])
    P = np.array(history['P'])
    vent = np.array(history['Vent'])
    feed = np.array(history['Consumption'])
    dt = np.diff(t)
    # Mass drawn by the feed over the history: sum of mdot * dt over the steps after the first.
    fed = float(np.sum(feed[1:] * dt))
    at_pmax = np.where(P >= tank.P_max / 1e5 - 1e-9)[0]
    venting = np.where(vent > 0.0)[0]
    return {
        "n_steps": int(len(t)),
        "t_end": float(t[-1]),
        "dt_max": float(dt.max()),
        "dt_median": float(np.median(dt)),
        "P_min_hist": float(P.min()),
        "P_max_hist": float(P.max()),
        "t_first_Pmax": float(t[at_pmax[0]]) if len(at_pmax) else None,
        "t_first_vent": float(t[venting[0]]) if len(venting) else None,
        "m_start": float(history['m_tot'][0]),
        "m_end": float(history['m_tot'][-1]),
        "m_fed": fed,
        "m_vented": float(history['m_vent_cum'][-1]),
        "vent_max": float(vent.max()),
        "Q_in_min": float(min(history['Q_in'])),
        "Q_in_max": float(max(history['Q_in'])),
        "Q_heater_max": float(max(history['Q_heater'])),
        "feed_max": float(feed.max()),
        "t_start": float(t[0]),
        "m_fed_before_climb": float(np.sum((feed[1:] * dt)[t[1:] <= 1e-9])),
    }


def mission_feed(aircraft):
    """The hydrogen feed of the design, step by step, as the tank sees it.

    Same steps as ``Mission.compute_tank_history``: taxi-out and the take-off run at the
    constant flows of the ground segments (steps of at most 10 s at the take-off altitude),
    then the flown mission, whose hydrogen mass flow over each accepted integrator step is
    the chemical-energy increment divided by ``ef`` and ``dt``, then taxi-in.
    Returns ``(t_start, ground_alt, steps)`` with ``t_start`` the start of taxi-out on the
    profile clock.
    """
    import math
    m = aircraft.mission
    ground_alt = float(m._ground_condition()[0])
    t_start = -sum(duration for _, duration, _ in m._ground_fuel_legs_out)

    def ground(legs):
        out = []
        for _, duration, P_chem in legs:
            if duration <= 0:
                continue
            n = int(math.ceil(duration / 10.0))
            out += [(float(duration / n), float(P_chem / m.ef), ground_alt)] * n
        return out

    steps = ground(m._ground_fuel_legs_out)
    for arr in m.integral_solution:
        for k in range(1, len(arr.t)):
            dt = arr.t[k] - arr.t[k - 1]
            dE = max(float(arr.y[0][k] - arr.y[0][k - 1]), 0.0)
            m_dot = (dE / m.ef) / dt if dt > 0 else 0.0
            t_mid = 0.5 * (arr.t[k] + arr.t[k - 1])
            steps.append((float(dt), float(m_dot), float(m.profile.Altitude(t_mid))))
    steps += ground(m._ground_fuel_legs_in)
    return float(t_start), ground_alt, steps


def replay(tank, feed, substeps=1):
    """Drive a stand-alone tank with a recorded feed; each step may be split in substeps.
    The full tank is logged at the start of taxi-out, as in ``compute_tank_history``."""
    t_start, ground_alt, steps = feed
    tank.log_state(t_start, ground_alt)
    for dt, m_dot, alt in steps:
        for _ in range(substeps):
            tank.time_step(dt / substeps, m_dot, alt)
    return tank.history


def design(cfg):
    t0 = time.time()
    aircraft = pg.build_aircraft()
    aircraft.configure(cfg)
    return aircraft, time.time() - t0


def main():
    t_start = time.time()
    out = {"coolprop_version": CoolProp.__version__,
           "database": {k: v for k, v in TANK_Database[REFERENCE_MODEL].items()}}

    # ------------------------------------------------------------- para-hydrogen properties
    props = {}
    for P_bar in (1.2, 1.6, 2.0, 3.0):
        P = P_bar * 1e5
        rho_l = CP.PropsSI('D', 'P', P, 'Q', 0, 'ParaHydrogen')
        rho_g = CP.PropsSI('D', 'P', P, 'Q', 1, 'ParaHydrogen')
        h_l = CP.PropsSI('H', 'P', P, 'Q', 0, 'ParaHydrogen')
        h_g = CP.PropsSI('H', 'P', P, 'Q', 1, 'ParaHydrogen')
        props[f"{P_bar}"] = {"T_sat": CP.PropsSI('T', 'P', P, 'Q', 0, 'ParaHydrogen'),
                             "rho_l": rho_l, "rho_g": rho_g, "delta_h": h_g - h_l,
                             "rho_star": rho_g / (rho_l - rho_g)}
    out["parahydrogen"] = props

    # ------------------------------------------------------------- full designs
    print("H2-GI design ...", flush=True)
    a_gi, dt_gi = design(hydrogen_config())
    out["h2_gi"] = {"weights": weights(a_gi), "runtime": dt_gi}

    print("H2-T design ...", flush=True)
    a_t, dt_t = design(hydrogen_config(tank=True))
    tank = a_t.tank
    rec = {"weights": weights(a_t), "runtime": dt_t, "tank": tank_geometry(tank),
           "capacity_matches_load": float(tank.m_tot_capacity
                                          - (a_t.weight.WH2_Fuel + a_t.weight.final_reserve)),
           "MissionTime": float(a_t.mission.profile.MissionTime),
           "MissionTime2": float(a_t.mission.profile.MissionTime2),
           "ground_h2": float(a_t.mission.E_ground / a_t.mission.ef),
           "ef": float(a_t.mission.ef)}
    # Flown hydrogen (profile only, ground segments excluded) without the margin.
    h2_margin = a_t.EnergyInput['H2 Fuel Margin']
    flown_plus_ground = a_t.weight.WH2_Fuel / (1.0 + h2_margin)
    rec["h2_flown_plus_ground"] = float(flown_plus_ground)
    rec["h2_margin_mass"] = float(a_t.weight.WH2_Fuel - flown_plus_ground)
    # Tank state at the start of the mission, used by the transient model (T_sat, phi).
    rho_bulk = tank.m_curr / tank.V_internal
    u0 = CP.PropsSI('U', 'P', tank.P_min, 'D', rho_bulk, 'ParaHydrogen')
    u1 = CP.PropsSI('U', 'P', tank.P_min + 100.0, 'D', rho_bulk, 'ParaHydrogen')
    rec["initial_state"] = {"rho_bulk": float(rho_bulk),
                            "fill_fraction_liquid": float(rho_bulk / props["1.2"]["rho_l"]),
                            "phi": float(1.0 / (rho_bulk * (u1 - u0) / 100.0))}

    # Tracked mission (track_tank) and the post-processing equivalent.
    t0 = time.time()
    a_t.mission.track_tank = True
    a_t.mission.EvaluateMission(a_t.weight.WTO)
    rec["track_runtime"] = time.time() - t0
    hist = history_arrays(tank.history)
    rec["history"] = hist
    rec["history_summary"] = history_summary(tank, tank.history)
    t0 = time.time()
    hist_pp = postprocess.compute_tank_history(a_t)
    rec["postprocess_runtime"] = time.time() - t0
    rec["postprocess_max_dP"] = float(np.max(np.abs(np.array(hist_pp['P']) - np.array(hist['P']))))
    rec["postprocess_max_dm"] = float(np.max(np.abs(np.array(hist_pp['m_tot'])
                                                    - np.array(hist['m_tot']))))
    feed_steps = mission_feed(a_t)
    out["h2_t"] = rec

    print("FCB-T design ...", flush=True)
    a_f, dt_f = design(fuelcell_battery_config(tank=True))
    rec = {"weights": weights(a_f), "runtime": dt_f, "tank": tank_geometry(a_f.tank)}
    a_f.mission.track_tank = True
    a_f.mission.EvaluateMission(a_f.weight.WTO)
    hist_track = history_arrays(a_f.tank.history)
    rec["track_tank_history_length"] = len(hist_track['t'])
    hist_f = history_arrays(postprocess.compute_tank_history(a_f))
    rec["postprocess_max_dP"] = float(np.max(np.abs(np.array(hist_f['P'])
                                                    - np.array(hist_track['P']))))
    rec["history"] = hist_f
    rec["history_summary"] = history_summary(a_f.tank, hist_f)
    rec["MissionTime"] = float(a_f.mission.profile.MissionTime)
    rec["ground_h2"] = float(a_f.mission.E_ground / a_f.mission.ef)
    h2_margin = a_f.EnergyInput['H2 Fuel Margin']
    rec["h2_margin_mass"] = float(a_f.weight.WH2_Fuel - a_f.weight.WH2_Fuel / (1.0 + h2_margin))
    p12 = props["1.2"]
    Q_sl = a_f.tank.get_heat_leak(p12["T_sat"], get_isa_atmosphere(0.0)[0])
    rec["balance_draw_total_sea_level"] = float(1.3 * Q_sl / (p12["delta_h"] * p12["rho_star"])
                                                * a_f.tank.n_tanks)
    out["fcb_t"] = rec

    # ------------------------------------------------------------- full-design sweeps
    sweep = []
    for dmax in (1.6, 2.0, 2.4, 2.8, 3.2):
        print(f"  design Dmax = {dmax}", flush=True)
        cfg = hydrogen_config(tank=True)
        cfg.tank.max_diameter = dmax
        try:
            a, rt = design(cfg)
        except Exception as err:          # record a design that does not close
            sweep.append({"max_diameter": dmax, "error": f"{type(err).__name__}: {err}"})
            continue
        sweep.append({"max_diameter": dmax, "runtime": rt, "weights": weights(a),
                      "tank": tank_geometry(a.tank)})
    out["design_sweep_dmax"] = sweep

    sweep = []
    for p_max in (1.6, 2.5, 3.5):
        print(f"  design P_max = {p_max}", flush=True)
        key = add_database_variant(f"manual_pmax_{p_max}", max_p_bar=p_max)
        cfg = hydrogen_config(tank=True)
        cfg.tank.tank_model = key
        a, rt = design(cfg)
        sweep.append({"max_p_bar": p_max, "runtime": rt, "weights": weights(a),
                      "tank": tank_geometry(a.tank)})
    out["design_sweep_pmax"] = sweep

    sweep = []
    for gi in (0.25, 0.30, 0.35, 0.40, 0.45):
        print(f"  design GI = {gi}", flush=True)
        cfg = hydrogen_config()
        cfg.energy.h2_gravimetric_index = gi
        a, rt = design(cfg)
        sweep.append({"gi": gi, "runtime": rt, "weights": weights(a)})
    out["design_sweep_gi"] = sweep

    # ------------------------------------------------------------- stand-alone tank sizing
    ref_capacity = out["h2_t"]["tank"]["capacity_total"]
    capacities = [25, 50, 100, 150, 200, 250, 300, 350, 400, 450, 500, 600, 700, 800,
                  900, 1000, 1200, 1500]
    cap_split, cap_nosplit, cap_nocap = [], [], []
    for c in capacities:
        cap_split.append(safe_geometry(c))
        cap_nosplit.append(safe_geometry(c, allow_auto_split=False))
        cap_nocap.append(safe_geometry(c, max_tanks=None))
    out["capacity_sweep"] = {"capacity": capacities, "auto_split": cap_split,
                             "no_split": cap_nosplit, "auto_split_nocap": cap_nocap}

    diameters = [1.4, 1.6, 1.8, 2.0, 2.2, 2.4, 2.6, 2.8, 3.0, 3.2, 3.4]
    out["diameter_sweep"] = {
        "max_diameter": diameters,
        "auto_split": [safe_geometry(ref_capacity, max_diameter=d) for d in diameters],
        "no_split": [safe_geometry(ref_capacity, max_diameter=d, allow_auto_split=False)
                     for d in diameters],
        "auto_split_nocap": [safe_geometry(ref_capacity, max_diameter=d, max_tanks=None)
                             for d in diameters],
    }

    out["ntanks_sweep"] = {
        "number_of_tanks": [1, 2, 3, 4],
        "auto_split": [safe_geometry(ref_capacity, number_of_tanks=n) for n in (1, 2, 3, 4)],
        "no_split": [safe_geometry(ref_capacity, number_of_tanks=n, allow_auto_split=False)
                     for n in (1, 2, 3, 4)],
    }

    p_sweep = []
    for p_max in (1.6, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0):
        key = add_database_variant(f"manual_pmax_{p_max}", max_p_bar=p_max)
        p_sweep.append({"max_p_bar": p_max, **tank_geometry(make_tank(ref_capacity, tank_model=key))})
    out["pmax_tank_sweep"] = p_sweep

    # ------------------------------------------------------------- heat leak
    ref_tank = make_tank(ref_capacity)
    T_c = props["1.2"]["T_sat"]
    N = ref_tank.n_layers_mli
    altitudes = list(np.linspace(0.0, 11000.0, 12))
    leak_alt = []
    for alt in altitudes:
        T_h, _ = get_isa_atmosphere(alt)
        # The three terms of the modified Lockheed equation, as in LH2_Tank.get_heat_leak.
        q_cond = ref_tank.C1 * ref_tank.Nt ** ref_tank.C2 * (T_h + T_c) * (T_h - T_c) / (2 * (N + 1))
        q_rad = ref_tank.C3 * ref_tank.eps * (T_h ** 4.67 - T_c ** 4.67) / N
        q_gas = ref_tank.Cg * (ref_tank.p_mli / N) * (T_h ** ref_tank.ng - T_c ** ref_tank.ng)
        Q = ref_tank.get_heat_leak(T_c, T_h)
        assert abs(Q - (q_cond + q_rad + q_gas) * ref_tank.area_inner_tot) < 1e-9 * Q
        leak_alt.append({"altitude": float(alt), "T_amb": float(T_h), "q_cond": float(q_cond),
                         "q_rad": float(q_rad), "q_gas": float(q_gas),
                         "Q_per_tank": float(Q), "Q_total": float(Q * ref_tank.n_tanks)})
    out["heat_leak_altitude"] = leak_alt

    leak_layers = []
    T_h, _ = get_isa_atmosphere(0.0)
    for n_layers in (5, 9, 15, 20, 30, 40, 60):
        key = add_database_variant(f"manual_mli_{n_layers}", n_layers_mli=n_layers)
        t_var = make_tank(ref_capacity, tank_model=key)
        leak_layers.append({"n_layers": n_layers,
                            "Q_total": float(t_var.get_heat_leak(T_c, T_h) * t_var.n_tanks),
                            "flux": float(t_var.get_heat_leak(T_c, T_h) / t_var.area_inner_tot),
                            "mass_insulation_total": float(t_var.mass_insulation * t_var.n_tanks),
                            "mass_system_empty": float(t_var.mass_system_empty)})
    out["heat_leak_layers"] = leak_layers

    # ------------------------------------------------------------- transient: parked tank
    parked = {}
    for label, alt in (("sea_level", 0.0), ("altitude_8000", 8000.0)):
        t_p = make_tank(ref_capacity)
        for _ in range(int(24 * 3600 / 30)):
            t_p.time_step(30.0, 0.0, alt)
        h = t_p.history
        vent = np.array(h['Vent'])
        rec = history_summary(t_p, h)
        rec["vent_steady"] = float(vent[-1])
        rec["boiloff_percent_per_day"] = float(h['m_vent_cum'][-1] / ref_capacity * 100.0)
        rec["t"] = [float(x) for x in h['t'][::10]]
        rec["P"] = [float(x) for x in h['P'][::10]]
        rec["m_vent_cum"] = [float(x) for x in h['m_vent_cum'][::10]]
        parked[label] = rec
    # Time-step sensitivity of the parked tank at sea level: time to reach P_max.
    dt_study = []
    for dt in (1.0, 10.0, 30.0, 60.0, 120.0):
        t_p = make_tank(ref_capacity)
        steps = int(6 * 3600 / dt)
        for _ in range(steps):
            t_p.time_step(dt, 0.0, 0.0)
        s = history_summary(t_p, t_p.history)
        dt_study.append({"dt": dt, "t_first_Pmax": s["t_first_Pmax"],
                         "m_vented_6h": s["m_vented"]})
    parked["dt_study"] = dt_study
    out["parked"] = parked

    # ------------------------------------------------------------- transient: heavy draw (heater)
    t_h = make_tank(ref_capacity)
    for _ in range(120):
        t_h.time_step(5.0, 0.5, 0.0)
    rec = history_summary(t_h, t_h.history)
    rec["Q_heater"] = [float(x) for x in t_h.history['Q_heater']]
    rec["t"] = [float(x) for x in t_h.history['t']]
    rec["P"] = [float(x) for x in t_h.history['P']]
    rec["Q_in"] = [float(x) for x in t_h.history['Q_in']]
    out["heavy_draw"] = rec
    # Draw rate at which the pressure stops rising at the start of the mission (sea level),
    # i.e. 1.3 Q = delta_h rho_star mdot_l, per tank.
    Q_sl = ref_tank.get_heat_leak(T_c, get_isa_atmosphere(0.0)[0])
    p12 = props["1.2"]
    out["balance_draw_total_sea_level"] = float(1.3 * Q_sl / (p12["delta_h"] * p12["rho_star"])
                                                * ref_tank.n_tanks)

    # ------------------------------------------------------------- transient: mission replay
    replays = {}
    t_base = make_tank(ref_capacity)
    base = replay(t_base, feed_steps)
    replays["reference"] = history_summary(t_base, base)
    for k in (2, 5):
        t_sub = make_tank(ref_capacity)
        h = replay(t_sub, feed_steps, substeps=k)
        replays[f"substeps_{k}"] = history_summary(t_sub, h)
    for p_max in (2.0, 3.0):
        key = add_database_variant(f"manual_pmax_{p_max}", max_p_bar=p_max)
        t_var = make_tank(ref_capacity, tank_model=key)
        h = replay(t_var, feed_steps)
        replays[f"pmax_{p_max}"] = history_summary(t_var, h) | {
            "mass_system_empty": float(t_var.mass_system_empty),
            "P": [float(x) for x in h['P']], "t": [float(x) for x in h['t']],
            "m_vent_cum": [float(x) for x in h['m_vent_cum']]}
    for n_layers in (20, 40):
        key = f"manual_mli_{n_layers}"
        t_var = make_tank(ref_capacity, tank_model=key)
        h = replay(t_var, feed_steps)
        replays[f"mli_{n_layers}"] = history_summary(t_var, h) | {
            "mass_system_empty": float(t_var.mass_system_empty),
            "P": [float(x) for x in h['P']], "t": [float(x) for x in h['t']],
            "m_vent_cum": [float(x) for x in h['m_vent_cum']]}
    replays["max_abs_dP_replay_vs_track"] = float(np.max(np.abs(
        np.array(base['P']) - np.array(out["h2_t"]["history"]['P']))))
    out["replay"] = replays

    out["total_runtime"] = time.time() - t_start
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "tank_data.json"), "w") as f:
        json.dump(out, f, indent=1)
    print(f"done in {out['total_runtime']:.0f} s")


if __name__ == "__main__":
    main()
