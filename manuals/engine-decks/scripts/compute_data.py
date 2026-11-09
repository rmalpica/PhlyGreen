"""Compute every number and every curve of the engine-deck manual.

Writes ../data/engine_decks_data.json. The figures (make_figures.py) and the numbers quoted in
engine_decks_manual.tex all come from this file, from gt_deck_check.json (check_gt_deck.py) and
from crn_check.json (check_crn.py).

Sections:

* ``gas_turbine``  -- the shipped turboshaft map, its RBF surrogate, a leave-one-out check of the
  RBF settings, the size-scaling exponent, the dry-mass correlation and the two power lapses;
* ``turbofan``     -- the shipped turbofan map, its five RBF surfaces, leave-one-out checks,
  maps of eta_o, TSFC and thrust lapse, and the Mattingly fallback lapse;
* ``propeller``    -- the Hamilton-Standard model on a fixed geometry, and the RBF propeller
  surrogate with its training residuals;
* ``emissions``    -- the two emission-index artifacts, their training residuals and leave-one-
  out checks, maps, the ICAO points written in the repository, and the Filippone correlation;
* ``designs``      -- aircraft designs: the turboprop with the constant and the Class-II gas
  turbine, a turboprop with the Hamilton propeller, the turbofan of examples/common.py, and
  their mission emissions with the Filippone and the surrogate NOx models.

The package and its artifacts are only read. The leave-one-out checks refit the RBFs in memory
with the settings of the training scripts; nothing is written back.

Runtime: about three minutes.

    cd trunk && python ../manuals/engine-decks/scripts/compute_data.py
"""

import contextlib
import io
import json
import os
import pickle
import sys
import time
import types
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
TRUNK = os.path.abspath(os.path.join(HERE, "..", "..", "..", "trunk"))
PT = os.path.join(TRUNK, "PhlyGreen", "Systems", "Powertrain")
DATA_DIR = os.path.join(PT, "data")
OUT = os.path.abspath(os.path.join(HERE, "..", "data", "engine_decks_data.json"))
sys.path.insert(0, os.path.join(TRUNK, "examples"))

import numpy as np                                                       # noqa: E402
import pandas as pd                                                      # noqa: E402
from scipy.interpolate import Rbf                                        # noqa: E402
from sklearn.preprocessing import StandardScaler                        # noqa: E402

import PhlyGreen as pg                                                   # noqa: E402
import PhlyGreen.Utilities.Atmosphere as ISA                             # noqa: E402
import PhlyGreen.Utilities.Units as Units                                # noqa: E402
import PhlyGreen.Utilities.Speed as Speed                                # noqa: E402
from PhlyGreen.config import ClimateImpactConfig, WellToTankConfig       # noqa: E402
from PhlyGreen.Systems.Powertrain import gas_turbine_surrogate as gts   # noqa: E402
from PhlyGreen.Systems.Powertrain.turbofan_surrogate import TurbofanResponseSurface  # noqa: E402
from PhlyGreen.Systems.Powertrain.emissions_surrogate import (           # noqa: E402
    EmissionSurrogate, default_model_path)
from PhlyGreen.Systems.Powertrain.propeller_hamilton import Propeller   # noqa: E402
from common import traditional_config, turbofan_config                  # noqa: E402

LHV_MAP = 43.0e6            # J/kg, used by both pyCycle decks
G0 = 9.80665
TSFC_TO_IMPERIAL = 3600.0 * G0   # kg/(N s) -> lb/(lbf h)


def flt(x):
    return float(x)


def stats(err):
    """Mean absolute, rms and max absolute of an error array."""
    err = np.asarray(err, float)
    return {"mae": flt(np.mean(np.abs(err))), "rms": flt(np.sqrt(np.mean(err ** 2))),
            "max": flt(np.max(np.abs(err)))}


