"""A take-off battery pays on a fuel-cell aircraft only when the take-off sizes the stack.

Pins the result discussed in example 23 and the hydrogen user guide, on the ATR 42-600
reference (examples/common.py): on the baseline 1,107 m field the climb sizes the fuel cell
and a take-off battery makes the aircraft heavier; on an 800 m field the take-off sizes it,
and a battery covering ~15 % of the take-off power (phi* = 1 - P_climb / P_take-off) makes the
aircraft lighter.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "examples"))

import PhlyGreen as pg                                   # noqa: E402
from common import fuelcell_battery_config               # noqa: E402


def _design(field_m, takeoff_phi):
    cfg = fuelcell_battery_config(cruise_phi=0.0)
    cfg.constraints.phases["Take Off"]["sTO"] = field_m
    for seg in cfg.mission_stages.segments:
        if seg.name == "Takeoff":
            seg.phi = takeoff_phi
        elif seg.segment_type in ("ConstantRateClimb", "ConstantMachCruise"):
            seg.phi_start = seg.phi_end = 0.0
    a = pg.build_aircraft()
    a.configure(cfg)
    return a


@pytest.mark.slow
def test_takeoff_battery_does_not_pay_when_the_climb_sizes_the_fuel_cell():
    base = _design(1107.0, 0.0)
    assert base.mission.Max_PEng > base.mission.TO_PP           # climb peak > take-off power
    assert _design(1107.0, 0.10).weight.WTO > base.weight.WTO


@pytest.mark.slow
def test_takeoff_battery_pays_on_a_short_field():
    base = _design(800.0, 0.0)
    m = base.mission
    assert m.TO_PP > m.Max_PEng                                 # take-off sizes the fuel cell
    phi_star = 1.0 - m.Max_PEng / m.TO_PP
    assert 0.1 < phi_star < 0.2
    assisted = _design(800.0, round(phi_star, 2))
    assert assisted.weight.WTO < base.weight.WTO
    assert assisted.weight.WPT < base.weight.WPT                # the stack shrinks
