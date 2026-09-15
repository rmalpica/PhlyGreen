"""The turbofan map generator must reject points whose cycle solve did not converge.

This exists because of a real failure. `prob.run_model()` does not raise when pyCycle's
off-design Newton solve stalls -- it returns whatever state it reached -- and an early version
of the sweep recorded those states silently. The resulting map had thrust lapses above 1.0
(more thrust at 10,000 ft than at sea level), compressor exit pressures implying an OPR of
~26,000, and an efficiency that did not respond to throttle at all.

`_reject_reason` is the guard. It is pure logic, so it can be tested without running a cycle.
"""

import importlib.util
import os

import pytest

pytest.importorskip("pycycle", reason="the map generator imports pyCycle")

_DECK = os.path.join(os.path.dirname(__file__), "..", "..", "PhlyGreen", "Systems",
                     "Powertrain", "data", "HBTF_turbofan.py")


@pytest.fixture(scope="module")
def deck():
    spec = importlib.util.spec_from_file_location("_hbtf_deck", os.path.abspath(_DECK))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _pair(pc=0.80, fn_full=30_000.0, lapse=0.5, opr=22.0):
    """A full-throttle / part-power state pair that should pass every check."""
    full = {"Fn_N": fn_full}
    part = {"Fn_N": pc * fn_full, "P3_Pa": opr * 101325.0}
    fn_sls = fn_full / lapse
    return full, part, pc, fn_sls


def test_a_converged_point_is_accepted(deck):
    full, part, pc, fn_sls = _pair()
    assert deck._reject_reason(full, part, pc, fn_sls, eta=0.32, tsfc=1.7e-5) is None


def test_rejects_a_thrust_fraction_that_did_not_converge(deck):
    """The most direct convergence test: percent_thrust mode must deliver the PC it was asked."""
    full, part, pc, fn_sls = _pair(pc=0.80)
    part["Fn_N"] = 0.55 * full["Fn_N"]          # solver settled somewhere else entirely
    reason = deck._reject_reason(full, part, pc, fn_sls, eta=0.32, tsfc=1.7e-5)
    assert reason and "thrust fraction did not converge" in reason


def test_rejects_thrust_lapse_above_unity(deck):
    """An engine cannot make more thrust at altitude than at sea level."""
    full, part, pc, fn_sls = _pair(lapse=1.4)
    reason = deck._reject_reason(full, part, pc, fn_sls, eta=0.32, tsfc=1.7e-5)
    assert reason and "thrust lapse" in reason


def test_rejects_an_absurd_pressure_ratio(deck):
    full, part, pc, fn_sls = _pair(opr=26_000.0)
    reason = deck._reject_reason(full, part, pc, fn_sls, eta=0.32, tsfc=1.7e-5)
    assert reason and "OPR" in reason


def test_rejects_out_of_range_or_non_finite_efficiency(deck):
    full, part, pc, fn_sls = _pair()
    assert deck._reject_reason(full, part, pc, fn_sls, eta=0.85, tsfc=1.7e-5)
    assert deck._reject_reason(full, part, pc, fn_sls, eta=float("nan"), tsfc=1.7e-5)
    assert deck._reject_reason(full, part, pc, fn_sls, eta=0.32, tsfc=float("inf"))