# =============================================================================================
# Gas turbine (turboshaft)
# =============================================================================================
def gas_turbine():
    print("gas turbine ...")
    csv = pd.read_csv(os.path.join(DATA_DIR, "GT_Universal_Map.csv"))
    surf = gts.GasTurbineResponseSurface()
    out = {"n_points": len(csv),
           "altitudes_ft": sorted(csv.Altitude_ft.unique().tolist()),
           "machs": sorted(csv.Mach.unique().tolist()),
           "power_fractions": sorted(csv.Power.unique().tolist()),
           "eta_min": flt(csv.Efficiency.min()), "eta_max": flt(csv.Efficiency.max()),
           "ref_hp": surf.ref_hp, "scaling_n_stored": surf._n,
           "scaling_n_calibrated": gts.calibrate_scaling_exponent(),
           "rbf_function": "linear", "rbf_smooth": 0.0}

    # Convergence columns written by the generator, and the training box stored in the pickle.
    out["max_power_error"] = flt(((csv.Delivered_hp - csv.Target_hp).abs() / csv.Target_hp).max())
    out["input_ranges"] = {k: [flt(v[0]), flt(v[1])] for k, v in (surf.input_ranges or {}).items()}
    out["static_column"] = csv[csv.Mach == csv.Mach.min()][["Altitude_ft", "Power", "Efficiency"]] \
        .to_dict(orient="list")

    # Shipped surrogate at its own training points (an interpolant: error should be ~0).
    def surrogate_at(alt, mach, pc, design_hp=surf.ref_hp):
        delta = gts._isa_pressure_ratio(alt)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            eta, _, _, _ = surf.predict(design_hp, alt, mach, pc * design_hp * delta)
        return eta
    fit = np.array([surrogate_at(r.Altitude_ft, r.Mach, r.Power) for r in csv.itertuples()])
    out["train_error"] = stats(fit - csv.Efficiency.values)

    # Leave-one-out with the trainer's settings (StandardScaler + linear Rbf, smooth 0).
    X = csv[["Altitude_ft", "Mach", "Power"]].values
    y = csv.Efficiency.values
    loo = np.zeros(len(y))
    for i in range(len(y)):
        keep = np.arange(len(y)) != i
        sc = StandardScaler().fit(X[keep])
        Xs = sc.transform(X[keep])
        rbf = Rbf(Xs[:, 0], Xs[:, 1], Xs[:, 2], y[keep], function="linear", smooth=0)
        xi = sc.transform(X[i:i + 1])[0]
        loo[i] = rbf(xi[0], xi[1], xi[2])
    flight = csv.Mach.values > 0
    out["loo_error_all"] = stats(loo - y)
    out["loo_error_flight"] = stats((loo - y)[flight])

    # Re-run of the deck (check_gt_deck.py).
    chk_path = os.path.join(os.path.dirname(OUT), "gt_deck_check.json")
    if os.path.exists(chk_path):
        chk = json.load(open(chk_path))
        out["deck_check"] = {k: chk[k] for k in ("design", "csv", "mach0_exact", "runtime_s")}
        out["deck_check"]["rerun"] = {k: v for k, v in chk["rerun"].items() if k != "points"}

    # Maps at the reference size.
    pcs = np.linspace(0.05, 1.0, 39)
    maps = {}
    for mach in (0.01, 0.2, 0.4, 0.6):
        for alt in (0.0, 10000.0, 20000.0, 30000.0):
            maps[f"{alt:.0f}_{mach:.2f}"] = [surrogate_at(alt, mach, p) for p in pcs]
    out["maps"] = {"pc": pcs.tolist(), "eta": maps}
    out["map_points"] = csv[["Altitude_ft", "Mach", "Power", "Efficiency"]].to_dict(orient="list")

    # Size scaling at a cruise-like point (20 000 ft, M 0.4, 70 % power).
    hp_grid = np.geomspace(300.0, 8000.0, 40)
    out["size_scaling"] = {"design_hp": hp_grid.tolist(),
                           "eta": [surrogate_at(20000.0, 0.4, 0.7, h) for h in hp_grid],
                           "eta_ref": surrogate_at(20000.0, 0.4, 0.7)}
    # The calibration data embedded in calibrate_scaling_exponent.
    data = np.array([[420, 0.650], [650, 0.592], [730, 0.580], [1000, 0.550], [1200, 0.540],
                     [1700, 0.480], [2500, 0.460], [4500, 0.430], [5500, 0.640]])
    eta_real = 2544.43 / (data[:, 1] * 18400.0)
    n = out["scaling_n_calibrated"]
    eta_model = 1.0 - (1.0 - eta_real[6]) * (2500.0 / data[:, 0]) ** n
    out["scaling_data"] = {"shp": data[:, 0].tolist(), "sfc": data[:, 1].tolist(),
                           "eta_real": eta_real.tolist(), "eta_model": eta_model.tolist()}

    # Dry-mass surrogate against its own correlation.
    hp = np.linspace(300.0, 8000.0, 60)
    w_rbf = [flt(surf.model_wt(surf.scaler_wt.transform([[h]])[0, 0])) for h in hp]
    w_phys = [surf.calculate_physics_weight(h) for h in hp]
    out["weight"] = {"hp": hp.tolist(), "rbf_lb": w_rbf, "phys_lb": w_phys,
                     "max_rel_diff": flt(np.max(np.abs(np.array(w_rbf) / np.array(w_phys) - 1))),
                     "W_2750_lb": surf.calculate_physics_weight(2750.0)}

    # Power lapses: the surrogate (ISA pressure ratio) and Powertrain.PowerLapse (rho^0.75).
    alts_m = np.linspace(0.0, 9144.0, 31)
    out["lapse"] = {"alt_m": alts_m.tolist(),
                    "delta": [gts._isa_pressure_ratio(Units.mToft(a)) for a in alts_m],
                    "rho075": [flt((ISA.atmosphere.RHOstd(a, 0.0) / ISA.atmosphere.RHOstd(0.0, 0.0))
                                   ** 0.75) for a in alts_m]}
    # Fraction below the training range: the runtime clips at 0.05, the map starts at 0.30.
    out["below_range"] = {"pc": [0.05, 0.1, 0.2, 0.3],
                          "eta": [surrogate_at(20000.0, 0.4, p) for p in (0.05, 0.1, 0.2, 0.3)]}
    return out


