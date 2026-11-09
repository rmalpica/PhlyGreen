"""Engine-deck data and the coordinates at which the surrogates are read.

- The turboshaft map (data/GT_Universal_Map.csv) holds only converged deck points: every row
  delivered its target shaft power, including the static (Mach 0.01) column, which used to sit
  at the FAR initial guess.
- GasTurbineResponseSurface reads the map at its own coordinate (shaft power over
  P_des * delta(h)), clips to the training box with a warning and warns on its 0.30 fallback.
- The PW127 combustor states and the turbofan emission map carry no unconverged deck or CRN
  states (FAR at the 0.017 guess; CO outliers from a frozen secondary zone).
- ClimateImpact queries the PW127 emission map at the gas-turbine shaft power over
  engineRating * delta(h) (the map's coordinate), adds the ground segments for both NOx models,
  reads the engine count from the powertrain and defaults MissionType to 'Continue'.
"""
import os
import sys
import warnings

import numpy as np
import pandas as pd
import pytest

import PhlyGreen as pg
import PhlyGreen.Utilities.Atmosphere as ISA
from PhlyGreen.ClimateImpact.ClimateImpact import ClimateImpact
from PhlyGreen.config import ClimateImpactConfig
from PhlyGreen.Systems.Powertrain import gas_turbine_surrogate as gts

PT_DIR = os.path.dirname(gts.__file__)
DATA = os.path.join(PT_DIR, "data")
PIPELINE = os.path.join(PT_DIR, "emissions_pipeline")

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "examples"))
from common import traditional_config, hybrid_config  # noqa: E402


def _isa_delta(alt_m):
    """ISA pressure ratio from PhlyGreen's atmosphere (independent of the surrogate's formula)."""
    return ISA.atmosphere.Pstd(alt_m) / ISA.atmosphere.Pstd(0.0)


# ---------------------------------------------------------------------------------------
# Turboshaft map and surrogate
# ---------------------------------------------------------------------------------------
def test_turboshaft_map_every_point_delivered_its_power():
    df = pd.read_csv(os.path.join(DATA, "GT_Universal_Map.csv"))
    assert len(df) == 80                                    # 4 altitudes x 4 Mach x 5 fractions
    assert {"Target_hp", "Delivered_hp"}.issubset(df.columns)
    err = (df["Delivered_hp"] - df["Target_hp"]).abs() / df["Target_hp"]
    assert err.max() < 1e-3
    # target = fraction x reference power x ISA pressure ratio (the map's coordinate)
    delta = np.array([gts._isa_pressure_ratio(a) for a in df["Altitude_ft"]])
    np.testing.assert_allclose(df["Target_hp"], df["Power"] * gts.REF_HP * delta, rtol=1e-12)


def test_turboshaft_map_static_column_is_not_the_far_guess_line():
    """The unconverged static column had eta / PC = 0.367462 at every point (constant fuel)."""
    df = pd.read_csv(os.path.join(DATA, "GT_Universal_Map.csv"))
    static = df[df["Mach"] < 0.05]
    assert len(static) == 20
    ratio = static["Efficiency"] / static["Power"]
    assert ratio.max() / ratio.min() > 2.0
    # part power is less efficient than full power, but not proportionally so
    for _, col in static.groupby("Altitude_ft"):
        col = col.sort_values("Power")
        assert np.all(np.diff(col["Efficiency"].to_numpy()) > 0)
        assert col["Efficiency"].iloc[0] > 0.25


def test_turboshaft_surrogate_is_read_at_the_map_coordinate():
    """At a training point, predict(design, alt, M, PC * design * delta) returns the map value
    (the RBF is an interpolant), so the fraction is formed over design * delta(h)."""
    df = pd.read_csv(os.path.join(DATA, "GT_Universal_Map.csv"))
    s = gts.GasTurbineResponseSurface()
    for i in (7, 33, 58, 77):
        r = df.iloc[i]
        req = r["Power"] * gts.REF_HP * gts._isa_pressure_ratio(r["Altitude_ft"])
        eta, _, p_avail, limited = s.predict(gts.REF_HP, r["Altitude_ft"], r["Mach"], req)
        assert eta == pytest.approx(r["Efficiency"], abs=1e-9)
        assert p_avail == pytest.approx(gts.REF_HP * gts._isa_pressure_ratio(r["Altitude_ft"]))
        assert not limited


