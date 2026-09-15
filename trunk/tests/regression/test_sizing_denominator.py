"""The constraint diagram's sizing denominator must be a no-op for power-rated aircraft.

Adding the turbofan meant rewriting every constraint block in `Constraint.EvaluateConstraints`
so the divisor is applied *after* the requirement (the divisor reads the speed state that the
requirement call sets). That rewrite touches every existing design, so this module pins the
invariant that makes it safe: for every configuration except Turbofan,
`Powertrain.SizingDenominator` returns exactly `PowerLapse`, and the design point is
unchanged. If this fails, the golden masters are about to move.
"""

import sys, os
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "examples"))

import PhlyGreen as pg
from common import traditional_config, hybrid_config


ALTITUDES = [0.0, 100.0, 3000.0, 5000.0, 6000.0, 8000.0, 9500.0]


@pytest.mark.parametrize("make_config", [traditional_config, hybrid_config],
                         ids=["traditional", "hybrid"])
def test_denominator_is_exactly_the_power_lapse(make_config):
    ac = pg.build_aircraft()
    ac.configure(make_config(), design=False)
    DISA = ac.constraint.DISA
    for alt in ALTITUDES:
        assert (ac.powertrain.SizingDenominator(alt, DISA)
                == ac.powertrain.PowerLapse(alt, DISA))


def test_take_off_denominator_is_unity_for_power_rated_aircraft():
    """Take-off was never lapsed; altitude_lapse=False must preserve that exactly."""
    ac = pg.build_aircraft()
    ac.configure(traditional_config(), design=False)
    assert ac.powertrain.SizingDenominator(100.0, 0.0, altitude_lapse=False) == 1.0


def test_design_point_unchanged_for_a_power_rated_aircraft():
    """Pinned from the pre-turbofan implementation of the constraint diagram."""
    ac = pg.build_aircraft()
    ac.configure(traditional_config(), design=False)
    ac.constraint.FindDesignPoint(None)
    assert ac.DesignPW == pytest.approx(194.905679, rel=1e-9)
    assert ac.DesignWTOoS == pytest.approx(3293.822823, rel=1e-9)


def test_design_tw_is_rejected_for_a_power_rated_aircraft():
    """DesignPW holds W/kg here, not N/kg; asking for T/W must not silently return it."""
    ac = pg.build_aircraft()
    ac.configure(traditional_config(), design=False)
    ac.constraint.FindDesignPoint(None)
    with pytest.raises(ValueError, match="only defined for the Turbofan"):
        _ = ac.DesignTW


def test_empty_aeo_climb_phase_does_not_break_the_design_point():
    """The empty-phase branch used to assign PWClimb, which FindDesignPoint never reads."""
    cfg = traditional_config()
    cfg.constraints.phases['AEO Climb'] = {}
    ac = pg.build_aircraft()
    ac.configure(cfg, design=False)
    ac.constraint.FindDesignPoint(None)
    assert np.all(ac.constraint.PWAEOClimb == 0.0)
    assert ac.DesignPW > 0.0
