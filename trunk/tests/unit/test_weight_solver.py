"""Unit tests for the robust WTO Brent solver (Weight._solve_wto).

The solver must (a) reproduce plain Brent when the full bracket already works, and (b) still
converge when the fixed endpoints do NOT bracket a sign change or the residual errors
mid-range — the failure modes that made parametric sweeps non-convergent.
"""

import types

import pytest

from PhlyGreen.Weight.Weight import Weight


def _solver():
    # _solve_wto only touches self.tol and self.aircraft.MissionInput.
    return Weight(types.SimpleNamespace(MissionInput={}))


def test_full_bracket_is_used_when_it_works():
    w = _solver()
    root = w._solve_wto(lambda x: x - 70000.0, 1000, 300000, xtol=1e-3)
    assert root == pytest.approx(70000.0, abs=1.0)


def test_fallback_when_endpoints_do_not_bracket():
    # Two roots (50k, 150k): f(1000)>0 and f(300000)>0 -> plain Brent raises; the grid scan
    # finds the first sign-change bracket and returns the lower root.
    w = _solver()
    root = w._solve_wto(lambda x: (x - 50000.0) * (x - 150000.0), 1000, 300000,
                        step=10000, xtol=1e-3)
    assert root == pytest.approx(50000.0, abs=50.0)


def test_fallback_when_residual_errors_midrange():
    # Residual blows up above 200k (e.g. TMS/feasibility limits) so the full-range evaluation
    # raises; the scan still brackets the real root at 50k from below.
    def func(x):
        if x > 200000.0:
            raise ValueError("infeasible region")
        return x - 50000.0

    w = _solver()
    root = w._solve_wto(func, 1000, 300000, step=10000, xtol=1e-3)
    assert root == pytest.approx(50000.0, abs=50.0)


def test_reraises_when_no_bracket_exists():
    w = _solver()
    with pytest.raises(Exception):
        w._solve_wto(lambda x: 1.0, 1000, 300000, step=10000, xtol=1e-3)