def test_turboshaft_surrogate_clips_to_the_training_box_and_warns():
    s = gts.GasTurbineResponseSurface()
    lo_f, _ = s.input_ranges["power_fraction"]
    d = gts._isa_pressure_ratio(20000.0)
    eta_edge, _, _, _ = s.predict(gts.REF_HP, 20000.0, 0.4, lo_f * gts.REF_HP * d)
    with pytest.warns(RuntimeWarning, match="power_fraction"):
        eta_low, _, _, _ = s.predict(gts.REF_HP, 20000.0, 0.4, 0.1 * gts.REF_HP * d)
    assert eta_low == pytest.approx(eta_edge, abs=1e-12)      # below 0.3 -> the 0.3 value
    eta_top, _, _, _ = s.predict(gts.REF_HP, 30000.0, 0.4, 0.7 * gts.REF_HP
                                 * gts._isa_pressure_ratio(30000.0))
    with pytest.warns(RuntimeWarning, match="altitude_ft"):
        eta_high, _, _, _ = s.predict(gts.REF_HP, 36000.0, 0.4, 0.7 * gts.REF_HP
                                      * gts._isa_pressure_ratio(36000.0))
    assert eta_high == pytest.approx(eta_top, abs=1e-12)
    # warned once per coordinate and instance
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        s.predict(gts.REF_HP, 20000.0, 0.4, 0.05 * gts.REF_HP * d)


def test_turboshaft_surrogate_fallback_warns():
    s = gts.GasTurbineResponseSurface()
    with pytest.warns(RuntimeWarning, match="fallback efficiency 0.30"):
        eta, _, _, _ = s.predict(0.0, 10000.0, 0.3, 1000.0)
    assert eta == 0.30
    with pytest.warns(RuntimeWarning, match="fallback efficiency 0.30"):
        eta, _, _, _ = s.predict(gts.REF_HP, 10000.0, float("nan"), 1000.0)
    assert eta == 0.30


# ---------------------------------------------------------------------------------------
# Emission-map data
# ---------------------------------------------------------------------------------------
def test_pw127_combustor_states_have_no_unconverged_point():
    df = pd.read_csv(os.path.join(PIPELINE, "pw127_crn_inputs_corrected.csv"))
    assert len(df) == 100
    assert not np.any(df["FAR"] == 0.017)                   # the deck's FAR initial guess
    # within every (altitude, Mach) column FAR, T3 and air flow rise with the power fraction
    for _, col in df.groupby(["alt_ft", "Mach"]):
        col = col.sort_values("PC")
        for c in ("FAR", "T3_K", "mdot_air3_kg_s"):
            assert np.all(np.diff(col[c].to_numpy()) > 0), c


def test_pw127_emission_map_low_power_sea_level_co_is_in_line():
    """The unconverged SL / M0.1 / 0.3 state gave CO 14.7 g/kg, three times its neighbours."""
    df = pd.read_csv(os.path.join(DATA, "PW127_Emission_Map.csv"))
    sl = df[df["alt_ft"] < 1.0]
    pt = sl[np.isclose(sl["Mach"], 0.10) & np.isclose(sl["PC"], 0.30)]["EICO"].iloc[0]
    nb = sl[np.isclose(sl["Mach"], 0.25) & np.isclose(sl["PC"], 0.30)]["EICO"].iloc[0]
    assert 0.67 < pt / nb < 1.5


def test_turbofan_emission_map_has_no_frozen_secondary_zone_outliers():
    """A frozen secondary zone gave CO 34-79 g/kg at 12 states (neighbours 1.4-10 g/kg)."""
    df = pd.read_csv(os.path.join(DATA, "Turbofan_Emission_Map.csv"))
    assert df[df["PC"] >= 0.8]["EICO"].max() < 10.0
    assert df["EICO"].max() < 20.0
    for _, col in df.groupby(["alt_ft", "Mach"]):
        co = col.sort_values("PC")["EICO"].to_numpy()
        assert np.all(co[1:] < 2.0 * co[:-1]), "CO jumps up with thrust within a column"


def test_turbofan_deck_is_on_one_cycle_branch():
    """At full throttle (T4 = T4_MAX) the available thrust falls with altitude at fixed Mach,
    and every thrust fraction of one flight condition shares the same full-throttle point.
    The previous map broke both: lapse 0.38 at 32,500 ft / M0.70 against 0.32 at 30,000 ft
    (T3 802 K), and PC 0.30 rows with a different lapse from the other fractions."""
    df = pd.read_csv(os.path.join(DATA, "Turbofan_Universal_Map.csv"))
    for (alt, mach), cond in df.groupby(["Altitude_ft", "Mach"]):
        assert cond["ThrustLapse"].max() - cond["ThrustLapse"].min() < 1e-6, (alt, mach)
    full = df.drop_duplicates(["Altitude_ft", "Mach"])
    for mach, col in full.groupby("Mach"):
        lapse = col.sort_values("Altitude_ft")["ThrustLapse"].to_numpy()
        assert np.all(np.diff(lapse) < 0), f"lapse does not fall with altitude at M {mach}"
    assert df["T3_K"].max() < 795.0          # inside the CRN calibration box (477-795 K)