# =============================================================================================
# Turbofan
# =============================================================================================
def turbofan():
    print("turbofan ...")
    csv = pd.read_csv(os.path.join(DATA_DIR, "Turbofan_Universal_Map.csv"))
    s = TurbofanResponseSurface()
    out = {"n_points": len(csv), "ref_fn_N": s.ref_fn, "tag": s.tag, "ranges": s._ranges,
           "envelope": {f"{m:.2f}": sorted(csv[csv.Mach == m].Altitude_ft.unique().tolist())
                        for m in sorted(csv.Mach.unique())},
           "fractions": sorted(csv.ThrustFraction.unique().tolist()),
           "n_conditions": int(csv.groupby(["Altitude_ft", "Mach"]).ngroups)}
    per_condition = csv.groupby(["Altitude_ft", "Mach"]).ThrustFraction.apply(list)
    out["incomplete_conditions"] = [{"alt_ft": a, "Mach": m, "fractions": f}
                                    for (a, m), f in per_condition.items() if len(f) < 5]
    # KNOWN_UNCONVERGED of the deck, read from its source (importing it needs pyCycle).
    import ast
    src = open(os.path.join(DATA_DIR, "HBTF_turbofan.py")).read()
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "KNOWN_UNCONVERGED":
            out["known_unconverged"] = sorted(list(k) for k in ast.literal_eval(node.value))
    # Lapse along each Mach column (one value per condition): does it fall with altitude?
    lap_c = csv.drop_duplicates(["Altitude_ft", "Mach"]).sort_values(["Mach", "Altitude_ft"])
    mono = {}
    for m, grp in lap_c.groupby("Mach"):
        mono[f"{m:.2f}"] = bool(np.all(np.diff(grp.ThrustLapse.values) < 0))
    out["lapse_monotone_by_mach"] = mono
    # spread of the lapse column within one condition (should be zero: one full-throttle point)
    out["lapse_spread_within_condition"] = flt(csv.groupby(["Altitude_ft", "Mach"]).ThrustLapse
                                               .agg(lambda x: x.max() - x.min()).max())
    for col in ("Efficiency", "TSFC", "ThrustLapse", "BPR", "T3_K", "P3_Pa", "FAR",
                "mdot_air3", "mdot_inlet"):
        out[f"range_{col}"] = [flt(csv[col].min()), flt(csv[col].max())]

    # TSFC = V / (eta_o LHV) in the deck itself.
    v = np.array([Speed.Mach2TAS(m, Units.ftTom(a), 0.0) for a, m in zip(csv.Altitude_ft, csv.Mach)])
    tsfc_from_eta = v / (csv.Efficiency.values * LHV_MAP)
    out["tsfc_identity_rel"] = stats(tsfc_from_eta / csv.TSFC.values - 1.0)

    # Residuals of the shipped surfaces at the training points.
    Xs = s.scaler_eff.transform(csv[["Altitude_ft", "Mach", "ThrustFraction"]].values)
    eta_fit = s.model_eff(Xs[:, 0], Xs[:, 1], Xs[:, 2])
    tsfc_fit = s.model_tsfc(Xs[:, 0], Xs[:, 1], Xs[:, 2])
    bpr_fit = s.model_bpr(Xs[:, 0], Xs[:, 1], Xs[:, 2])
    out["train_eta"] = stats(eta_fit - csv.Efficiency.values)
    out["train_tsfc_rel"] = stats(tsfc_fit / csv.TSFC.values - 1.0)
    out["train_bpr"] = stats(bpr_fit - csv.BPR.values)
    lap = csv.drop_duplicates(["Altitude_ft", "Mach"])
    lap_fit = np.array([s.thrust_lapse(a, m) for a, m in zip(lap.Altitude_ft, lap.Mach)])
    out["train_lapse"] = stats(lap_fit - lap.ThrustLapse.values)

    # Leave-one-out for eta_o (multiquadric, smooth 1e-3) and the lapse (smooth 1e-4).
    X = csv[["Altitude_ft", "Mach", "ThrustFraction"]].values
    y = csv.Efficiency.values
    loo = np.zeros(len(y))
    for i in range(len(y)):
        keep = np.arange(len(y)) != i
        sc = StandardScaler().fit(X[keep])
        Z = sc.transform(X[keep])
        rbf = Rbf(Z[:, 0], Z[:, 1], Z[:, 2], y[keep], function="multiquadric", smooth=1e-3)
        z = sc.transform(X[i:i + 1])[0]
        loo[i] = rbf(z[0], z[1], z[2])
    out["loo_eta"] = stats(loo - y)
    out["loo_eta_rel"] = stats(loo / y - 1.0)
    XL = lap[["Altitude_ft", "Mach"]].values
    yl = lap.ThrustLapse.values
    lool = np.zeros(len(yl))
    for i in range(len(yl)):
        keep = np.arange(len(yl)) != i
        sc = StandardScaler().fit(XL[keep])
        Z = sc.transform(XL[keep])
        rbf = Rbf(Z[:, 0], Z[:, 1], yl[keep], function="multiquadric", smooth=1e-4)
        z = sc.transform(XL[i:i + 1])[0]
        lool[i] = rbf(z[0], z[1])
    out["loo_lapse"] = stats(lool - yl)

    # Maps.
    fr = np.linspace(0.3, 1.0, 29)
    conds = {"SL_M0.25": (0.0, 0.25), "10kft_M0.45": (10000.0, 0.45),
             "20kft_M0.60": (20000.0, 0.60), "30kft_M0.75": (30000.0, 0.75),
             "35kft_M0.78": (35000.0, 0.78)}
    eta_maps, tsfc_maps = {}, {}
    for key, (a, m) in conds.items():
        avail = s.ref_fn * s.thrust_lapse(a, m)
        e, t = [], []
        for f in fr:
            eta, tsfc, _, _ = s.predict(s.ref_fn, a, m, f * avail)
            e.append(eta)
            t.append(tsfc * TSFC_TO_IMPERIAL)
        eta_maps[key], tsfc_maps[key] = e, t
    out["maps"] = {"fraction": fr.tolist(), "eta": eta_maps, "tsfc_imperial": tsfc_maps}
    out["map_points"] = {k: {"alt_ft": a, "Mach": m} for k, (a, m) in conds.items()}

    machs = np.linspace(0.2, 0.85, 27)
    lapse_curves, mattingly = {}, {}
    for a in (0.0, 10000.0, 20000.0, 30000.0, 35000.0):
        lapse_curves[f"{a:.0f}"] = [s.thrust_lapse(a, m) for m in machs]
        delta = ISA.atmosphere.Pstd(Units.ftTom(a)) / ISA.atmosphere.Pstd(0.0)
        mattingly[f"{a:.0f}"] = [flt(delta * (1 - 0.49 * np.sqrt(m))) for m in machs]
    out["lapse_curves"] = {"mach": machs.tolist(), "map": lapse_curves, "mattingly": mattingly}
    out["lapse_training"] = {"alt_ft": lap.Altitude_ft.tolist(), "Mach": lap.Mach.tolist(),
                             "lapse": lap.ThrustLapse.tolist()}
    out["clip"] = {"lapse_39kft_M080": s.thrust_lapse(39000.0, 0.80),
                   "lapse_35kft_M080": s.thrust_lapse(35000.0, 0.80)}
    # Points quoted in example 26 (F00 240 kN): eta_o, TSFC and lapse.
    table = []
    for label, a, m, pc in [("take-off", 0., 0.25, 1.00), ("climb", 10000., 0.55, 0.90),
                            ("cruise", 35000., 0.78, 0.70), ("fast cruise", 35000., 0.85, 0.85),
                            ("descent", 20000., 0.60, 0.30)]:
        lapse = s.thrust_lapse(a, m)
        eta, tsfc, _, _ = s.predict(240e3, a, m, pc * 240e3 * lapse)
        table.append({"label": label, "alt_ft": a, "Mach": m, "fraction": pc, "eta": eta,
                      "tsfc_imperial": tsfc * TSFC_TO_IMPERIAL, "lapse": lapse})
    out["table"] = table
    return out


# =============================================================================================
# Propeller
# =============================================================================================
def hamilton_propeller(diameter_m, rpm, n_blades, activity_factor, cli, n_engines):
    """A Hamilton-Standard Propeller attached to a minimal stand-in for the aircraft."""
    fake = types.SimpleNamespace(
        PropellerInput={'Propeller Diameter': diameter_m, 'RPM': rpm, 'N_ENGINES': n_engines,
                        'N_BLADES': n_blades, 'ACTIVITY_FACTOR': activity_factor,
                        'INTEGRATED_LIFT_COEFFICIENT': cli},
        constraint=types.SimpleNamespace(DISA=0.0),
        powertrain=types.SimpleNamespace(n_engines=n_engines))
    prop = Propeller(fake)
    prop.SetInput()
    return prop


