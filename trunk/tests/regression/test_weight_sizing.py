"""Regression tests for weight-loop sizing details: the final-reserve rule and the
Class-II battery thermal-management (cooling) mass."""

import copy

import pytest

import _sample_configs as sc
from conftest import design_from_config


@pytest.mark.slow
def test_final_reserve_recomputes_on_converged_fuel():
    # With no Contingency Fuel specified, the reserve falls back to 5% of the mission fuel —
    # recomputed each iteration (regression for the bug where it froze at the first Brent probe
    # and collapsed to a few kg).
    flags, kwargs = sc.traditional_config()
    kwargs = copy.deepcopy(kwargs)
    kwargs['EnergyInput']['Contingency Fuel'] = 0
    aircraft = design_from_config(flags, kwargs)
    assert aircraft.weight.final_reserve == pytest.approx(0.05 * aircraft.weight.Wf, rel=1e-3)
    assert aircraft.weight.final_reserve > 50.0          # not the frozen ~5 kg


@pytest.mark.slow
def test_final_reserve_uses_fixed_contingency_when_given():
    flags, kwargs = sc.traditional_config()                # specifies Contingency Fuel = 130
    aircraft = design_from_config(flags, kwargs)
    assert aircraft.weight.final_reserve == pytest.approx(130.0)


@pytest.mark.slow
def test_classII_battery_cooling_mass_in_wto():
    # A Class-II battery carries an in-flight thermal-management (cooling) mass, sized from the
    # peak in-flight battery heat and included in the take-off-weight balance.
    aircraft = design_from_config(*sc.hybrid_parallel_config())   # Class-II battery
    assert aircraft.mission.Max_Bat_Thermal_Pwr > 0
    assert aircraft.weight.WHeat_Exchanger > 0
