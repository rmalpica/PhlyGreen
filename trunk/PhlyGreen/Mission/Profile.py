"""Mission profile generator (clean, extensible reimplementation).

Builds the time history of altitude, velocity, vertical rate, and (for hybrids) the
supplied-power ratio phi(t) over a full trajectory: mission climb/cruise/descent, an
optional diversion, and an optional loiter.

Design
------
The trajectory is a list of *segments* (see :mod:`PhlyGreen.Mission.segments`). Each
segment computes its own geometry; this class only:

1. instantiates segments from the stage dicts (via the segment registry),
2. orders them within each phase (climbs, then cruise, then descents),
3. lays them on a common timeline (``Breaks`` = the segment start-times), and
4. exposes piecewise lookups :meth:`Altitude`, :meth:`Velocity`, :meth:`PowerExcess`,
   :meth:`SuppliedPowerRatio`.

This replaces the legacy ``getattr`` dispatch, manual counters, and offset-indexed
altitude closures of :mod:`PhlyGreen.Mission.Profile_legacy`, while producing identical
numerical results (verified in tests/regression/test_profile_equivalence.py). New segment
types can be added purely by registering them — no change to this file.
"""

import numbers

import numpy as np

import PhlyGreen.Utilities.Speed as Speed
import PhlyGreen.Utilities.Units as Units
from .segments import make_segment, CRUISE, CLIMB, DESCENT


class _MergedSegment:
    """One segment placed on the global timeline."""

    __slots__ = ("name", "phase", "start_time", "start_altitude", "vertical_rate",
                 "velocity", "duration", "phi_start", "phi_end", "category")

    def __init__(self, name, phase, result, phi_start, phi_end):
        self.name = name
        self.phase = phase
        self.start_altitude = result.start_altitude
        self.vertical_rate = result.vertical_rate
        self.velocity = result.velocity
        self.duration = result.duration
        self.category = result.category
        self.phi_start = phi_start
        self.phi_end = phi_end
        self.start_time = None  # filled in during global assembly

    @property
    def end_time(self):
        return self.start_time + self.duration