def propeller():
    print("propeller ...")
    out = {}
    # Geometry of examples/25_fuelcell_battery_class_ii_models.py.
    geo = {"diameter_m": Units.ftTom(13), "rpm": 13820 / 13, "n_blades": 6,
           "activity_factor": 167, "cli": 0.5, "n_engines": 2}
    prop = hamilton_propeller(**geo)
    out["geometry"] = geo
    out["V_tip_ft_s"] = prop.V_tip
    curves = {}
    vel = np.linspace(20.0, 200.0, 37)
    for alt in (0.0, 6000.0):
        for p_mw in (1.0, 2.0, 4.0):
            key = f"{alt:.0f}_{p_mw:.0f}"
            eta = []
            with contextlib.redirect_stdout(io.StringIO()):
                for v in vel:
                    eta.append(flt(prop.ComputePropEfficiency(alt, v, p_mw * 1e6)))
            curves[key] = eta
    J = (np.pi * Units.mToft(vel) / prop.V_tip).tolist()
    out["hamilton"] = {"V": vel.tolist(), "J": J, "eta": curves}
    # Power coefficient at sea level, 2 MW total (1 MW per engine), as computed in the code.
    hp_engine = Units.wTohp(2e6 / 2)
    out["cp_sl_2MW"] = flt(hp_engine * 10e10 / (2 * 6966) / 1.0 /
                           (prop.V_tip ** 3 * prop.diam_prop ** 2))
    # Tip Mach number at sea level and 6000 m.
    out["tip_mach"] = {f"{a:.0f}": flt(prop.V_tip / Units.mToft(ISA.atmosphere.astd(a)))
                       for a in (0.0, 6000.0)} if hasattr(ISA.atmosphere, "astd") else {}

    # RBF surrogate (it is fitted from the CSV when constructed).
    csv_path = os.path.join(DATA_DIR, "propeller_data_rbf.csv")
    df = pd.read_csv(csv_path)
    out["csv"] = {"n_rows": len(df), "n_zero_rpm": int((df.RPM == 0).sum()),
                  "altitudes_m": sorted(df.Altitude_m.unique().tolist()),
                  "speeds": sorted(df.Airspeed_m_s.unique().tolist()),
                  "powers_raw": sorted(df.EM_Power_kW.unique().tolist()),
                  "rpm_range_nonzero": [flt(df[df.RPM > 0].RPM.min()), flt(df.RPM.max())],
                  "pitch_range": [flt(df.Pitch.min()), flt(df.Pitch.max())],
                  "eta_max": flt(df.Efficiency.max())}
    from PhlyGreen.Systems.Powertrain.propeller_surrogate import PropellerSurrogate
    t0 = time.time()
    with contextlib.redirect_stdout(io.StringIO()):
        sur = PropellerSurrogate(csv_path)
    out["surrogate_build_s"] = time.time() - t0
    p_kw = np.where(df.EM_Power_kW.values > 10000, df.EM_Power_kW.values / 1000, df.EM_Power_kW.values)
    eta_fit = np.array([sur.get_efficiency(p, a, v, b, r) for p, a, v, b, r in
                        zip(p_kw, df.Altitude_m, df.Airspeed_m_s, df.Pitch, df.RPM)])
    good = df.RPM.values > 0
    out["surrogate_train"] = stats((eta_fit - df.Efficiency.values)[good])
    pitch_fit = np.array([sur.solve_pitch(p, a, v, r) for p, a, v, r in
                          zip(p_kw, df.Altitude_m, df.Airspeed_m_s, df.RPM)])
    out["surrogate_pitch_train_deg"] = stats((pitch_fit - df.Pitch.values)[good])
    # The CSV rows at one altitude and one power level of the grid (5556 m, 867 kW).
    a_near = min(out["csv"]["altitudes_m"], key=lambda a: abs(a - 5555.6))
    p_near = sorted(set(p_kw), key=lambda p: abs(p - 866.7))[0]
    sel = df[np.isclose(df.Altitude_m, a_near) & np.isclose(p_kw, p_near) & good]
    out["csv_slice"] = {"alt_m": a_near, "power_kw": flt(p_near), "V": sel.Airspeed_m_s.tolist(),
                        "eta": sel.Efficiency.tolist(), "rpm": sel.RPM.tolist(),
                        "pitch": sel.Pitch.tolist(),
                        "eta_fit": [sur.get_efficiency(p_near, a_near, v, b, r) for v, b, r in
                                    zip(sel.Airspeed_m_s, sel.Pitch, sel.RPM)]}
    # Efficiency through the runtime chain (pitch governor, then map) at the same condition,
    # for the two rpm values the data hold (1200 at low speed, 1000 at high speed).
    chain = {}
    for rpm in (1000.0, 1200.0):
        vals = []
        for v in vel:
            b = sur.solve_pitch(p_near, a_near, v, rpm)
            vals.append(sur.get_efficiency(p_near, a_near, v, b, rpm))
        chain[f"{rpm:.0f}"] = vals
    out["surrogate_chain"] = {"V": vel.tolist(), "eta": chain}
    # rpm histogram of the converged rows
    out["csv"]["n_rpm_near_1000"] = int(((df.RPM > 950) & (df.RPM < 1050)).sum())
    out["csv"]["n_rpm_near_1200"] = int(((df.RPM > 1150) & (df.RPM < 1250)).sum())
    return out


# =============================================================================================
# Emission indices
# =============================================================================================
def filippone_ei(mfuel_engine, opr, phase):
    """EINOx [g/kg] of the Filippone correlation as written in ClimateImpact.py."""
    coeff = {"climb": [0.7194e+1, 0.5609e+0, -0.1059e-1, -0.3223e+1, 0.2889e+0, 0.2591e+0],
             "cruise": [0.1605e+0, 0.2412e+0, -0.1650e-2, -0.8818e+1, 0.3714e+2, -0.2268e+0],
             "descent": [0.3699e+0, 0.5470e+0, -0.7445e-2, -0.6914e+1, 0.6782e+1, 0.1138e+0]}
    c = coeff[phase]
    m = mfuel_engine
    return 2 * (c[0] + c[1] * opr + c[2] * opr ** 2 + c[3] * m + c[4] * m ** 2 + c[5] * opr * m)


