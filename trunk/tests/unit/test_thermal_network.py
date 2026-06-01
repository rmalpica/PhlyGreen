"""Unit tests for the heat-exchanger network scaffold."""

import pytest

from PhlyGreen.Systems.Thermal import (
    ThermalConditions, ConstantHeatSource, CallableHeatSource, RamAirSink,
    HeatExchangerNetwork, HeatSource, THERMAL_COMPONENTS, register_thermal_component,
)


def test_sources_and_sinks_sum_in_balance():
    net = HeatExchangerNetwork()
    net.add_source(ConstantHeatSource('fc', 10_000.0))
    net.add_source(ConstantHeatSource('motor', 2_000.0))
    net.add_sink(RamAirSink('ram', UA=500.0, T_coolant=350.0))

    cond = ThermalConditions(altitude=0.0, T_ambient=288.15)
    balance = net.solve(cond)
    assert balance.total_heat == pytest.approx(12_000.0)
    # capacity = UA * (T_coolant - T_ambient) = 500 * (350 - 288.15)
    assert balance.sink_capacity == pytest.approx(500.0 * (350.0 - 288.15))


def test_feasible_when_capacity_exceeds_load():
    net = HeatExchangerNetwork()
    net.add_source(ConstantHeatSource('fc', 1_000.0))
    net.add_sink(RamAirSink('ram', UA=500.0, T_coolant=350.0))
    balance = net.solve(ThermalConditions(T_ambient=288.15))
    assert balance.feasible
    assert balance.unmet == 0.0


def test_infeasible_reports_unmet_heat():
    net = HeatExchangerNetwork()
    net.add_source(ConstantHeatSource('fc', 1_000_000.0))
    net.add_sink(RamAirSink('ram', UA=500.0, T_coolant=350.0))
    balance = net.solve(ThermalConditions(T_ambient=288.15))
    assert not balance.feasible
    assert balance.unmet > 0


def test_callable_source_depends_on_conditions():
    src = CallableHeatSource('fc', lambda c: 100.0 * c.velocity)
    assert src.heat_load(ThermalConditions(velocity=120.0)) == pytest.approx(12_000.0)


def test_ram_air_capacity_falls_at_high_ambient():
    sink = RamAirSink('ram', UA=500.0, T_coolant=350.0)
    cold = sink.capacity(ThermalConditions(T_ambient=250.0))
    hot = sink.capacity(ThermalConditions(T_ambient=340.0))
    assert cold > hot >= 0


def test_register_custom_component():
    @register_thermal_component('AvionicsHeatSource')
    class AvionicsHeatSource(HeatSource):
        def heat_load(self, conditions):
            return 500.0

    try:
        assert 'AvionicsHeatSource' in THERMAL_COMPONENTS
        assert THERMAL_COMPONENTS['AvionicsHeatSource']('av').heat_load(ThermalConditions()) == 500.0
    finally:
        del THERMAL_COMPONENTS['AvionicsHeatSource']
