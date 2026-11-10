"""Class-II (FLOPS) structures on full designs: the wing follows the sizing.

* The FLOPS wing area is the sized wing area, and the span is sqrt(AR * S).
* A larger aspect ratio at the same wing loading makes a heavier wing.
* A 'Turbofan' can be sized with Class II: no propeller mass, nacelles from the sized thrust.
"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "examples"))

import PhlyGreen as pg                                              # noqa: E402
import PhlyGreen.Utilities.Units as Units                           # noqa: E402
from PhlyGreen.Weight.Components.sizing_inputs import (            # noqa: E402
    wing_area_ft2, wing_span_ft)
from common import (traditional_config, turbofan_config,           # noqa: E402
                    atr_flops_input, a320_flops_input)

ATR42_WING_LOADING = 18600.0 / 54.5          # [kg/m^2], ATR 42-600 factsheet


def _atr(aspect_ratio=11.0):
    cfg = traditional_config()
    cfg.weight_class = 'II'
    cfg.design_wing_loading = ATR42_WING_LOADING * 9.81
    cfg.aerodynamics.analytic_polar["input"]["AR"] = aspect_ratio
    a = pg.build_aircraft()
    a.FLOPSInput = atr_flops_input()
    a.configure(cfg)
    return a


@pytest.mark.slow
def test_flops_wing_area_and_span_follow_the_sizing():
    a = _atr()
    area = Units.ft2tom2(wing_area_ft2(a, a.FLOPSInput))
    assert area == pytest.approx(a.WingSurface, rel=1e-4)
    span = Units.ftTom(wing_span_ft(a, a.FLOPSInput))
    assert span == pytest.approx(np.sqrt(11.0 * a.WingSurface), rel=1e-4)


@pytest.mark.slow
def test_a_larger_aspect_ratio_makes_a_heavier_wing():
    wings = [Units.lbTokg(_atr(ar).weight.AircraftComponents.Wing.wingmass) for ar in (8, 11, 14)]
    assert wings[0] < wings[1] < wings[2]
    assert wings[2] / wings[0] > 1.25             # +35 % from AR 8 to 14 at 341 kg/m^2


@pytest.mark.slow
def test_turbofan_class_ii_has_nacelles_and_no_propeller():
    cfg = turbofan_config()
    cfg.weight_class = 'II'
    a = pg.build_aircraft()
    a.FLOPSInput = a320_flops_input()
    a.configure(cfg)
    c = a.weight.AircraftComponents
    assert c.Propeller.propellermass == 0.0
    assert c.Nacelle.nacellemass > 0.0
    assert c.OperatingItems.starter_mass > 0.0
    r = a.results()
    assert r.empty_weight + r.WPayload + r.Wf + r.final_reserve == pytest.approx(r.WTO, abs=5.0)