def emissions():
    print("emissions ...")
    out = {}
    files = {"PW127": ("PW127_Emission_Map.csv", default_model_path()),
             "Turbofan": ("Turbofan_Emission_Map.csv", default_model_path("Turbofan"))}
    for name, (csv_name, pkl) in files.items():
        df = pd.read_csv(os.path.join(DATA_DIR, csv_name))
        es = EmissionSurrogate(pkl)
        X = df[["alt_ft", "Mach", "PC"]].values
        pred = es.predict(X)
        d = {"n_points": len(df), "tag": es.tag, "ranges": es._ranges,
             "machs": sorted(df.Mach.unique().tolist()),
             "alts": sorted(df.alt_ft.unique().tolist()),
             "pcs": sorted(df.PC.unique().tolist())}
        for col in ("T3_K", "P3_Pa", "FAR", "mdot_air3_kg_s", "EINOX", "EICO", "EIUHC"):
            d[f"range_{col}"] = [flt(df[col].min()), flt(df[col].max())]
        d["far_equal_0p017"] = int(np.isclose(df.FAR, 0.017).sum())
        # CRN outputs that break the trend: CO above 10 g/kg at 80 % power or more.
        high = df[(df.PC >= 0.8) & (df.EICO > 10.0)]
        d["high_power_co_outliers"] = high[["alt_ft", "Mach", "PC", "T3_K", "FAR", "EINOX",
                                            "EICO", "EIUHC"]].to_dict(orient="records")
        d["n_high_power_rows"] = int((df.PC >= 0.8).sum())
        # the five largest NOx residuals of the shipped surrogate
        res = pd.DataFrame({"alt_ft": df.alt_ft, "Mach": df.Mach, "PC": df.PC,
                            "data": df.EINOX, "fit": pred["EINOX"]})
        res["abs"] = (res.fit - res.data).abs()
        d["worst_nox"] = res.sort_values("abs", ascending=False).head(5).to_dict(orient="records")
        for sp in ("EINOX", "EICO", "EIUHC"):
            y = df[sp].values
            d[f"train_{sp}"] = stats(pred[sp] - y)
            d[f"train_{sp}_rel"] = stats(pred[sp] / y - 1.0)
            # leave-one-out with the trainer's settings
            log = sp in ("EICO", "EIUHC")
            yt = np.log10(np.clip(y, 1e-9, None)) if log else y
            loo = np.zeros(len(y))
            for i in range(len(y)):
                keep = np.arange(len(y)) != i
                sc = StandardScaler().fit(X[keep])
                Z = sc.transform(X[keep])
                rbf = Rbf(*Z.T, yt[keep], function="multiquadric", smooth=0.1)
                z = sc.transform(X[i:i + 1])
                val = rbf(*z.T)[0]
                loo[i] = 10 ** val if log else val
            d[f"loo_{sp}_rel"] = stats(loo / y - 1.0)
            d[f"loo_{sp}"] = stats(loo - y)
        # maps vs fraction at several altitudes, mid Mach of each artifact
        pcs = np.linspace(0.3, 1.0, 29)
        mach_map = 0.4 if name == "PW127" else 0.6
        alts = (0.0, 10000.0, 20000.0, 30000.0) if name == "PW127" else \
            (0.0, 10000.0, 20000.0, 30000.0, 35000.0)
        maps = {}
        for a in alts:
            p = es.predict(np.column_stack([np.full_like(pcs, a), np.full_like(pcs, mach_map), pcs]))
            maps[f"{a:.0f}"] = {k: np.asarray(v).tolist() for k, v in p.items()}
        d["maps"] = {"pc": pcs.tolist(), "Mach": mach_map, "by_alt": maps}
        # sea-level training rows, for the certification comparison
        sl = df[df.alt_ft < 1.0]
        d["sl_rows"] = sl[["Mach", "PC", "EINOX", "EICO", "EIUHC", "T3_K", "FAR"]] \
            .to_dict(orient="list")
        out[name] = d

    # Certification points written in the repository.
    # PW127G (FOCA/EASA emission-factor DB), EMISSIONS_MODEL_NOTES.md section 3a; the NOx anchor
    # of build_pw127_surrogate.py uses PF 0.30/0.90/1.00 -> 10/16/19 g/kg.
    out["pw127_cert"] = {"modes": ["Taxi", "App", "Cl", "To"],
                         "PF_notes": [0.07, 0.30, 0.85, 1.00],
                         "PF_anchor": [None, 0.30, 0.90, 1.00],
                         "FF_kg_s": [0.04, 0.08, 0.14, 0.16],
                         "NOx": [5.0, 10.0, 16.0, 19.0], "CO": [20.0, 4.0, 2.0, 2.0],
                         "UHC": [0.0, 0.0, 0.0, 0.0]}
    # CFM56-7B27E ICAO LTO, build_turbofan_surrogate.py ICAO_CFM56 (from the CRN file).
    out["cfm56_icao"] = {"modes": ["Idle", "Approach", "Climb", "TakeOff"],
                         "PC": [0.07, 0.30, 0.85, 1.00], "NOx": [4.36, 9.09, 17.89, 23.94],
                         "CO": [29.39, 2.82, 0.17, 0.31], "UHC": [1.54, 0.05, 0.02, 0.03]}
    # Surrogate at sea level at the certification fractions, Mach-averaged over each grid.
    for name, pcs_cert in (("PW127", [0.30, 0.90, 1.00]), ("Turbofan", [0.30, 0.85, 1.00])):
        es = EmissionSurrogate(files[name][1])
        machs = out[name]["machs"]
        machs_sl = [m for m in machs if m <= (0.55 if name == "PW127" else 0.75)]
        res = {}
        for pc in pcs_cert:
            p = es.predict(np.array([[0.0, m, pc] for m in machs_sl]))
            res[f"{pc:.2f}"] = {k: flt(np.mean(v)) for k, v in p.items()}
        out[name]["sl_at_cert"] = res
        out[name]["sl_machs"] = machs_sl

    # Filippone EINOx vs single-engine fuel flow, OPR 15.77 (default) and 30 (turbofan input).
    mf = np.linspace(0.02, 1.2, 60)
    out["filippone"] = {"mfuel": mf.tolist(),
                        "curves": {f"{phase}_{opr}": [filippone_ei(m, opr, phase) for m in mf]
                                   for phase in ("climb", "cruise", "descent")
                                   for opr in (15.77, 30.0)}}
    return out


# =============================================================================================
# Designs
# =============================================================================================
def climate(einox_model):
    return ClimateImpactConfig(H=100, N=1.6e7, Y=30, einox_model=einox_model,
                               wtw_co2=8.30e-3, grid_co2=9.36e-2)


def well_to_tank():
    return WellToTankConfig(eta_charge=0.95, eta_grid=1., eta_extraction=1.,
                            eta_production=1., eta_transportation=0.25)


def design(cfg, propeller_input=None):
    a = pg.build_aircraft()
    if propeller_input is not None:
        a.PropellerInput = propeller_input
    t0 = time.time()
    with warnings.catch_warnings(record=True) as caught, \
            contextlib.redirect_stdout(io.StringIO()):
        warnings.simplefilter("always")
        a.configure(cfg)
    msgs = sorted(set(str(w.message) for w in caught))
    # every component-power non-convergence warning, not only the distinct ones
    a._n_component_power_warnings = sum("component powers" in str(w.message) for w in caught)
    return a, time.time() - t0, msgs