class Profile:
    """Mission profile generator. Drop-in replacement for the legacy ``Profile``."""

    def __init__(self, aircraft):
        self.aircraft = aircraft

        self.MissionRange = None
        self.DiversionRange = None
        self.MissionStages = None
        self.DiversionStages = None
        self.LoiterStages = None
        self.TLoiter = None
        self.LoiterRange = None
        self.AltitudeLoiter = None

        self._segments = []          # list[_MergedSegment] in flight order

        # legacy-compatible public surface (assembled in DefineMission)
        self.Breaks = None
        self.Velocities = None
        self.HTMission = None
        self.MissionTime = None
        self.MissionTime2 = None
        self.SPW = None
        self.SPWinterp = None
        self.times = None
        self.Distances = []
        self.DistancesDiversion = []
        self.BreaksClimb = []
        self.BreaksDescent = []
        self.BreaksClimbDiversion = []

        self._alt_funcs = []

    # --- properties (preserve legacy validation) ----------------------------

    @property
    def MissionRange(self):
        if self._MissionRange is None:
            raise ValueError("Mission Range unset. Exiting")
        return self._MissionRange

    @MissionRange.setter
    def MissionRange(self, value):
        if isinstance(value, numbers.Number) and value <= 0:
            raise ValueError("Error: Illegal mission range: %e. Exiting" % value)
        self._MissionRange = value

    @property
    def DiversionRange(self):
        if self._DiversionRange is None:
            raise ValueError("Diversion Range unset. Exiting")
        return self._DiversionRange

    @DiversionRange.setter
    def DiversionRange(self, value):
        if isinstance(value, numbers.Number) and value <= 0:
            raise ValueError("Error: Illegal diversion range: %e. Exiting" % value)
        self._DiversionRange = value

    # --- setup --------------------------------------------------------------

    def SetInput(self):
        self.MissionRange = Units.NMtoM(self.aircraft.MissionInput['Range Mission'])
        self.DiversionRange = Units.NMtoM(self.aircraft.MissionInput['Range Diversion'])
        self.MissionStages = self.aircraft.MissionStages
        self.DiversionStages = self.aircraft.DiversionStages
        if self.aircraft.LoiterStages is not None:
            self.LoiterStages = self.aircraft.LoiterStages
            self.AltitudeLoiter = self.aircraft.LoiterStages['Cruise']['input']['Altitude']
            if 'Range Loiter' in self.aircraft.MissionInput:
                self.LoiterRange = Units.NMtoM(self.aircraft.MissionInput['Range Loiter'])
            elif 'Time Loiter' in self.aircraft.MissionInput:
                self.TLoiter = self.aircraft.MissionInput['Time Loiter']
            else:
                raise ValueError("Insert loiter range or duration")

    # --- assembly -----------------------------------------------------------

    def DefineMission(self):
        """Build the full timeline and the phi(t) schedule."""
        self.SetInput()
        hybrid = self.aircraft.Configuration == 'Hybrid'

        merged = []
        # Mission phase (also carries the takeoff supplied-power ratio).
        mission_segs, self.Distances, phi_takeoff = self._build_phase(
            self.MissionStages, self.MissionRange, "Mission", hybrid, want_takeoff=True)
        merged += mission_segs

        # Diversion phase.
        diversion_segs, self.DistancesDiversion, _ = self._build_phase(
            self.DiversionStages, self.DiversionRange, "Diversion", hybrid)
        merged += diversion_segs

        # Optional loiter phase.
        if self.LoiterStages is not None:
            merged += self._build_loiter(hybrid)

        # Lay segments on the global timeline: Breaks are the segment start-times.
        t = 0.0
        for seg in merged:
            seg.start_time = t
            t += seg.duration
        self._segments = merged

        self.Breaks = [seg.start_time for seg in merged]
        self.Velocities = [seg.velocity for seg in merged]
        self.HTMission = [seg.vertical_rate for seg in merged]
        self.MissionTime2 = merged[-1].end_time if merged else 0.0

        # End of the mission phase (used by some downstream consumers).
        mission_end = [s.end_time for s in merged if s.phase == "Mission"]
        self.MissionTime = mission_end[-1] if mission_end else 0.0

        # Legacy-compatible auxiliary break lists.
        self.BreaksClimb = [s.end_time for s in merged if s.phase == "Mission" and s.category == CLIMB]
        self.BreaksDescent = [s.end_time for s in merged if s.phase == "Mission" and s.category == DESCENT]
        self.BreaksClimbDiversion = [s.end_time for s in merged if s.phase == "Diversion" and s.category == CLIMB]

        # Altitude lookup functions (default-arg binding avoids the late-binding bug).
        self._alt_funcs = [
            (lambda t, a=seg.start_altitude, h=seg.vertical_rate, b=seg.start_time: a + h * (t - b))
            for seg in merged
        ]

        if hybrid:
            spw = [[phi_takeoff, phi_takeoff]]
            spw += [[seg.phi_start, seg.phi_end] for seg in merged]
            self.SPW = np.array(spw, dtype=float)
            self.times = np.append(self.Breaks, self.MissionTime2)
            self.SPWinterp = [
                (lambda t, i=i: np.interp(t, [self.times[i], self.times[i + 1]], self.SPW[i + 1]))
                for i in range(len(self.times) - 1)
            ]

    def _build_phase(self, stages, phase_range, phase, hybrid, want_takeoff=False):
        """Build the ordered merged segments for one phase.

        Returns (merged_segments, non_cruise_distances, takeoff_phi).
        """
        phi_takeoff = 0.0
        noncruise = []  # (name, stage, result)
        cruise = []     # (name, stage, segment)

        for name, stage in stages.items():
            if 'type' not in stage:           # takeoff-style entry (phi only)
                if want_takeoff:
                    phi_takeoff = stage.get('Supplied Power Ratio', {}).get('phi', 0.0)
                continue
            seg = make_segment(name, stage['type'], stage.get('input'))
            if seg.category == CRUISE:
                cruise.append((name, stage, seg))
            else:
                noncruise.append((name, stage, seg.compute(phase_range, 0.0)))

        distance_so_far = sum(r.distance for _, _, r in noncruise)
        built = [(name, stage, r) for name, stage, r in noncruise]
        for name, stage, seg in cruise:
            built.append((name, stage, seg.compute(phase_range, distance_so_far)))

        # Order within the phase: climbs, then cruise, then descents (stable).
        built.sort(key=lambda item: item[2].category)

        merged = [_MergedSegment(name, phase, result, *self._phi(stage, hybrid))
                  for name, stage, result in built]
        non_cruise_distances = [r.distance for _, _, r in noncruise]
        return merged, non_cruise_distances, phi_takeoff

    def _build_loiter(self, hybrid):
        cruise = self.LoiterStages['Cruise']
        velocity = Speed.Mach2TAS(cruise['input']['Mach'], self.AltitudeLoiter)
        if self.TLoiter is not None:
            duration = self.TLoiter * 60.0
        else:
            duration = np.ceil(self.LoiterRange / velocity)

        from .segments import SegmentResult
        result = SegmentResult(
            start_altitude=self.AltitudeLoiter, vertical_rate=0, velocity=velocity,
            duration=duration, distance=velocity * duration, category=CRUISE)
        return [_MergedSegment('Loiter', 'Loiter', result, *self._phi(cruise, hybrid))]

    @staticmethod
    def _phi(stage, hybrid):
        if not hybrid:
            return (None, None)
        spr = stage.get('Supplied Power Ratio', {})
        return (spr.get('phi_start', 0), spr.get('phi_end', 0))

    # --- piecewise lookups --------------------------------------------------

    def Altitude(self, t):
        """Altitude at time t [m]."""
        return np.piecewise(t, [t >= ti for ti in self.Breaks], self._alt_funcs)

    def PowerExcess(self, t):
        """Vertical rate dh/dt at time t [m/s]."""
        return np.piecewise(t, [t >= ti for ti in self.Breaks], self.HTMission)

    def Velocity(self, t):
        """True airspeed at time t [m/s]."""
        return np.piecewise(t, [t >= ti for ti in self.Breaks], self.Velocities)

    def SuppliedPowerRatio(self, t):
        """Hybrid supplied-power ratio phi(t) via per-segment linear interpolation."""
        idx = np.piecewise(
            t,
            [self.times[i] < t <= self.times[i + 1] for i in range(len(self.times) - 1)],
            [i for i in range(len(self.times) - 1)],
        )
        return self.SPWinterp[int(idx)](t)
