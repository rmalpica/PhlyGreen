"""Typed configuration for mission flight profiles (``MissionStages`` etc.).

The legacy format is an *ordered* dict of stages, each like::

    'Climb1': {'type': 'ConstantRateClimb',
               'input': {...},
               'Supplied Power Ratio': {'phi_start': 0, 'phi_end': 0}}

with a special takeoff entry carrying only a constant ``phi``. :class:`Segment` makes
one stage a typed object and :class:`StagesConfig` an ordered collection that serializes
back to the legacy ordered dict.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from ._base import ConfigError


def _check_fraction(name, value):
    if value is not None and not (0.0 <= value <= 1.0):
        raise ConfigError(f"{name} must be in [0, 1], got {value!r}")


@dataclass
class Segment:
    """A single flight-profile stage.

    Either set ``phi`` (constant supplied-power ratio over the segment) or the pair
    ``phi_start``/``phi_end`` (linear ramp). A takeoff-style entry sets only ``phi`` and
    leaves ``segment_type``/``inputs`` as ``None``.
    """

    name: str
    segment_type: Optional[str] = None
    inputs: Optional[Dict[str, Any]] = None
    phi: Optional[float] = None
    phi_start: Optional[float] = None
    phi_end: Optional[float] = None

    def __post_init__(self):
        for n in ("phi", "phi_start", "phi_end"):
            _check_fraction(n, getattr(self, n))
        if self.segment_type is not None and self.inputs is None:
            raise ConfigError(f"segment {self.name!r} has a type but no inputs")

    def _supplied_power_ratio(self):
        if self.phi is not None:
            return {"phi": self.phi}
        return {
            "phi_start": self.phi_start if self.phi_start is not None else 0,
            "phi_end": self.phi_end if self.phi_end is not None else 0,
        }

    def to_stage_dict(self):
        """Return the legacy per-stage dict (the value keyed by the stage name)."""
        out = {}
        if self.segment_type is not None:
            out["type"] = self.segment_type
            out["input"] = dict(self.inputs)
        out["Supplied Power Ratio"] = self._supplied_power_ratio()
        return out

    @classmethod
    def from_stage_dict(cls, name, data):
        spr = data.get("Supplied Power Ratio", {})
        return cls(
            name=name,
            segment_type=data.get("type"),
            inputs=data.get("input"),
            phi=spr.get("phi"),
            phi_start=spr.get("phi_start"),
            phi_end=spr.get("phi_end"),
        )


@dataclass
class StagesConfig:
    """An ordered collection of :class:`Segment` (one flight phase's stages)."""

    segments: List[Segment] = field(default_factory=list)

    def to_dict(self):
        return {seg.name: seg.to_stage_dict() for seg in self.segments}

    @classmethod
    def from_dict(cls, data):
        if data is None:
            return None
        return cls(segments=[Segment.from_stage_dict(name, d) for name, d in data.items()])

    def add(self, segment: Segment):
        self.segments.append(segment)
        return self