def mission_walk(a):
    """Time, altitude, TAS, Mach, propulsive power, fuel flow and component powers along the
    flown mission (the accepted integrator points, as ClimateImpact walks them). The component
    efficiencies are read at the power through their own component (Powertrain.eta)."""
    m, perf, pt = a.mission, a.performance, a.powertrain
    t = np.concatenate([s.t for s in m.integral_solution])
    beta = np.concatenate([s.y[1] for s in m.integral_solution])
    alt = m.profile.Altitude(t)
    vel = m.profile.Velocity(t)
    pp, ff, psh, ppr, eta_gt, eta_pp, unconverged = [], [], [], [], [], [], []
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for i in range(len(t)):
            p = a.weight.WTO * perf.PoWTO(a.DesignWTOoS, beta[i], m.profile.PowerExcess(t[i]), 1,
                                          alt[i], m.DISA, vel[i], 'TAS')
            n_before = len(caught)
            r = pt.Traditional(alt[i], vel[i], p)
            if any("component powers" in str(w.message) for w in caught[n_before:]):
                unconverged.append({"t": flt(t[i]), "alt": flt(alt[i]), "V": flt(vel[i]),
                                    "P_prop": flt(p), "P_prop_shaft": flt(p * r[2])})
            pp.append(flt(p))
            ff.append(flt(p * r[0] / a.weight.ef))
            psh.append(flt(p * r[1]))
            ppr.append(flt(p * r[2]))
            eta_gt.append(flt(pt.eta('gas_turbine', alt[i], vel[i], p * r[1])))
            eta_pp.append(flt(pt.eta('propeller', alt[i], vel[i], p * r[2])))
    T = np.array([ISA.atmosphere.Tstd(float(x)) for x in alt]) + m.DISA
    mach = vel / (20.0468 * np.sqrt(T))
    return {"t": t.tolist(), "alt": np.asarray(alt).tolist(), "V": np.asarray(vel).tolist(),
            "Mach": mach.tolist(), "P_prop": pp, "fuel_flow": ff, "P_shaft": psh,
            "P_prop_shaft": ppr, "eta_gt": eta_gt, "eta_pp": eta_pp,
            "unconverged_points": unconverged}


def summary(a, runtime, msgs):
    r = a.results()
    return {"WTO": a.weight.WTO, "Wf": a.weight.Wf, "WPT": a.weight.WPT,
            "DesignPW": a.DesignPW, "DesignWTOoS": a.DesignWTOoS,
            "engineRating": a.powertrain.engineRating, "engineRating_units": r.engineRating_units,
            "gt_design_power": a.powertrain.gt_design_power,
            "n_engines": a.powertrain.n_engines,
            "empty_weight": r.empty_weight, "runtime_s": runtime, "warnings": msgs,
            "n_component_power_warnings": getattr(a, "_n_component_power_warnings", None),
            "wing_area": a.WingSurface}


def ei_along_mission(a, walk):
    """EI of the configuration's artifact at the map coordinate, recomputed independently of
    ClimateImpact: shaft power over engineRating * delta(h) (turboprop), thrust over the lapsed
    available thrust (turbofan)."""
    es = EmissionSurrogate(default_model_path(a.Configuration))
    alt = np.array(walk["alt"])
    mach = np.array(walk["Mach"])
    rating = a.powertrain.engineRating
    if a.Configuration == 'Turbofan':
        thrust = np.array(walk["P_prop"]) / np.array(walk["V"])
        lapse = np.array([a.powertrain.ThrustLapse(alt[i], mach[i], 0.0) for i in range(len(alt))])
        frac = thrust / (rating * lapse)
    else:
        delta = np.array([gts._isa_pressure_ratio(Units.mToft(x)) for x in alt])
        frac = np.array(walk["P_shaft"]) / (rating * delta)
    ei = es.predict(np.column_stack([alt / 0.3048, mach, frac]))
    t = np.array(walk["t"])
    ff = np.array(walk["fuel_flow"])
    return {"fraction": frac.tolist(), "EI": {k: np.asarray(v).tolist() for k, v in ei.items()},
            "n_points": int(len(frac)), "n_above_1": int((frac > 1.0 + 1e-9).sum()),
            "n_below_0p3": int((frac < 0.3).sum()),
            "fraction_max": flt(frac.max()), "fraction_min": flt(frac.min()),
            "flown_mass_kg": {k: flt(np.trapezoid(np.asarray(v) * ff, t) * 1e-3)
                              for k, v in ei.items()}}


def filippone_along_mission(a, walk):
    """Recompute the Filippone EINOx with the phase logic of ClimateImpact (continuous mission)."""
    t = np.array(walk["t"])
    alt = np.array(walk["alt"])
    alt_cruise = a.MissionStages['Cruise']['input']['Altitude']
    alt_start_div = a.DiversionStages['Climb1']['input']['StartAltitude']
    alt_div_cruise = a.DiversionStages['Cruise']['input']['Altitude']
    bp = np.zeros(5)
    idx = np.where(alt == alt_cruise)[0]
    bp[0], bp[1] = t[idx[0]], t[idx[-1]]
    for i in np.where(alt == alt_start_div)[0]:
        if t[i] > bp[1]:
            bp[2] = t[i]
            break
    for i in np.where(alt == alt_div_cruise)[0]:
        if t[i] > bp[2]:
            bp[3] = t[i]
            break
    bp[4] = t[np.where(alt == alt_div_cruise)[0][-1]]
    opr = a.climateimpact._opr()
    n_eng = a.climateimpact._n_engines()
    ei, phases = [], []
    for ti, ff in zip(t, walk["fuel_flow"]):
        if ti <= bp[0] or (bp[2] <= ti <= bp[3]):
            phase = "climb"
        elif (bp[0] < ti < bp[1]) or (bp[3] < ti < bp[4]):
            phase = "cruise"
        else:
            phase = "descent"
        ei.append(filippone_ei(ff / n_eng, opr, phase))
        phases.append(phase)
    return {"EINOX": ei, "OPR": opr, "n_engines": n_eng, "phase": phases}


def ground_legs(a):
    """The ground legs ClimateImpact adds, with their load fraction on the emission map."""
    ci = a.climateimpact
    legs = ci._ground_legs()
    out = []
    for leg in legs:
        frac = ci._surrogate_load_fraction(np.array([leg['altitude']]),
                                           np.array([leg['mach_takeoff']]),
                                           np.array([leg['propulsive_power']]),
                                           np.array([leg['shaft_power']]),
                                           np.array([leg['velocity']]),
                                           a.powertrain.engineRating)[0]
        out.append({k: (flt(v) if not isinstance(v, str) else v) for k, v in leg.items()}
                   | {"fraction": flt(frac), "fuel_kg": flt(leg['fuel_flow'] * leg['duration'])})
    return out


def with_emissions(cfg_fn, model, propeller_input=None):
    """Design with a ClimateImpactConfig and compute the mission emissions."""
    cfg = cfg_fn()
    cfg.climate_impact = climate(model)
    cfg.well_to_tank = well_to_tank()
    a, rt, msgs = design(cfg, propeller_input)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a.climateimpact.calculate_mission_emissions()
    out = summary(a, rt, msgs)
    out["mission_type"] = getattr(a, "MissionType", None)
    out["emissions"] = {k: flt(v) for k, v in a.climateimpact.mission_emissions.items()}
    out["ground_emissions"] = {k: flt(v) for k, v in a.climateimpact.ground_emissions.items()}
    return a, out


