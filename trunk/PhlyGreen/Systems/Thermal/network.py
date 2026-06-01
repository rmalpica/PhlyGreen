"""Scaffold for a future heat-exchanger network (thermal-management) module.

Hydrogen-electric aircraft must reject large amounts of low-grade heat — from the fuel-cell
stack, power electronics, motors — and can use the cryogenic fuel and ram air as heat
sinks. A full thermal-management module would size a network of heat exchangers, coolant
loops and pumps. This module provides the **interfaces and a minimal balance solver** that
such a module will build on, so the rest of the code can already register heat sources
(e.g. the fuel cell's ``Q_thermal``, the tank's heat leak) and sinks today.

Design (mirrors the powertrain graph and the efficiency-model registry):

* :class:`ThermalConditions` — the operating point (altitude, speed, ambient temperature).
* :class:`HeatSource` — something that produces heat to reject at a temperature.
* :class:`HeatSink` — something that can absorb heat (ram-air cooler, fuel heat sink, ...).
* :class:`HeatExchangerNetwork` — collects sources and sinks and solves a heat balance.
* concrete helpers (:class:`ConstantHeatSource`, :class:`CallableHeatSource`,
  :class:`RamAirSink`) plus a registry for future custom components.

The solver here is intentionally simple (does total rejected heat fit within total sink
capacity?). It is the seam where a detailed effectiveness-NTU / coolant-loop model will go.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, List


@dataclass
class ThermalConditions:
    """Operating point at which the thermal network is evaluated."""
    altitude: float = 0.0
    velocity: float = 0.0
    T_ambient: float = 288.15   # [K]


class HeatSource(ABC):
    """A component that produces heat to be rejected, at a characteristic temperature."""

    def __init__(self, name, T_source=350.0):
        self.name = name
        self.T_source = T_source     # [K], the temperature the heat is available at

    @abstractmethod
    def heat_load(self, conditions: ThermalConditions) -> float:
        """Heat to reject at ``conditions`` [W]."""


class HeatSink(ABC):
    """A component that can absorb heat."""

    def __init__(self, name):
        self.name = name

    @abstractmethod
    def capacity(self, conditions: ThermalConditions) -> float:
        """Maximum heat the sink can absorb at ``conditions`` [W]."""


# --- concrete helpers -------------------------------------------------------

class ConstantHeatSource(HeatSource):
    """A fixed heat load (W), independent of the operating point."""

    def __init__(self, name, load, T_source=350.0):
        super().__init__(name, T_source)
        self.load = load

    def heat_load(self, conditions):
        return self.load


class CallableHeatSource(HeatSource):
    """Wrap any ``fn(ThermalConditions) -> watts`` (e.g. the fuel cell's instantaneous heat)."""

    def __init__(self, name, fn: Callable[[ThermalConditions], float], T_source=350.0):
        super().__init__(name, T_source)
        self._fn = fn

    def heat_load(self, conditions):
        return float(self._fn(conditions))


class RamAirSink(HeatSink):
    """A simple ram-air cooler: capacity ~ UA * (coolant - ambient) temperature difference.

    Args:
        UA: overall conductance [W/K].
        T_coolant: coolant-side temperature [K] (the hot side of the exchanger).
    """

    def __init__(self, name, UA, T_coolant=350.0):
        super().__init__(name)
        self.UA = UA
        self.T_coolant = T_coolant

    def capacity(self, conditions):
        return self.UA * max(self.T_coolant - conditions.T_ambient, 0.0)


@dataclass
class ThermalBalance:
    """Result of solving the network at one operating point."""
    total_heat: float       # [W] produced by all sources
    sink_capacity: float    # [W] available across all sinks
    rejected: float         # [W] actually rejected
    unmet: float            # [W] heat that could not be rejected

    @property
    def feasible(self) -> bool:
        return self.unmet <= 1e-9


class HeatExchangerNetwork:
    """Collects heat sources and sinks and solves a (simple) heat balance.

    This is the extension point for a future detailed thermal-management module: replace
    :meth:`solve` with an effectiveness-NTU network / coolant-loop model while keeping the
    same source/sink interfaces.
    """

    def __init__(self):
        self.sources: List[HeatSource] = []
        self.sinks: List[HeatSink] = []

    def add_source(self, source: HeatSource):
        self.sources.append(source)
        return self

    def add_sink(self, sink: HeatSink):
        self.sinks.append(sink)
        return self

    def solve(self, conditions: ThermalConditions) -> ThermalBalance:
        total = sum(s.heat_load(conditions) for s in self.sources)
        capacity = sum(k.capacity(conditions) for k in self.sinks)
        rejected = min(total, capacity)
        return ThermalBalance(total_heat=total, sink_capacity=capacity,
                              rejected=rejected, unmet=max(total - capacity, 0.0))

    @classmethod
    def from_aircraft(cls, aircraft, T_source=None):
        """Build a starter network from a designed aircraft's heat sources.

        Adds the fuel cell's thermal load (if present) as a source. Sinks are not added
        automatically — a future module will size them; for now add e.g. a
        :class:`RamAirSink`. This shows the intended wiring without committing to physics.
        """
        net = cls()
        fc = getattr(aircraft, 'fuelcell', None)
        if fc is not None and getattr(fc, 'Q_thermal', 0.0):
            t_src = T_source if T_source is not None else getattr(fc, 'T_op', 350.0)
            net.add_source(ConstantHeatSource('fuel_cell', float(fc.Q_thermal), T_source=t_src))
        return net


# --- registry for future custom thermal components --------------------------

THERMAL_COMPONENTS = {
    'ConstantHeatSource': ConstantHeatSource,
    'CallableHeatSource': CallableHeatSource,
    'RamAirSink': RamAirSink,
}


def register_thermal_component(name):
    """Class decorator registering a new thermal component type (future extension point)."""
    def _register(cls):
        THERMAL_COMPONENTS[name] = cls
        return cls
    return _register
