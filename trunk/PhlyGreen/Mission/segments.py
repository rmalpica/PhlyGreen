"""Flight-profile segment types and an extensible registry.

A flight profile is a sequence of *segments* (climb, cruise, descent, ...). Each segment
type is a small, self-contained class that knows how to compute its own geometry — its
duration, ground distance, velocity and vertical rate — from its input dict. New segment
types are added by subclassing :class:`FlightSegment` and registering them, with no
changes to the profile-assembly code::

    @register_segment("ConstantThrustClimb")
    class ConstantThrustClimbSegment(FlightSegment):
        category = CLIMB
        def compute(self, phase_range, distance_so_far):
            ...

This replaces the legacy ``getattr(self, stage['type'])(...)`` dispatch and the per-type
``if phase == 'Mission'/'Diversion'`` branches in the old Profile.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import numpy as np

import PhlyGreen.Utilities.Speed as Speed

# Merge-ordering categories: within a phase, climbs come first, then cruise, then descents
# (matching the legacy MergeMission ordering).
CLIMB = 0
CRUISE = 1
DESCENT = 2


@dataclass
class SegmentResult:
    """Geometry of one executed segment (all SI units; times in s, distances in m)."""

    start_altitude: float
    vertical_rate: float   # dh/dt [m/s] (0 for cruise, negative for descent)
    velocity: float        # true airspeed [m/s]
    duration: float        # [s]
    distance: float        # ground distance covered [m]
    category: int          # CLIMB / CRUISE / DESCENT


class FlightSegment(ABC):
    """Base class for all flight-profile segments.

    Attributes:
        name: the stage name (e.g. ``'Climb1'``).
        inputs: the stage ``'input'`` dict.
        category: CLIMB/CRUISE/DESCENT, used for ordering within a phase.
    """

    category = CLIMB

    def __init__(self, name, inputs):
        self.name = name
        self.inputs = inputs or {}

    @abstractmethod
    def compute(self, phase_range, distance_so_far):
        """Return a :class:`SegmentResult`.

        Args:
            phase_range: total ground range of the phase this segment belongs to [m].
            distance_so_far: ground distance already consumed by non-cruise segments of
                this phase [m] (used by range-filling cruise segments).
        """


class _ConstantRateSegment(FlightSegment):
    """Shared logic for a constant-gradient, constant-true-airspeed climb/descent."""

    def compute(self, phase_range, distance_so_far):
        start = self.inputs["StartAltitude"]
        end = self.inputs["EndAltitude"]
        cb = self.inputs["CB"]
        velocity = self.inputs["Speed"]

        vertical_rate = cb * velocity
        duration = np.ceil(abs((end - start) / vertical_rate))
        distance = velocity * duration
        return SegmentResult(
            start_altitude=start,
            vertical_rate=vertical_rate,
            velocity=velocity,
            duration=duration,
            distance=distance,
            category=self.category,
        )


class ConstantRateClimbSegment(_ConstantRateSegment):
    """Constant climb gradient (CB) at constant true airspeed."""
    category = CLIMB


class ConstantRateDescentSegment(_ConstantRateSegment):
    """Constant descent gradient (CB < 0) at constant true airspeed."""
    category = DESCENT


class ConstantMachCruiseSegment(FlightSegment):
    """Level, constant-Mach cruise that fills the remaining range of its phase."""
    category = CRUISE

    def compute(self, phase_range, distance_so_far):
        altitude = self.inputs["Altitude"]
        velocity = Speed.Mach2TAS(self.inputs["Mach"], altitude)
        remaining = phase_range - distance_so_far
        duration = np.ceil(remaining / velocity)
        return SegmentResult(
            start_altitude=altitude,
            vertical_rate=0,
            velocity=velocity,
            duration=duration,
            distance=remaining,
            category=self.category,
        )


# --- registry ---------------------------------------------------------------

SEGMENT_TYPES = {
    "ConstantRateClimb": ConstantRateClimbSegment,
    "ConstantRateDescent": ConstantRateDescentSegment,
    "ConstantMachCruise": ConstantMachCruiseSegment,
}


def register_segment(name):
    """Class decorator registering a new segment type under ``name``."""
    def _register(cls):
        SEGMENT_TYPES[name] = cls
        return cls
    return _register


def make_segment(name, segment_type, inputs):
    """Instantiate the segment class registered for ``segment_type``."""
    try:
        cls = SEGMENT_TYPES[segment_type]
    except KeyError:
        raise KeyError(
            f"Unknown segment type {segment_type!r}. Registered types: "
            f"{sorted(SEGMENT_TYPES)}"
        )
    return cls(name, inputs)
