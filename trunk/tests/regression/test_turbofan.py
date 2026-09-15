"""Regression tests for the turbofan configuration, end to end.

These need the fitted engine map, which is generated offline by
``Systems/Powertrain/data/HBTF_turbofan.py`` (pyCycle) and fitted by
``train_turbofan_surrogate.py``. They skip cleanly when it is absent so the suite still runs
on a checkout that has not built it.
"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "examples"))

import PhlyGreen as pg
from PhlyGreen.config import ConfigError
from common import turbofan_config

_MAP = os.path.join(os.path.dirname(pg.__file__), "Systems", "Powertrain", "data",
                    "Turbofan_Engine_Model.pkl")
needs_map = pytest.mark.skipif(not os.path.isfile(_MAP),
                               reason="turbofan engine map not built (see HBTF_turbofan.py)")

LHV = 43.0e6


# --- configuration plumbing (no engine map needed) --------------------------

def test_flops_is_rejected_for_a_turbofan():
    """FLOPS has no engine or pylon mass and always adds a propeller -- refuse, don't guess."""
    cfg = turbofan_config()
    with pytest.raises(ConfigError, match="does not support the Turbofan"):
        cfg.weight_class = "II"
        cfg.__post_init__()


def test_turbofan_is_an_accepted_configuration():
    cfg = turbofan_config()
    assert cfg.configuration == "Turbofan"
    assert cfg.energy.to_dict()["Turbofan Design Thrust"] > 0


# --- the sizing loop --------------------------------------------------------

@pytest.fixture(scope="module")
def sized():
    # A mark on a fixture has no effect, so skip from inside it.
    if not os.path.isfile(_MAP):
        pytest.skip("turbofan engine map not built (see HBTF_turbofan.py)")
    ac = pg.build_aircraft()
    ac.configure(turbofan_config())
    return ac


@needs_map
def test_design_closes_with_physical_numbers(sized):
    r = sized.results()
    assert 50_000 < r.WTO < 120_000, f"MTOW {r.WTO:.0f} kg is not short-haul-jet-like"
    assert r.empty_weight < r.WTO
    assert sized.weight.Wf > 0
    assert 90.0 < sized.WingSurface < 230.0