@pytest.mark.slow
def test_crn_secondary_zone_is_not_declared_steady_before_reacting(monkeypatch):
    """The 10,000 ft / M0.6 / 0.8 state: CO 53.5 g/kg with the old integrator, ~2.5 now."""
    pytest.importorskip("cantera")
    crn_dir = os.path.join(PIPELINE, "crn")
    monkeypatch.chdir(crn_dir)
    monkeypatch.syspath_prepend(crn_dir)
    import evap_model_ottimizzato as evap
    params = {"label": "TEST", "power": 0.0, "T_in": 709.487794, "p_in_bar": 16.88350,
              "mdot_air": 28.714562, "FAR": 0.021941, "dPqP": 1.0 - 0.0540,
              "chi_mixer_scale": 1.0, "EIUHC_ICAO": 0.0}
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        r = evap.run_crn_evap_mode("GRID", params)
    assert r["EI_CO"] < 5.0
    assert r["EI_NOx"] > 15.0


# ---------------------------------------------------------------------------------------
# ClimateImpact: coordinates, ground segments, engine count, MissionType
# ---------------------------------------------------------------------------------------
class _RecordingSurrogate:
    """Stands in for EmissionSurrogate: records every query and returns constant indices."""
    inputs = ["alt_ft", "Mach", "PC"]
    outputs = ["EINOX", "EICO", "EIUHC"]
    tag = "recorder"
    EI = {"EINOX": 10.0, "EICO": 2.0, "EIUHC": 0.1}

    def __init__(self):
        self.calls = []

    def predict(self, X):
        X = np.atleast_2d(np.asarray(X, float))
        self.calls.append(X.copy())
        return {k: np.full(len(X), v) for k, v in self.EI.items()}


def _climate(model):
    return ClimateImpactConfig(H=100, N=1.6e7, Y=30, einox_model=model,
                               wtw_co2=8.30e-3, grid_co2=9.36e-2)


def _design(cfg, model):
    cfg.climate_impact = _climate(model)
    a = pg.build_aircraft()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a.configure(cfg)
    return a


def _walk(a, hybrid=False):
    """Flown points as ClimateImpact walks them: time, fuel flow, propulsive and shaft power."""
    m, pt = a.mission, a.powertrain
    t = np.concatenate([s.t for s in m.integral_solution])
    beta = np.concatenate([s.y[2] if hybrid else s.y[1] for s in m.integral_solution])
    alt, vel = m.profile.Altitude(t), m.profile.Velocity(t)
    ff, pp, shaft = [], [], []
    for i in range(len(t)):
        p = a.weight.WTO * a.performance.PoWTO(a.DesignWTOoS, beta[i], m.profile.PowerExcess(t[i]),
                                               1, alt[i], m.DISA, vel[i], 'TAS')
        r = (pt.Hybrid(m.profile.SuppliedPowerRatio(t[i]), alt[i], vel[i], p) if hybrid
             else pt.Traditional(alt[i], vel[i], p))
        ff.append(p * r[0] / a.weight.ef)
        pp.append(p)
        shaft.append(p * r[1])
    return t, alt, np.array(ff), np.array(pp), np.array(shaft)


