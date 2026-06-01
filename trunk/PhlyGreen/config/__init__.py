"""Typed configuration objects for PhlyGreen.

Replaces the deeply nested, unvalidated input dictionaries with dataclasses that have
named fields, defaults, and validation, while remaining fully interoperable with the
legacy dict API (every section has ``to_dict``/``from_dict``).
"""

from ._base import ConfigError, DictConfig
from .sections import (
    MissionConfig, EnergyConfig, CellConfig, WellToTankConfig,
    ClimateImpactConfig, AerodynamicsConfig, ConstraintsConfig, TankConfig,
)
from .profile import Segment, StagesConfig
from .aircraft_config import AircraftConfig

__all__ = [
    "ConfigError", "DictConfig",
    "MissionConfig", "EnergyConfig", "CellConfig", "WellToTankConfig",
    "ClimateImpactConfig", "AerodynamicsConfig", "ConstraintsConfig", "TankConfig",
    "Segment", "StagesConfig", "AircraftConfig",
]
