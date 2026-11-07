"""Run the PhlyGreen designs behind the TMS manual and store the numbers in ../data/tms_data.json.

Every number quoted in the manual comes from this file. It sizes:

* the hydrogen fuel-cell aircraft of ``examples/common.py:hydrogen_config`` with the Class-I and
  the Class-II TMS (default TMS inputs), and with the Class-II TMS and an intake ram recovery
  of 0.9;
* the fuel-cell + battery aircraft of ``examples/common.py:fuelcell_battery_config`` (cruise
  phi 0.15) with the Class-I and the Class-II TMS;
* the take-off-assisted fuel-cell + battery design of
  ``examples/30_off_design_mission.py:fc_battery_design`` (Class-I TMS), flown with a degraded
  stack (50 mV cell-voltage loss).

It then post-processes these designs: heat history along the mission, heat split per mission
point, the check of the Class-II hardware along the mission (``CheckMission``) and its cost,
the frozen Class-II geometry rated over a grid of altitudes and speeds, and parameter
sweeps of ``ThermalManagementSystem.SizeForMission`` on a frozen heat profile.

Runtime: about 10 minutes (each Class-II design takes 1-1.5 min).
"""

import copy
import importlib.util
import json
import math
import os
import sys
import time
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
TRUNK = os.path.abspath(os.path.join(HERE, "..", "..", "..", "trunk"))
DATA = os.path.abspath(os.path.join(HERE, "..", "data"))
sys.path.insert(0, os.path.join(TRUNK, "examples"))

import numpy as np                                                   # noqa: E402
import PhlyGreen as pg                                               # noqa: E402
from PhlyGreen.Systems.Thermal.hex import SIZERS, DesignSpec, rate_design   # noqa: E402
from PhlyGreen.Systems.Thermal.ram_air import ram_air_drag          # noqa: E402
from common import hydrogen_config, fuelcell_battery_config         # noqa: E402

G = 9.81


def _f(x):
    """JSON-friendly float."""
    x = float(x)
    return None if (math.isnan(x) or math.isinf(x)) else x