@pytest.mark.slow
def test_turboprop_surrogate_is_queried_at_shaft_over_lapsed_rating_and_adds_ground():
    a = _design(traditional_config(), "Surrogate")
    assert a.MissionType == "Continue"                      # set by build_aircraft
    rec = _RecordingSurrogate()
    a.climateimpact.emission_surrogate = rec
    a.climateimpact.calculate_mission_emissions()
    flown_X, ground_X = rec.calls
    t, alt, ff, pp, shaft = _walk(a)
    assert len(flown_X) == len(t)

    expected = shaft / (a.powertrain.engineRating * np.array([_isa_delta(x) for x in alt]))
    np.testing.assert_allclose(flown_X[:, 2], expected, rtol=2e-3)
    # not the old coordinate (propulsive power over the sea-level rating)
    assert not np.allclose(flown_X[:, 2], pp / a.powertrain.engineRating, rtol=0.05)
    np.testing.assert_allclose(flown_X[:, 0], alt / 0.3048)

    # ground segments: taxi-out, take-off run, taxi-in at the Mission's fuel flows
    m = a.mission
    assert len(ground_X) == 3
    ground_fuel = a.climateimpact.ground_emissions["fuel"]
    assert ground_fuel == pytest.approx(m.E_ground / a.weight.ef, rel=1e-9)
    assert ground_fuel > 0.0
    flown_fuel = np.trapezoid(ff, t)
    e = a.climateimpact.mission_emissions
    assert e["nox"] == pytest.approx(10.0e-3 * (flown_fuel + ground_fuel), rel=1e-9)
    assert a.climateimpact.ground_emissions["nox"] == pytest.approx(10.0e-3 * ground_fuel)
    assert e["co"] == pytest.approx(2.0e-3 * (flown_fuel + ground_fuel), rel=1e-9)
    # flown + ground fuel is the fuel the CO2 is computed from
    assert flown_fuel + ground_fuel == pytest.approx(a.weight.Wf, rel=2e-3)
    # take-off run at full take-off power: shaft fraction near 1 at sea level, taxi at 7 % of it
    takeoff_fraction = ground_X[1, 2]
    assert ground_X[0, 2] == pytest.approx(m.taxi_power_fraction / m.takeoff_power_fraction
                                           * takeoff_fraction, rel=0.15)
    assert ground_X[0, 1] == 0.0 and ground_X[1, 1] > 0.0


@pytest.mark.slow
def test_hybrid_surrogate_fraction_excludes_the_battery_share():
    a = _design(hybrid_config(battery_class='I'), "Surrogate")
    rec = _RecordingSurrogate()
    a.climateimpact.emission_surrogate = rec
    a.climateimpact.calculate_mission_emissions()
    flown_X = rec.calls[0]
    t, alt, ff, pp, shaft = _walk(a, hybrid=True)
    phi = np.array([a.mission.profile.SuppliedPowerRatio(x) for x in t])
    assert phi.max() > 0.0
    delta = np.array([_isa_delta(x) for x in alt])
    np.testing.assert_allclose(flown_X[:, 2], shaft / (a.powertrain.engineRating * delta),
                               rtol=2e-3)
    # where the battery supplies power, the thermal shaft power is below the propulsive power
    on = phi > 0.05
    assert np.all(shaft[on] < pp[on])


@pytest.mark.slow
def test_filippone_adds_the_ground_segments():
    a = _design(traditional_config(), "Filippone")
    ci = a.climateimpact
    ci.calculate_mission_emissions()
    total = ci.mission_emissions["nox"]
    g = ci.ground_emissions
    assert g["fuel"] == pytest.approx(a.mission.E_ground / a.weight.ef, rel=1e-9)
    # recompute the ground NOx leg by leg with the correlation
    legs = ci._ground_legs()
    assert [leg["name"] for leg in legs] == ["Taxi-out", "Takeoff", "Taxi-in"]
    OPR, n = ci._opr(), ci._n_engines()
    nox = 0.0
    for leg in legs:
        c = ClimateImpact.FILIPPONE_COEFF[0 if leg["name"] == "Takeoff" else 1]
        mf = leg["fuel_flow"] / n
        ei = 2 * (c[0] + c[1] * OPR + c[2] * OPR ** 2 + c[3] * mf + c[4] * mf ** 2
                  + c[5] * OPR * mf)
        nox += ei * leg["fuel_flow"] * leg["duration"] * 1e-3
    assert g["nox"] == pytest.approx(nox, rel=1e-12)
    assert 0.0 < g["nox"] < 0.1 * total


class _Stub:
    pass


def test_engine_count_comes_from_the_powertrain():
    a = _Stub()
    a.powertrain = _Stub()
    ci = ClimateImpact(a)
    assert ci._n_engines() == 2                             # no attribute -> 2
    a.powertrain.n_engines = 4
    assert ci._n_engines() == 4
    a.PropellerInput = {'Number of Engines': 3}             # no longer read here
    assert ci._n_engines() == 4


def test_mission_type_defaults_to_continue():
    a = _Stub()
    ci = ClimateImpact(a)
    assert ci._mission_type() == 'Continue'
    a.MissionType = 'Discrete'
    assert ci._mission_type() == 'Discrete'
    assert pg.build_aircraft().MissionType == 'Continue'
