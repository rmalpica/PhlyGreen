"""Unit tests for flight-profile segments and the extensible registry.

These teach how a profile is built one segment at a time, and show how to add a brand-new
segment type without touching the profile-assembly code.
"""

import numpy as np
import pytest

import PhlyGreen.Utilities.Speed as Speed
from PhlyGreen.Mission.segments import (
    SEGMENT_TYPES, make_segment, register_segment, FlightSegment, SegmentResult,
    ConstantRateClimbSegment, ConstantRateDescentSegment, ConstantMachCruiseSegment,
    CLIMB, CRUISE, DESCENT,
)


# --- individual segment geometry --------------------------------------------

def test_constant_rate_climb_geometry():
    seg = ConstantRateClimbSegment("Climb1", {"StartAltitude": 100, "EndAltitude": 1500,
                                              "CB": 0.16, "Speed": 77})
    r = seg.compute(phase_range=1e6, distance_so_far=0)
    assert r.category == CLIMB
    assert r.vertical_rate == pytest.approx(0.16 * 77)            # dh/dt
    assert r.duration == np.ceil((1500 - 100) / (0.16 * 77))      # ceil of dh/rate
    assert r.distance == pytest.approx(77 * r.duration)
    assert r.start_altitude == 100


def test_constant_rate_descent_has_negative_rate():
    seg = ConstantRateDescentSegment("Descent1", {"StartAltitude": 8000, "EndAltitude": 200,
                                                  "CB": -0.04, "Speed": 90})
    r = seg.compute(phase_range=1e6, distance_so_far=0)
    assert r.category == DESCENT
    assert r.vertical_rate < 0
    assert r.duration == np.ceil(abs((200 - 8000) / (-0.04 * 90)))


def test_constant_mach_cruise_fills_remaining_range():
    seg = ConstantMachCruiseSegment("Cruise", {"Mach": 0.4, "Altitude": 8000})
    phase_range, already = 1_000_000.0, 300_000.0
    r = seg.compute(phase_range=phase_range, distance_so_far=already)
    assert r.category == CRUISE
    assert r.vertical_rate == 0
    assert r.velocity == pytest.approx(Speed.Mach2TAS(0.4, 8000))
    assert r.duration == np.ceil((phase_range - already) / r.velocity)


# --- registry ---------------------------------------------------------------

def test_known_types_are_registered():
    for name in ("ConstantRateClimb", "ConstantRateDescent", "ConstantMachCruise"):
        assert name in SEGMENT_TYPES


def test_unknown_segment_type_raises():
    with pytest.raises(KeyError):
        make_segment("X", "NotARealSegment", {})


def test_register_new_segment_type_is_usable():
    @register_segment("ConstantTimeClimb")
    class ConstantTimeClimbSegment(FlightSegment):
        category = CLIMB

        def compute(self, phase_range, distance_so_far):
            v = self.inputs["Speed"]
            dur = self.inputs["Duration"]
            return SegmentResult(self.inputs["StartAltitude"], self.inputs["CB"] * v,
                                 v, dur, v * dur, CLIMB)

    try:
        seg = make_segment("Climb", "ConstantTimeClimb",
                           {"StartAltitude": 0, "CB": 0.1, "Speed": 80, "Duration": 120})
        r = seg.compute(0, 0)
        assert r.duration == 120
        assert r.distance == pytest.approx(80 * 120)
    finally:
        del SEGMENT_TYPES["ConstantTimeClimb"]
