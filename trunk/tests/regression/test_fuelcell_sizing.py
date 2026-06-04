"""Tests for the fuel-cell power-adequacy check (mirrors the Class-II GT/EM check).

The fuel cell is auto-sized to the worst-case propulsive demand, but its *available* net
power falls with altitude (the air-system draws more), so a stack can still be power-limited.
``FuelCell.report_sizing`` walks the flown mission and flags that shortfall — without it,
``ComputePRatio`` silently substitutes an analytical fallback.
"""

import warnings

import pytest

import PhlyGreen as pg
import _sample_configs as sc


def _hydrogen_aircraft():
    flags, kwargs = sc.hydrogen_config()
    aircraft = pg.build_aircraft()
    aircraft.Configuration = flags['Configuration']
    aircraft.HybridType = flags['HybridType']
    aircraft.AircraftType = flags['AircraftType']
    aircraft.weight.Class = flags['weight_class']
    aircraft.DesignAircraft(kwargs['AerodynamicsInput'], kwargs['ConstraintsInput'],
                            kwargs['MissionInput'], kwargs['EnergyInput'],
                            kwargs['MissionStages'], kwargs['DiversionStages'])
    return aircraft


@pytest.mark.slow
def test_autosized_fuel_cell_is_adequate():
    # The default auto-sized stack should comfortably meet the mission (no warning).
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        aircraft = _hydrogen_aircraft()
    report = aircraft.fuelcell.report_sizing()
    assert report['status'] != 'UNDERSIZED'
    assert not report['power_limited']
    assert 0.0 < report['worst_load_ratio'] <= 1.0 + 1e-6
    assert not any("fuel cell is undersized" in str(w.message) for w in caught)


@pytest.mark.slow
def test_undersized_fuel_cell_warns():
    aircraft = _hydrogen_aircraft()
    fc = aircraft.fuelcell
    # Shrink the stack well below the take-off peak and re-fly, then check it is flagged.
    fc.SizeForPropulsivePower(0.45 * aircraft.mission.TO_PP)
    aircraft.mission.EvaluateMission(aircraft.weight.WTO)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        report = fc.report_sizing()
    assert report['status'] == 'UNDERSIZED'
    assert report['power_limited']
    assert report['worst_load_ratio'] > 1.0
    assert report['min_rating'] > fc.P_fc_rated
    assert any("undersized" in str(w.message) for w in caught)