def tp_class2_config():
    cfg = traditional_config()
    cfg.energy.eta_gas_turbine_model = 'ResponseSurface'
    return cfg


def designs():
    out = {}
    two_engines = {'Number of Engines': 2}
    # --- 1. turboprop, constant efficiencies, Filippone and Surrogate NOx ----------------
    print("designs: turboprop constant ...")
    for model in ("Filippone", "Surrogate"):
        a, d = with_emissions(traditional_config, model)
        key = f"tp_const_{model}"
        out[key] = d
        if model == "Surrogate":
            walk = mission_walk(a)
            out["tp_walk"] = walk
            out["tp_ei"] = ei_along_mission(a, walk)
            out["tp_filippone"] = filippone_along_mission(a, walk)
            out["tp_ground_legs"] = ground_legs(a)
            out["tp_flown_fuel"] = flt(np.trapezoid(walk["fuel_flow"], walk["t"]))
            out["tp_ground_fuel"] = flt(a.weight.Wf - out["tp_flown_fuel"])

    # --- 2. turboprop with the Class-II gas turbine ----------------------------------------
    print("designs: turboprop Class-II gas turbine ...")
    # 2a. nominal follows the sized rating (no explicit GT Design Power)
    for model in ("Filippone", "Surrogate"):
        a, d = with_emissions(tp_class2_config, model, two_engines)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            d["report"] = {k: (flt(v) if not isinstance(v, (str, bool)) else v) for k, v in
                           a.powertrain.report_class_ii_sizing()['gas turbine'].items()}
        out[f"tp_c2_{model}"] = d
        if model == "Surrogate":
            walk = mission_walk(a)
            out["tp_c2_walk"] = walk
            out["tp_c2_ei"] = ei_along_mission(a, walk)
            out["tp_c2_filippone"] = filippone_along_mission(a, walk)
            out["tp_c2_ground_legs"] = ground_legs(a)
            ff = np.array(walk["fuel_flow"])
            out["tp_c2_Surrogate"]["mean_eta_gt_fuel_weighted"] = flt(
                np.sum(np.array(walk["eta_gt"]) * ff) / np.sum(ff))
            out["tp_c2_Surrogate"]["eta_gt_range"] = [flt(min(walk["eta_gt"])),
                                                       flt(max(walk["eta_gt"]))]
    # engine count read by the powertrain without a PropellerInput
    a_default, rt_d, _ = design(tp_class2_config())
    out["tp_c2_no_propeller_input"] = {"n_engines": a_default.powertrain.n_engines,
                                       "WTO": a_default.weight.WTO}

    # 2b. example 16 workflow: explicit nominal from a Class-I pre-pass, then 1.05 x min_nominal
    pre, rt, _ = design(traditional_config(), two_engines)
    p_nom = pre.DesignPW * pre.weight.WTO
    cfg = tp_class2_config()
    cfg.energy.gt_design_power = p_nom
    a1, rt1, msgs1 = design(cfg, two_engines)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rep1 = a1.powertrain.report_class_ii_sizing()['gas turbine']
    cfg.energy.gt_design_power = 1.05 * rep1['min_nominal']
    a2, rt2, msgs2 = design(cfg, two_engines)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        rep2 = a2.powertrain.report_class_ii_sizing()['gas turbine']
    walk2 = mission_walk(a2)
    conv = lambda rep: {k: (flt(v) if not isinstance(v, (str, bool)) else v) for k, v in rep.items()}
    out["tp_class2"] = {
        "pre": summary(pre, rt, []), "nominal_first": p_nom,
        "first": summary(a1, rt1, msgs1), "report_first": conv(rep1),
        "second": summary(a2, rt2, msgs2), "report_second": conv(rep2),
        "report_second_warnings": sorted(set(str(w.message) for w in caught)),
        "walk": walk2,
        "mean_eta_gt_fuel_weighted": flt(np.sum(np.array(walk2["eta_gt"]) * np.array(walk2["fuel_flow"]))
                                         / np.sum(walk2["fuel_flow"]))}

    # --- 3. turboprop with the Hamilton propeller -----------------------------------------
    print("designs: turboprop Hamilton propeller ...")
    prop_input = {'Propeller Diameter': Units.ftTom(13), 'RPM': 13820 / 13, 'Number of Engines': 2,
                  'N_BLADES': 6, 'ACTIVITY_FACTOR': 167, 'INTEGRATED_LIFT_COEFFICIENT': 0.5}
    cfg = traditional_config()
    cfg.energy.eta_propulsive_model = 'Hamilton'
    try:
        a3, rt3, msgs3 = design(cfg, prop_input)
        walk3 = mission_walk(a3)
        out["tp_hamilton"] = summary(a3, rt3, msgs3)
        out["tp_hamilton"]["walk"] = walk3
        eta_pp = np.array(walk3["eta_pp"])
        ff3 = np.array(walk3["fuel_flow"])
        out["tp_hamilton"]["eta_pp_min"] = flt(eta_pp.min())
        out["tp_hamilton"]["eta_pp_max"] = flt(eta_pp.max())
        out["tp_hamilton"]["n_at_clip"] = int((eta_pp <= 0.4 + 1e-12).sum())
        out["tp_hamilton"]["n_points"] = int(len(eta_pp))
        out["tp_hamilton"]["eta_pp_fuel_weighted"] = flt(np.sum(eta_pp * ff3) / np.sum(ff3))
    except Exception as exc:          # recorded, reported in the manual
        out["tp_hamilton"] = {"error": f"{type(exc).__name__}: {exc}"}

    # --- 3b. turboprop with the RBF propeller surrogate (default 1200 rpm) -----------------
    print("designs: turboprop RBF propeller ...")
    cfg = traditional_config()
    cfg.energy.eta_propulsive_model = 'Surrogate'
    a4, rt4, msgs4 = design(cfg, two_engines)
    walk4 = mission_walk(a4)
    eta_pp = np.array(walk4["eta_pp"])
    ff4 = np.array(walk4["fuel_flow"])
    out["tp_rbf_prop"] = summary(a4, rt4, msgs4)
    out["tp_rbf_prop"].update({"eta_pp_min": flt(eta_pp.min()), "eta_pp_max": flt(eta_pp.max()),
                               "eta_pp_fuel_weighted": flt(np.sum(eta_pp * ff4) / np.sum(ff4)),
                               "walk": walk4})

    # --- 4. turbofan ----------------------------------------------------------------------
    print("designs: turbofan ...")
    for model in ("Filippone", "Surrogate"):
        a, d = with_emissions(turbofan_config, model)
        key = f"tf_{model}"
        out[key] = d
        if model == "Surrogate":
            r = a.results()
            rep = a.powertrain.report_turbofan_sizing(warn=False)
            out[key].update({"DesignTW": r.DesignTW, "mean_TSFC_imperial": r.mean_TSFC * TSFC_TO_IMPERIAL,
                             "sizing": {"case": rep["sizing_case"],
                                        "cases": {k: flt(v) for k, v in rep["cases"].items()},
                                        "nominal": rep["nominal"],
                                        "ratio": rep["nominal_ratio"]}})
            cruise = a.constraint.CruiseConstraints
            alt = cruise['Altitude']
            v = Speed.Mach2TAS(cruise['Speed'], alt, a.constraint.DISA)
            pw = a.performance.PoWTO(a.DesignWTOoS, cruise['Beta'], 0, 1., alt, a.constraint.DISA,
                                     cruise['Speed'], cruise['Speed Type'])
            thrust = flt(pw) * a.weight.WTO / v
            eta_c = a.powertrain.eta('gas_turbine', alt, v, thrust * v)
            out[key]["cruise"] = {"alt_m": alt, "Mach": cruise['Speed'], "V": v,
                                  "thrust_N": thrust, "eta_o": eta_c,
                                  "tsfc_imperial": v / (eta_c * a.weight.ef) * TSFC_TO_IMPERIAL}
            walk = mission_walk(a)
            out["tf_walk"] = walk
            out["tf_ei"] = ei_along_mission(a, walk)
            out["tf_filippone"] = filippone_along_mission(a, walk)
            out["tf_ground_legs"] = ground_legs(a)
            out["tf_flown_fuel"] = flt(np.trapezoid(walk["fuel_flow"], walk["t"]))
            out["tf_ground_fuel"] = flt(a.weight.Wf - out["tf_flown_fuel"])

    # --- 5. A320 validation points (validation/a320_reference.py) --------------------------
    print("designs: A320 validation points ...")
    sys.path.insert(0, os.path.join(TRUNK, "validation"))
    import a320_reference as val
    with contextlib.redirect_stdout(io.StringIO()), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        wall = val.landing_limited_wing_loading()
        ac_A = val._design()
        ac_B = val._design(wall)
        k_cal = val.calibrate_structure_to_oew(wall)
        ac_C = val._design(wall, structure_calibration=k_cal)
        ws_ref = val.REFERENCE["MTOW"][0] / val.REFERENCE["wing_area"][0]
        ac_E = val._design(ws_ref)
    out["a320"] = {"reference": {k: v[0] for k, v in val.REFERENCE.items() if k != "citation"},
                   "wall_kgm2": wall, "ws_ref_kgm2": ws_ref, "calibration": k_cal}
    for key, ac in (("A", ac_A), ("B", ac_B), ("C", ac_C), ("E", ac_E)):
        r = ac.results()
        out["a320"][key] = {"WTO": ac.weight.WTO, "OEW": r.empty_weight,
                            "S": ac.WingSurface, "thrust_kN": ac.powertrain.engineRating / 1e3,
                            "DesignTW": r.DesignTW, "WS_kgm2": ac.weight.WTO / ac.WingSurface,
                            "sizing_case": ac.powertrain.report_turbofan_sizing(warn=False)["sizing_case"]}
    return out


