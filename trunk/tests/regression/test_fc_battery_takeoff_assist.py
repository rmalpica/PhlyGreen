"""When does a take-off battery pay on a fuel-cell aircraft? (example 23)

On the ATR 42-600 reference (examples/common.py) and the baseline 1,107 m field the climb
sizes the fuel cell, and a take-off battery makes the aircraft heavier (21,634 -> 22,563 kg).
On an 800 m field the take-off sizes it, and a battery covering ~15 % of the take-off power
(phi* = 1 - P_climb / P_take-off) shrinks the stack (net rating 5.06 -> 4.38 MW). The motor and
PMAD carry the battery power too: they are sized on the coincident peak propulsive power
through the drive (mission.Max_PDrive, 3.93 -> 3.97 MW), so they do not shrink (motor
501 -> 507 kg). With the default 1.5 kW/kg pack the stack saving (WPT 3,153 -> 2,875 kg) does
not pay for the 512 kg battery: the aircraft is ~1.2 % heavier (24,024 -> 24,306 kg). With an
assumed 3 kW/kg power pack covering the take-off run only, the battery weighs about half as
much and the aircraft is ~3 % lighter.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "examples"))

import PhlyGreen as pg                                   # noqa: E402
from common import fuelcell_battery_config               # noqa: E402


def _design(field_m, takeoff_phi, battery_specific_power=None, taxi_phi=None):
    cfg = fuelcell_battery_config(cruise_phi=0.0)
    cfg.constraints.phases["Take Off"]["sTO"] = field_m
    if battery_specific_power is not None:
        cfg.energy.battery_specific_power = battery_specific_power
    if taxi_phi is not None:
        cfg.mission.taxi_phi = taxi_phi
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
def test_takeoff_battery_shrinks_the_stack_but_does_not_pay_on_a_short_field():
    base = _design(800.0, 0.0)
    m = base.mission
    assert m.TO_PP > m.Max_PEng                                 # take-off sizes the fuel cell
    phi_star = 1.0 - m.Max_PEng / m.TO_PP
    assert 0.1 < phi_star < 0.2
    assisted = _design(800.0, round(phi_star, 2))
    assert assisted.fuelcell.P_fc_rated < base.fuelcell.P_fc_rated   # the stack shrinks
    assert assisted.weight.WPT < base.weight.WPT
    # the motor and PMAD still carry the full take-off power, and the battery adds mass
    assert assisted.weight.WElectric > base.weight.WElectric
    assert assisted.weight.WTO > base.weight.WTO


@pytest.mark.slow
def test_takeoff_power_battery_pays_on_a_short_field():
    """A 3 kW/kg (assumed) power pack on the take-off run only makes the aircraft lighter."""
    base = _design(800.0, 0.0, taxi_phi=0.0)
    assisted = _design(800.0, 0.15, battery_specific_power=3000.0, taxi_phi=0.0)
    # The stack loses phi of its take-off load; the drive still carries the full take-off
    # power and shrinks only through the snowball of the lighter aircraft.
    stack_ratio = assisted.fuelcell.P_fc_rated / base.fuelcell.P_fc_rated
    motor_ratio = assisted.weight.WElectric / base.weight.WElectric
    assert stack_ratio < 0.9 and motor_ratio > 0.95
    assert assisted.weight.WPT < base.weight.WPT
    assert assisted.weight.WTO < 0.98 * base.weight.WTO          # and the aircraft is lighter
