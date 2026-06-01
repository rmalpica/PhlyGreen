"""The top-level :class:`AircraftConfig` bundling all configuration sections + flags.

This is the single typed entry point that replaces the loose pile of dicts plus the
``aircraft.Configuration = ...`` flag assignments. Apply it with
``aircraft.configure(config)`` (see :meth:`PhlyGreen.Aircraft.Aircraft.configure`).
"""

from dataclasses import dataclass
from typing import Optional

from ._base import ConfigError
from .sections import (
    MissionConfig, EnergyConfig, CellConfig, WellToTankConfig,
    ClimateImpactConfig, AerodynamicsConfig, ConstraintsConfig,
)
from .profile import StagesConfig


@dataclass
class AircraftConfig:
    """Complete, validated specification of an aircraft design problem."""

    # configuration flags (formerly set directly on the Aircraft instance)
    configuration: str = None          # 'Traditional' | 'Hybrid'
    hybrid_type: Optional[str] = None  # 'Parallel' | 'Serial'
    aircraft_type: str = None          # 'ATR' | 'DO228'
    weight_class: str = "I"            # 'I' | 'II'

    # required sections
    aerodynamics: AerodynamicsConfig = None
    constraints: ConstraintsConfig = None
    mission: MissionConfig = None
    energy: EnergyConfig = None
    mission_stages: StagesConfig = None
    diversion_stages: StagesConfig = None

    # optional sections
    loiter_stages: Optional[StagesConfig] = None
    well_to_tank: Optional[WellToTankConfig] = None
    cell: Optional[CellConfig] = None
    climate_impact: Optional[ClimateImpactConfig] = None

    def __post_init__(self):
        if self.configuration not in ("Traditional", "Hybrid"):
            raise ConfigError(
                f"configuration must be 'Traditional' or 'Hybrid', got {self.configuration!r}")
        if self.configuration == "Hybrid" and self.hybrid_type not in ("Parallel", "Serial"):
            raise ConfigError(
                f"hybrid_type must be 'Parallel' or 'Serial' for Hybrid, got {self.hybrid_type!r}")
        if self.weight_class not in ("I", "II"):
            raise ConfigError(f"weight_class must be 'I' or 'II', got {self.weight_class!r}")

    def read_input_args(self):
        """Return ``(positional, kwargs)`` matching ``Aircraft.ReadInput``'s signature."""
        positional = [
            self.aerodynamics.to_dict(),
            self.constraints.to_dict(),
            self.mission.to_dict(),
            self.energy.to_dict(),
            self.mission_stages.to_dict(),
            self.diversion_stages.to_dict(),
        ]
        kwargs = {}
        if self.loiter_stages is not None:
            kwargs["LoiterStages"] = self.loiter_stages.to_dict()
        if self.well_to_tank is not None:
            kwargs["WellToTankInput"] = self.well_to_tank.to_dict()
        if self.cell is not None:
            kwargs["CellInput"] = self.cell.to_dict()
        if self.climate_impact is not None:
            kwargs["ClimateImpactInput"] = self.climate_impact.to_dict()
        return positional, kwargs
