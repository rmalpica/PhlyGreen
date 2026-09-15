"""Unit tests for the 'compressible' drag polar (Korn drag divergence + Lock wave drag).

The plain quadratic polar carries no wave drag, and the legacy `Cd0(Mach)` bump is flat
below M 0.8 and then steps *down*. Neither can size a transonic aircraft, which is why the
turbofan configuration needs this polar. These tests pin the properties that make it usable:
the drag rise is zero below M_crit, monotone and steep above it, and consistent with the
definition of the drag-divergence Mach number.
"""

import numpy as np
import pytest

from PhlyGreen.Systems.Aerodynamics.Aerodynamics import Aerodynamics


def _aero(sweep=25.0, tc=0.11, kappa=0.95, cd0=0.0180):
    a = Aerodynamics(None)
    a.set_compressible_polar(AR=9.5, e_osw=0.80)
    a.Cd_0, a.ClMin = cd0, 0.0
    a.sweep, a.tc, a.kappa = sweep, tc, kappa
    return a


def test_drag_divergence_definition_holds():
    """M_dd is *defined* as dCd/dM = 0.1; the M_crit offset must reproduce that exactly."""
    a = _aero()
    m_dd = float(a.MachDD(0.5))
    d = 1e-5
    slope = float((a.Cd_wave(0.5, m_dd + d) - a.Cd_wave(0.5, m_dd - d)) / (2 * d))
    assert slope == pytest.approx(0.1, rel=1e-3)


def test_no_wave_drag_below_critical_mach():
    a = _aero()
    m_crit = float(a.MachCrit(0.5))
    assert float(a.Cd_wave(0.5, m_crit - 0.05)) == 0.0
    assert float(a.Cd_wave(0.5, 0.3)) == 0.0


def test_wave_drag_is_monotone_and_steep():
    a = _aero()
    machs = np.array([0.74, 0.78, 0.80, 0.82, 0.84, 0.86])
    cdw = np.array([float(a.Cd_wave(0.5, m)) for m in machs])
    assert np.all(np.diff(cdw) >= 0.0)
    # Fourth-power growth: doubling the overshoot past M_crit raises wave drag ~16x.
    m_crit = float(a.MachCrit(0.5))
    assert (float(a.Cd_wave(0.5, m_crit + 0.08))
            == pytest.approx(16.0 * float(a.Cd_wave(0.5, m_crit + 0.04)), rel=1e-6))


def test_sweep_and_thinness_delay_drag_divergence():
    """The geometry terms must act in the physically right direction."""
    base = float(_aero(sweep=25.0, tc=0.11).MachDD(0.5))
    assert float(_aero(sweep=35.0, tc=0.11).MachDD(0.5)) > base   # more sweep
    assert float(_aero(sweep=25.0, tc=0.09).MachDD(0.5)) > base   # thinner
    assert float(_aero(sweep=25.0, tc=0.11).MachDD(0.2)) > base   # less loaded


def test_compressible_reduces_to_quadratic_below_drag_rise():
    a = _aero()
    q = Aerodynamics(None)
    q.set_quadratic_polar(AR=9.5, e_osw=0.80)
    q.Cd_0, q.ClMin = 0.0180, 0.0
    assert float(a.Cd(0.5, 0.60)) == pytest.approx(float(q.Cd(0.5, 0.60)))


def test_cd0_accepts_an_array_of_mach():
    """The legacy np.piecewise mis-broadcast its array branch; np.where does not."""
    a = _aero()
    out = a.Cd(0.5, np.array([0.60, 0.78, 0.84]))
    assert out.shape == (3,)
    assert out[2] > out[1] > out[0]

    q = Aerodynamics(None)
    q.set_quadratic_polar(AR=11, e_osw=0.8)
    q.Cd_0, q.ClMin = 0.021476, 0.0
    legacy = q.Cd0(np.array([0.5, 0.9]))
    assert legacy[0] == pytest.approx(0.021476)
    assert legacy[1] == pytest.approx(0.035 * 0.9 - 0.011)