def summaries(data):
    """Derived numbers quoted in the text, computed from the sections above."""
    out = {}
    ds = data["designs"]
    for tag in ("tp", "tp_c2", "tf"):
        w, ei, fil = ds[f"{tag}_walk"], ds[f"{tag}_ei"], ds[f"{tag}_filippone"]
        t = np.array(w["t"])
        ff = np.array(w["fuel_flow"])
        phase = np.array(fil["phase"])
        flown = np.trapezoid(ff, t)
        d = {"flown_fuel": flt(flown)}
        for name, arr in (("filippone", fil["EINOX"]), ("surrogate", ei["EI"]["EINOX"])):
            arr = np.array(arr)
            d[f"mean_{name}"] = flt(np.trapezoid(arr * ff, t) / flown)
            for ph in ("climb", "cruise", "descent"):
                m = phase == ph
                d[f"{ph}_{name}"] = flt(np.sum(arr[m] * ff[m]) / np.sum(ff[m]))
        out[tag] = d
    # Emission sea-level CO of the turbofan data at fractions >= 0.8
    sl = data["emissions"]["Turbofan"]["sl_rows"]
    co = [c for c, p in zip(sl["EICO"], sl["PC"]) if p >= 0.8]
    out["tf_sl_co_high_power"] = [min(co), max(co)]
    # Size-scaling fit: largest deviation without the 5500 shp row
    sd = data["gas_turbine"]["scaling_data"]
    dev = np.abs(np.array(sd["eta_real"]) - np.array(sd["eta_model"]))
    out["scaling_max_dev_without_5500"] = flt(dev[:-1].max())
    # CRN re-run of the PW127 sea-level slice
    crn_path = os.path.join(os.path.dirname(OUT), "crn_check.json")
    if os.path.exists(crn_path):
        pw = json.load(open(crn_path))["pw127_sls"]
        raw = np.array([p["NOx"] for p in pw])
        anch = np.array([p["shipped_EINOX"] for p in pw])
        full = [p for p in pw if abs(p["PC"] - 1.0) < 1e-9]
        out["pw127_crn"] = {
            "raw_range": [flt(raw.min()), flt(raw.max())],
            "anchored_range": [flt(anch.min()), flt(anch.max())],
            "raw_full_range": [min(p["NOx"] for p in full), max(p["NOx"] for p in full)],
            "anchored_full_range": [min(p["shipped_EINOX"] for p in full),
                                    max(p["shipped_EINOX"] for p in full)],
            "full_power_ratio": flt(np.mean([p["NOx"] for p in full])
                                    / np.mean([p["shipped_EINOX"] for p in full])),
            "co_max_rel_diff": flt(max(abs(p["CO"] / p["shipped_EICO"] - 1) for p in pw)),
            "uhc_max_rel_diff": flt(max(abs(p["UHC"] / p["shipped_EIUHC"] - 1) for p in pw))}
    return out


def main():
    t0 = time.time()
    data = {}
    for name, fn in (("gas_turbine", gas_turbine), ("turbofan", turbofan),
                     ("propeller", propeller), ("emissions", emissions), ("designs", designs)):
        t = time.time()
        data[name] = fn()
        data[f"runtime_{name}_s"] = time.time() - t
    data["summaries"] = summaries(data)
    data["runtime_total_s"] = time.time() - t0
    with open(OUT, "w") as f:
        json.dump(data, f, indent=1, default=float)
    print(f"done in {data['runtime_total_s']:.0f} s -> {OUT}")


if __name__ == "__main__":
    main()