def load_example_30():
    path = os.path.join(TRUNK, "examples", "30_off_design_mission.py")
    spec = importlib.util.spec_from_file_location("ex30", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------------------- designs
def design(cfg, label):
    a = pg.build_aircraft()
    t0 = time.time()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        a.configure(cfg)
    dt = time.time() - t0
    tms_warnings = [str(w.message) for w in caught if "TMS" in str(w.message)]
    print(f"  {label}: {dt:.1f} s, MTOW {a.weight.WTO:.0f} kg")
    return a, dt, tms_warnings


def summarize(a, runtime, tms_warnings):
    w, m, fc, tms = a.weight, a.mission, a.fuelcell, a.tms
    r = a.results()
    S = w.WTO * G / a.DesignWTOoS
    d = {
        "configuration": a.Configuration, "tms_class": tms.Class, "runtime_s": runtime,
        "tms_warnings": tms_warnings,
        "WTO": w.WTO, "WPT": w.WPT, "WH2": w.WH2_Fuel, "WTank": w.WTank,
        "WBat": getattr(w, "WBat", 0.0) or 0.0, "WStructure": w.WStructure,
        "W_TMS": w.WHeat_Exchanger, "wing_area": S, "WS": a.DesignWTOoS, "PW": a.DesignPW,
        "P_fc_rated": fc.P_fc_rated, "P_aux_tms": fc.P_aux_tms,
        "extra_Cd": a.aerodynamics.extra_Cd,
        "Q_TO": m.TO_FC_Thermal_Pwr, "Q_mission_peak": m.Max_FC_Thermal_Pwr,
        "Q_mission_peak_alt": float(m.Max_FC_Thermal_Pwr_alt),
        "Q_mission_peak_V": float(m.Max_FC_Thermal_Pwr_V),
        "hex_sp_h2": a.EnergyInput.get("HEX Specific Power H2", 5000.0),
        "T_op": fc.T_op, "x_vapour": fc.x_vapour, "stoich": fc.stoich,
        "P_cathode": fc.Target_Press, "comp_eta": fc.comp_eta,
        "thermal_profile": [{k: (_f(v) if k != "name" else v) for k, v in p.items()}
                            for p in m.thermal_profile],
        "results_tms_mass": r.tms_mass,
    }
    res = w.tms_result
    if res is not None:
        d["tms"] = {
            "design_point": res.design_point["name"],
            "design_Q_fc": res.design_point["Q_fc"],
            "design_alt": res.design_point["altitude"], "design_V": res.design_point["V_inf"],
            "mdot_coolant": res.mdot_coolant, "mdot_ram_air": res.mdot_ram_air,
            "capture_area": res.capture_area, "pump_power": res.pump_power,
            "pump_mass": res.pump_mass, "hex_mass": res.hex_mass, "hex_volume": res.hex_volume,
            "total_mass": res.total_mass, "ram_drag": res.ram_drag,
            "ram_drag_raw": res.ram_drag_raw, "heat_shortfall": res.heat_shortfall,
            "heat_balance": {k: _f(v) for k, v in res.heat_balance.items()},
            "units": [{"role": u.role, "family": u.design.family, "n": u.n_parallel,
                       "unit_mass": u.design.weight, "unit_volume": u.design.volume,
                       "mass": u.mass, "q": u.q, "A": u.design.A, "U": u.design.U,
                       "dP_hot": u.design.dP_hot, "dP_cold": u.design.dP_cold,
                       "v_cold": u.design.v_cold, "caps_exceeded": u.caps_exceeded,
                       "geometry": {k: (_f(v) if isinstance(v, (int, float)) else v)
                                    for k, v in u.design.geometry.items()},
                       "family_candidates": [{"family": c.family, "mass": c.weight,
                                              "volume": c.volume} for c in u.candidates]}
                      for u in res.units],
            "candidates": [{"point": c["point"], "mass": _f(c["mass"]),
                            "worst_shortfall": _f(c["worst_shortfall"]),
                            "worst_shortfall_at": c["worst_shortfall_at"],
                            "feasible": bool(c["feasible"])} for c in res.candidates],
        }
        # the chosen hardware rated at every point (capped and full capacity)
        rows = []
        for p in m.thermal_profile:
            q_rej, q_req = tms.RateAtPoint(res, p)
            q_cap, _ = tms.RateAtPoint(res, p, capped=False)
            rows.append({"name": p["name"], "q_req": q_req, "q_rej": q_rej, "q_cap": q_cap})
        d["tms"]["rating"] = rows
        d["tms"]["mission_check"] = check_summary(res, len(m.thermal_profile))
    return d


def check_summary(res, n_profile):
    """Summary of ``res.checks`` (ThermalManagementSystem.CheckMission, filled at the end of
    the design): the profile points and the continuous-mission points."""
    checks = res.checks
    known = [c for c in checks if c["q_required"] > 0 and not math.isnan(c["dP_coolant"])]
    air = [c for c in checks if c["dP_air_available"] > 0 and c["q_required"] > 0]
    coldest = min(checks, key=lambda c: c["T_wall_min"])
    worst_air = max(air, key=lambda c: c["dP_air"] / c["dP_air_available"])
    return {
        "n_profile": n_profile, "n_history": len(checks) - n_profile,
        "worst_shortfall": max(c["shortfall"] for c in checks),
        "worst_shortfall_history": max((c["shortfall"] for c in checks[n_profile:]), default=0.0),
        "dP_coolant_max": max(c["dP_coolant"] for c in known),
        "dP_coolant_available": checks[0]["dP_coolant_available"],
        "n_coolant_dp_unknown": sum(1 for c in checks
                                    if c["q_required"] > 0 and math.isnan(c["dP_coolant"])),
        "air_dp_ratio_max": worst_air["dP_air"] / worst_air["dP_air_available"],
        "air_dp_ratio_max_at": worst_air["name"],
        "n_choked": sum(1 for c in checks if c["choked"]),
        "drag_max": max(c["ram_drag"] for c in checks),
        "n_drag_over": sum(1 for c in checks if c["ram_drag"] > c["ram_drag_accounted"]),
        "drag_excess_max": max(c["ram_drag"] - c["ram_drag_accounted"] for c in checks),
        "T_wall_min": coldest["T_wall_min"], "T_wall_min_at": coldest["name"],
        "T_freeze": coldest["T_freeze"],
        "violations": res.violations(),
        "risks": res.risks(),
        "ram_drag_work": res.ram_drag_work,
        "ram_drag_work_accounted": res.ram_drag_work_accounted,
        "profile": [{"name": c["name"], "dP_air": c["dP_air"],
                     "dP_air_available": c["dP_air_available"], "ram_drag": c["ram_drag"],
                     "ram_drag_accounted": c["ram_drag_accounted"],
                     "mdot_ram_air": c["mdot_ram_air"], "T_wall_min": c["T_wall_min"],
                     "limits": c["limits"], "risks": c["risks"]} for c in checks[:n_profile]],
    }


def check_cost(a):
    """Wall-clock cost of the continuous-mission check on the converged design: one
    SizeForMission with and without the history, one CheckMission."""
    tms, m = a.tms, a.mission
    profile, history = m.thermal_profile, m.thermal_history
    t0 = time.time(); tms.SizeForMission(profile); t_profile = time.time() - t0
    t0 = time.time(); r = tms.SizeForMission(profile, history); t_history = time.time() - t0
    t0 = time.time(); tms.CheckMission(r, profile, history); t_check = time.time() - t0
    tms.result = a.weight.tms_result
    return {"n_history": len(history), "SizeForMission_profile_s": t_profile,
            "SizeForMission_history_s": t_history, "CheckMission_s": t_check}


def heat_split(a):
    """Heat split at every thermal-profile point (needs CoolProp, any TMS class)."""
    tms = a.tms
    rows = []
    for p in a.mission.thermal_profile:
        c = tms._conditions(p)
        rows.append({"name": p["name"], "Q_fc": p["Q_fc"], "q_reactant": c["q_reactant"],
                     "q_h2": c["q_h2_target"], "q_ram": c["Q_ext"] - c["q_h2_target"],
                     "T_amb": c["T_amb"], "V_inf": c["V_inf"],
                     "T0_ram": c["T_amb"] + c["V_inf"] ** 2 / (2 * 1005.0)})
    return rows


def heat_history(a):
    """Fuel-cell heat at every accepted solver point of the mission (the converged
    design is re-flown once with a recorder around Mission._track_fc_heat)."""
    m, fc = a.mission, a.fuelcell
    rec = []
    original = m._track_fc_heat

    def recorder(t, alt, vel):
        rec.append((float(t), float(fc.Q_thermal), float(alt), float(vel)))
        return original(t, alt, vel)

    m._track_fc_heat = recorder
    m.EvaluateMission(a.weight.WTO)
    del m._track_fc_heat                      # restore the bound method
    rec.sort()
    segs = [{"name": f"{s.phase}/{s.name}", "t0": s.start_time, "t1": s.end_time}
            for s in m.profile._segments]
    return {"t": [r[0] for r in rec], "Q": [r[1] for r in rec], "alt": [r[2] for r in rec],
            "V": [r[3] for r in rec], "segments": segs,
            "thermal_profile": [{k: (_f(v) if k != "name" else v) for k, v in p.items()}
                                for p in m.thermal_profile]}


def ram_sweep(a, eta_values, alts, speeds):
    """Frozen ram-air exchanger of a Class-II design at other (altitude, TAS): intake flow
    rho V A_capture, core velocity and pressure drop from the built geometry, heat held at the
    design ram-air duty (or the capacity, if lower). Drag from ram_air_drag."""
    tms, res = a.tms, a.weight.tms_result
    u2 = next(u for u in res.units if u.role == "coolant_to_ram_air")
    n = u2.n_parallel
    q2_design = res.heat_balance["HEX ram air"]
    q1_design = res.heat_balance["HEX H2"]
    S = a.weight.WTO * G / a.DesignWTOoS
    out = {"alts": alts, "speeds": speeds, "eta": eta_values, "q2_design": q2_design,
           "extra_Cd": a.aerodynamics.extra_Cd, "wing_area": S, "mdot": [], "q": [],
           "D": {str(e): [] for e in eta_values}, "D_cd": [], "v_core": [], "dP_core": []}
    for h in alts:
        row_m, row_q, row_cd, row_v, row_dp = [], [], [], [], []
        row_D = {str(e): [] for e in eta_values}
        for V in speeds:
            point = dict(res.design_point, altitude=h, V_inf=V, takeoff=False)
            cond = tms._conditions(point)
            mdot = res.capture_area * cond["rho_amb"] * V
            coolant = tms._coolant(cond["T_op"], res.mdot_coolant)
            T1 = cond["T_op"] - q1_design / coolant.C
            air = tms._ram_air(cond, mdot)
            hot, cold = coolant.with_inlet(T1).split(n), air.split(n)
            sizer = SIZERS[u2.design.family](DesignSpec(hot=hot, cold=cold, q_target=0.0))
            q_dyn = 0.5 * cond["rho_amb"] * V ** 2
            row_m.append(mdot)
            row_cd.append(a.aerodynamics.extra_Cd * q_dyn * S)
            try:
                r = sizer.compute_U(u2.design.geometry, hot, cold)
            except ValueError:
                row_q.append(None); row_v.append(None); row_dp.append(None)
                for e in eta_values:
                    row_D[str(e)].append(None)
                continue
            q = min(n * rate_design(u2.design, hot, cold), q2_design)
            row_q.append(q); row_v.append(r["v_cold"]); row_dp.append(r["dP_cold"])
            for e in eta_values:
                row_D[str(e)].append(ram_air_drag(q, mdot, cond["T_amb"], cond["P_amb"], V,
                                                  r["v_cold"], r["dP_cold"], eta_ram=e))
        out["mdot"].append(row_m); out["q"].append(row_q); out["D_cd"].append(row_cd)
        out["v_core"].append(row_v); out["dP_core"].append(row_dp)
        for e in eta_values:
            out["D"][str(e)].append(row_D[str(e)])
    return out


def frozen_profile_sweeps(a, sweeps):
    """SizeForMission on the frozen thermal profile of ``a`` with one TMS input changed."""
    tms = a.tms
    profile = a.mission.thermal_profile
    out = {}
    for attr, values in sweeps.items():
        default = getattr(tms, attr)
        rows = []
        for v in values:
            setattr(tms, attr, v)
            r = tms.SizeForMission(profile)
            by = {u.role: u for u in r.units}
            rows.append({"value": v, "total_mass": r.total_mass, "hex_mass": r.hex_mass,
                         "pump_mass": r.pump_mass, "pump_power": r.pump_power,
                         "mass_h2": by["coolant_to_h2"].mass if "coolant_to_h2" in by else 0.0,
                         "mass_ram": (by["coolant_to_ram_air"].mass
                                      if "coolant_to_ram_air" in by else 0.0),
                         "n_ram": (by["coolant_to_ram_air"].n_parallel
                                   if "coolant_to_ram_air" in by else 0),
                         "family_ram": (by["coolant_to_ram_air"].design.family
                                        if "coolant_to_ram_air" in by else None),
                         "mdot_ram_air": r.mdot_ram_air, "capture_area": r.capture_area,
                         "ram_drag_raw": r.ram_drag_raw, "design_point": r.design_point["name"],
                         "feasible": any(c["feasible"] for c in r.candidates),
                         "caps_exceeded": r.caps_exceeded})
            print(f"    {attr}={v}: {r.total_mass:.0f} kg at {r.design_point['name']}")
        setattr(tms, attr, default)
        out[attr] = {"default": default, "rows": rows}
    tms.result = None
    return out


def degraded_flight(ex30, sized, voltage_loss, range_nm):
    """Peak heat of the frozen design flown with a degraded stack at the design take-off mass,
    and the off-design check of example 30 at that state of health."""
    a = copy.deepcopy(sized)
    ex30._set_state_of_health(a, {"fc_voltage_loss": voltage_loss})
    a.fuelcell.reset_adequacy()
    a.mission.EvaluateMission(sized.weight.WTO)
    q_design = ex30._fc_design_heat(sized.mission)
    q_deg = ex30._fc_design_heat(a.mission)
    od = ex30.fly_off_design(sized, range_nm, state_of_health={"fc_voltage_loss": voltage_loss})
    return {"voltage_loss": voltage_loss, "range_nm": range_nm, "Q_design": q_design,
            "Q_degraded_same_WTO": q_deg, "Q_TO_design": sized.mission.TO_FC_Thermal_Pwr,
            "Q_TO_degraded": a.mission.TO_FC_Thermal_Pwr,
            "Q_peak_design": sized.mission.Max_FC_Thermal_Pwr,
            "Q_peak_degraded": a.mission.Max_FC_Thermal_Pwr,
            "off_design_violations": od.violations, "off_design_risks": od.risks, "off_design_wto": od.WTO
            }


def degraded_rating(sized, voltage_loss):
    """Rate the frozen Class-II hardware of ``sized`` with a degraded stack at every point."""
    a = copy.deepcopy(sized)
    a.fuelcell.set_state_of_health(voltage_loss=voltage_loss)
    a.fuelcell.reset_adequacy()
    a.mission.EvaluateMission(sized.weight.WTO)
    res = sized.weight.tms_result
    rows = []
    for p in a.mission.thermal_profile:
        q_rej, q_req = a.tms.RateAtPoint(res, p)
        rows.append({"name": p["name"], "Q_fc": p["Q_fc"], "q_req": q_req, "q_rej": q_rej})
    checks = a.tms.CheckMission(copy.deepcopy(res), a.mission.thermal_profile,
                                a.mission.thermal_history)
    coldest = min(checks, key=lambda c: c["T_wall_min"])
    return {"rows": rows, "T_wall_min": coldest["T_wall_min"], "T_wall_min_at": coldest["name"],
            "worst_shortfall": max(c["shortfall"] for c in checks),
            "worst_shortfall_at": max(checks, key=lambda c: c["shortfall"])["name"],
            "n_short": sum(1 for c in checks if "heat" in c["limits"]),
            "n_checks": len(checks)}


def main():
    os.makedirs(DATA, exist_ok=True)
    data = {}

    print("Designs:")
    cfg = hydrogen_config(tms_class="I")
    h2_I, t, wn = design(cfg, "hydrogen, Class I")
    data["h2_I"] = summarize(h2_I, t, wn)
    data["h2_I"]["heat_split"] = heat_split(h2_I)

    cfg = hydrogen_config(tms_class="II")
    h2_II, t, wn = design(cfg, "hydrogen, Class II")
    data["h2_II"] = summarize(h2_II, t, wn)
    data["h2_II"]["heat_split"] = heat_split(h2_II)
    data["h2_II"]["history"] = heat_history(h2_II)

    cfg = hydrogen_config(tms_class="II"); cfg.tms.ram_recovery = 0.9
    h2_II9, t, wn = design(cfg, "hydrogen, Class II, ram recovery 0.9")
    data["h2_II_eta09"] = summarize(h2_II9, t, wn)

    cfg = fuelcell_battery_config(tms_class="I")
    fcb_I, t, wn = design(cfg, "FC+battery, Class I")
    data["fcb_I"] = summarize(fcb_I, t, wn)

    cfg = fuelcell_battery_config(tms_class="II")
    fcb_II, t, wn = design(cfg, "FC+battery, Class II")
    data["fcb_II"] = summarize(fcb_II, t, wn)
    data["fcb_II"]["heat_split"] = heat_split(fcb_II)

    print("Frozen ram-air exchanger over altitude and speed ...")
    data["ram_sweep"] = ram_sweep(h2_II9, [1.0, 0.9, 0.8],
                                  [0.0, 2000.0, 4000.0, 6000.0, 8000.0],
                                  [float(v) for v in np.arange(60.0, 171.0, 5.0)])

    print("Frozen-profile sweeps (hydrogen, Class II):")
    data["sweeps_h2"] = frozen_profile_sweeps(h2_II, {
        "coolant_delta_T": [4.0, 6.0, 8.0, 10.0, 12.0, 15.0, 20.0],
        "ram_air_delta_T": [20.0, 30.0, 40.0, 50.0, 60.0, 70.0],
        "takeoff_overtemperature": [0.0, 5.0, 10.0, 15.0, 20.0],
        "stack_pressure_drop": [0.0, 1.0e5, 1.5e5, 1.8e5, 1.9e5, 1.95e5],
    })
    data["check_cost_h2"] = check_cost(h2_II)

    print("Example-30 FC+battery design (take-off battery, 800 m field):")
    ex30 = load_example_30()
    t0 = time.time()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fcb30 = ex30.fc_battery_design()
    data["fcb30"] = summarize(fcb30, time.time() - t0, [])
    data["fcb30"]["heat_split"] = heat_split(fcb30)
    print("  frozen-profile sweep of the take-off over-temperature:")
    data["sweeps_fcb30"] = frozen_profile_sweeps(fcb30, {
        "takeoff_overtemperature": [0.0, 5.0, 10.0, 15.0, 20.0]})
    data["degradation_fcb30"] = degraded_flight(ex30, fcb30, 0.05, 750.0)
    data["degradation_h2_II"] = degraded_rating(h2_II, 0.05)
    od = ex30.fly_off_design(h2_II, 750.0, state_of_health={"fc_voltage_loss": 0.05})
    data["offdesign_h2_II_degraded"] = {"violations": od.violations, "risks": od.risks, "WTO": od.WTO}
    od = ex30.fly_off_design(h2_II, 750.0)
    data["offdesign_h2_II_bol"] = {"violations": od.violations, "risks": od.risks, "WTO": od.WTO}
    od = ex30.fly_off_design(h2_II9, 750.0)
    data["offdesign_h2_II_eta09_bol"] = {"violations": od.violations, "risks": od.risks, "WTO": od.WTO}

    print("Humidity of the cathode inlet (hydrogen, Class I):")
    data["humidity"] = {}
    for key, kw in (("humidifier_rh1", {"fc_cathode_inlet_rh": 1.0}),
                    ("ambient_rh06", {"fc_ambient_relative_humidity": 0.6}),
                    ("ambient_rh1", {"fc_ambient_relative_humidity": 1.0})):
        cfg = hydrogen_config(tms_class="I")
        for k, v in kw.items():
            setattr(cfg.energy, k, v)
        a, t, wn = design(cfg, "hydrogen, Class I, " + key)
        data["humidity"][key] = summarize(a, t, wn)

    with open(os.path.join(DATA, "tms_data.json"), "w") as fh:
        json.dump(data, fh, indent=1, default=float)
    print("written", os.path.join(DATA, "tms_data.json"))


if __name__ == "__main__":
    main()