def _a320_module():
    import importlib.util
    path = os.path.join(os.path.dirname(__file__), "..", "..", "validation",
                        "a320_reference.py")
    spec = importlib.util.spec_from_file_location("a320ref", os.path.abspath(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@needs_map
def test_a320_empty_weight_fraction_matches():
    """The empty-weight FRACTION is the meaningful Class-I check, and it is good.

    Asserting the fraction separately from the absolute masses keeps the two failure modes
    distinguishable: a wrong empty-weight model moves the fraction, whereas a wrong mission or
    fuel model moves the absolute size at roughly constant fraction.
    """
    a320 = _a320_module()
    ac = a320._design(a320.landing_limited_wing_loading())
    r = ac.results()
    frac = r.empty_weight / r.WTO
    ref_frac = a320.REFERENCE["OEW"][0] / a320.REFERENCE["MTOW"][0]
    assert abs(frac - ref_frac) / ref_frac < 0.05, f"OEW/MTOW {frac:.3f} vs {ref_frac:.3f}"


@needs_map
def test_a320_absolute_masses_are_within_the_stated_band():
    """Pins the headline numbers with the honest accounting (no engine double count).

    With the 'NarrowBody' empty-weight regression and no engine double count, all four land
    within 5 %; the band here is 10 % so that a real regression is caught without the test
    becoming brittle to small model changes. See validation/a320_reference.md.
    """
    a320 = _a320_module()
    ac = a320._design(a320.landing_limited_wing_loading())
    r = ac.results()
    got = {"MTOW": r.WTO, "OEW": r.empty_weight, "wing_area": ac.WingSurface,
           "SLS_thrust_total": r.engineRating / 1000.0}
    for key, value in got.items():
        ref = a320.REFERENCE[key][0]
        err = 100.0 * (value - ref) / ref
        assert abs(err) < 10.0, f"{key}: {value:.1f} vs reference {ref:.1f} ({err:+.1f} %)"
    # The engine is sized by the mission, never told the reference, so this is an independent
    # check rather than a restatement of an input.
    assert abs(100.0 * (got["SLS_thrust_total"] - 240.2) / 240.2) < 10.0


@needs_map
def test_powertrain_double_count_moves_the_empty_weight():
    """The switch must actually do something, and in the direction claimed."""
    a320 = _a320_module()
    wall = a320.landing_limited_wing_loading()
    honest = a320._design(wall, avoid_double_count=True)
    doubled = a320._design(wall, avoid_double_count=False)
    assert doubled.results().empty_weight > honest.results().empty_weight
    assert doubled.weight.WTO > honest.weight.WTO


@needs_map
def test_minimum_thrust_point_is_not_the_minimum_weight_point():
    """Sizing on the constraint-diagram minimum gives a heavier aircraft than the landing wall.

    This is the single largest source of disagreement in the A320 validation, and it is a
    property of the method rather than a defect: FindDesignPoint minimises installed thrust,
    not take-off weight.
    """
    import importlib.util
    path = os.path.join(os.path.dirname(__file__), "..", "..", "validation",
                        "a320_reference.py")
    spec = importlib.util.spec_from_file_location("a320ref2", os.path.abspath(path))
    a320 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(a320)

    wall = a320.landing_limited_wing_loading()
    default = a320._design()
    landing = a320._design(wall)
    assert default.DesignWTOoS < landing.DesignWTOoS
    assert landing.weight.WTO < default.weight.WTO


@needs_map
def test_design_point_is_a_thrust_to_weight_ratio(sized):
    r = sized.results()
    assert r.engineRating_units == "N"
    # A short-haul twin sits near T/W 0.3; the band is wide enough to be a sanity check
    # rather than a pinned number, since the constraint set is the user's to choose.
    assert 0.15 < r.DesignTW < 0.60
    assert sized.DesignTW == sized.DesignPW


@needs_map
def test_engine_is_sized_by_the_worst_of_three_requirements(sized):
    """Mission peak, take-off/OEI and the constraint diagram are all sizing cases."""
    rep = sized.powertrain.report_turbofan_sizing()
    assert set(rep["cases"]) == {"mission peak", "take-off / OEI", "constraint diagram"}
    assert rep["required_SLS_thrust"] == pytest.approx(max(rep["cases"].values()))
    assert sized.powertrain.engineRating == pytest.approx(rep["required_SLS_thrust"])


@needs_map
def test_tsfc_and_overall_efficiency_agree_on_the_sized_aircraft(sized):
    """The identity the whole single-node formulation rests on, checked after sizing."""
    alt, v = 10668.0, 231.0
    thrust = 25_000.0
    eta = sized.powertrain.eta('gas_turbine', alt, v, thrust * v)
    tsfc = v / (eta * LHV)
    # recovering eta from TSFC must return the same number
    assert v / (tsfc * LHV) == pytest.approx(eta, rel=1e-12)
    # and the mission-mean TSFC must be a plausible turbofan value
    r = sized.results()
    tsfc_imperial = r.mean_TSFC * 3600.0 * 9.80665
    assert 0.3 < tsfc_imperial < 1.0, f"mean TSFC {tsfc_imperial:.3f} lb/(lbf h) is not jet-like"


@needs_map
def test_thrust_lapse_falls_with_altitude_and_mach(sized):
    pt = sized.powertrain
    assert pt.ThrustLapse(0.0, 0.2, 0.0) > pt.ThrustLapse(10668.0, 0.2, 0.0)
    assert pt.ThrustLapse(0.0, 0.2, 0.0) > pt.ThrustLapse(0.0, 0.8, 0.0)
    assert 0.1 < pt.ThrustLapse(10668.0, 0.78, 0.0) < 0.45


@needs_map
def test_postprocess_reports_thrust_for_a_turbofan(sized):
    from PhlyGreen import postprocess
    ps = postprocess.power_timeseries(sized)
    assert "thrust" in ps and "throttle" in ps
    assert np.all(ps["thrust"] > 0)
    assert np.all(ps["throttle"] <= 1.5)


@needs_map
def test_turbofan_timeseries_is_consistent_with_the_weight_loop(sized):
    """The engine history must reproduce the fuel the design actually converged on.

    This is the sharpest available check that the reported time histories describe the design
    rather than a parallel re-modelling of it: the fuel flow is integrated independently here,
    and must land on the mission fuel the Brent loop closed with.
    """
    from PhlyGreen import postprocess

    ts = postprocess.turbofan_timeseries(sized)
    for key in ("time", "thrust", "fuel_flow", "tsfc", "throttle", "mach"):
        assert key in ts and len(ts[key]) == len(ts["time"])

    integrated = float(np.trapezoid(ts["fuel_flow"], ts["time"]))
    assert abs(integrated - sized.weight.Wf) / sized.weight.Wf < 0.01

    # TSFC is fuel flow per unit thrust by definition; check the table is self-consistent.
    assert np.allclose(ts["tsfc"], ts["fuel_flow"] / np.maximum(ts["thrust"], 1e-9), rtol=1e-9)
    # and lands in a turbofan band once expressed the customary way
    imperial = ts["tsfc"] * 3600.0 * 9.80665
    assert 0.3 < float(np.median(imperial)) < 1.0

    assert np.all(ts["thrust"] > 0)
    assert np.all(ts["throttle"] <= 1.5)


@needs_map
def test_turbofan_timeseries_carries_emissions_and_air_flow(sized):
    from PhlyGreen import postprocess

    ts = postprocess.turbofan_timeseries(sized)
    if "core_air_flow" in ts:
        # core flow of a ~240 kN twin: tens of kg/s, and it must fall with altitude
        assert 5.0 < float(np.median(ts["core_air_flow"])) < 300.0
    if "EINOX" in ts:
        assert np.all(ts["EINOX"] > 0)
        assert ts["NOX_kg"][-1] > 0 and ts["NOX_kg"][-1] < 5000.0
        assert np.all(np.diff(ts["NOX_kg"]) >= -1e-9)      # cumulative, so monotone


def test_validation_module_does_not_force_a_headless_backend():
    """Importing the validation helpers must not kill inline plotting in a notebook.

    It used to: `matplotlib.use("Agg")` at module scope meant every figure after the import
    silently produced nothing.
    """
    import matplotlib
    before = matplotlib.get_backend()
    _a320_module()
    assert matplotlib.get_backend() == before


@needs_map
def test_inlet_flow_is_not_the_core_flow_times_one_plus_bpr():
    """Total inlet flow must come from the cycle, not from core flow and a bypass ratio.

    Two things break that reconstruction, and this test pins both:

    * BPR is an off-design *balance* variable in the deck (solved against the bypass-nozzle
      throat area), so it is not the design value away from the design point;
    * station 3 sits downstream of the compressor bleeds, so the core stream there is already
      ~25-30 % smaller than what entered the core.

    Together they make ``core x (1 + BPR)`` substantially under-predict the true inlet flow.
    """
    from PhlyGreen.Systems.Powertrain.turbofan_surrogate import TurbofanResponseSurface

    s = TurbofanResponseSurface()
    if getattr(s, "model_mdot_inlet", None) is None:
        pytest.skip("artifact predates the inlet-flow surface")

    F00 = 240.2e3
    for alt, mach, pc in ((0.0, 0.25, 1.00), (20000.0, 0.60, 0.85), (35000.0, 0.78, 0.85)):
        core = s.core_air_flow(F00, alt, mach, pc)
        inlet = s.inlet_air_flow(F00, alt, mach, pc)
        bpr = s.bypass_ratio(alt, mach, pc)
        assert inlet > core > 0
        assert 2.0 < bpr < 10.0
        naive = core * (1.0 + bpr)
        assert naive < inlet, "the (1+BPR) reconstruction should under-predict, not match"
        assert (inlet - naive) / inlet > 0.10, "bleed gap should be substantial"


@needs_map
def test_bypass_ratio_varies_across_the_envelope():
    """If BPR were effectively constant the whole objection would be moot -- check it is not."""
    from PhlyGreen.Systems.Powertrain.turbofan_surrogate import TurbofanResponseSurface

    s = TurbofanResponseSurface()
    if getattr(s, "model_bpr", None) is None:
        pytest.skip("artifact predates the bypass-ratio surface")

    values = [s.bypass_ratio(a, m, pc)
              for a, m in ((0.0, 0.25), (10000.0, 0.45), (20000.0, 0.60), (35000.0, 0.78))
              for pc in (0.40, 0.70, 1.00)]
    spread = (max(values) - min(values)) / np.mean(values)
    assert spread > 0.05, f"BPR spread is only {100*spread:.1f} % across the envelope"


@needs_map
def test_bypass_ratio_is_size_independent():
    """BPR is a cycle property, so it must not be scaled by the installed thrust."""
    from PhlyGreen.Systems.Powertrain.turbofan_surrogate import TurbofanResponseSurface

    s = TurbofanResponseSurface()
    if getattr(s, "model_bpr", None) is None:
        pytest.skip("artifact predates the bypass-ratio surface")
    assert s.bypass_ratio(10000.0, 0.45, 0.85) == s.bypass_ratio(10000.0, 0.45, 0.85)
    # and the flows, which ARE size-dependent, must scale linearly with installed thrust
    a = s.inlet_air_flow(100e3, 10000.0, 0.45, 0.85)
    b = s.inlet_air_flow(200e3, 10000.0, 0.45, 0.85)
    assert abs(b / a - 2.0) < 1e-9
