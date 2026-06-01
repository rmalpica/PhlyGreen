"""Thermal-management (heat-exchanger network) scaffold.

Interfaces and a minimal balance solver for rejecting waste heat (fuel cell, electronics,
motors) into sinks (ram air, cryogenic fuel). Intended as the foundation for a future,
detailed heat-exchanger-network module — see :mod:`PhlyGreen.Systems.Thermal.network`.
"""

from .network import (
    ThermalConditions, HeatSource, HeatSink, ConstantHeatSource, CallableHeatSource,
    RamAirSink, ThermalBalance, HeatExchangerNetwork, THERMAL_COMPONENTS,
    register_thermal_component,
)

__all__ = [
    "ThermalConditions", "HeatSource", "HeatSink", "ConstantHeatSource",
    "CallableHeatSource", "RamAirSink", "ThermalBalance", "HeatExchangerNetwork",
    "THERMAL_COMPONENTS", "register_thermal_component",
]
