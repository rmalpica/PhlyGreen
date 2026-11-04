"""Thermal management.

- :mod:`.network` -- scaffold for heat-source / heat-sink balances (used for studies).
- :mod:`.TMS` -- the aircraft thermal-management subsystem (``aircraft.tms``): Class I
  (specific-power mass) and Class II (geometric FC_SPEC model).
- :mod:`.hex` -- geometric heat-exchanger sizing (epsilon-NTU, tube banks, plate-fin).
- :mod:`.ram_air` -- net drag of a ram-air cooling duct.
"""

from .network import (
    ThermalConditions, HeatSource, HeatSink, ConstantHeatSource, CallableHeatSource,
    RamAirSink, ThermalBalance, HeatExchangerNetwork, THERMAL_COMPONENTS,
    register_thermal_component,
)
from .TMS import ThermalManagementSystem, FCThermalManagementResult, ExchangerUnit
from .hex import (
    FluidStream, DesignSpec, FlowArrangement, HEX_Design, effectiveness, ntu_required,
    thermal_solve, PlainTubeBankSizer, FinnedTubeBankSizer, PlateFinSizer,
    HeatExchangerSelector, rate_design, coolprop_available,
)
from .ram_air import ram_air_drag

__all__ = [
    "ThermalConditions", "HeatSource", "HeatSink", "ConstantHeatSource",
    "CallableHeatSource", "RamAirSink", "ThermalBalance", "HeatExchangerNetwork",
    "THERMAL_COMPONENTS", "register_thermal_component",
    "ThermalManagementSystem", "FCThermalManagementResult", "ExchangerUnit",
    "FluidStream", "DesignSpec", "FlowArrangement", "HEX_Design", "effectiveness",
    "ntu_required", "thermal_solve", "PlainTubeBankSizer", "FinnedTubeBankSizer",
    "PlateFinSizer", "HeatExchangerSelector", "rate_design", "coolprop_available",
    "ram_air_drag",
]
