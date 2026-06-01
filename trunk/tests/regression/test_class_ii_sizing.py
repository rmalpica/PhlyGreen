"""Tests for Class-II GT/EM nominal-power sizing and the over/under-size check."""

import warnings

import pytest

import PhlyGreen as pg
import _sample_configs as sc


def _traditional_class_ii_gt(gt_design_power):
    flags, kwargs = sc.traditional_config()
    energy = dict(kwargs['EnergyInput'])
    energy['Eta Gas Turbine Model'] = 'ResponseSurface'
    energy['GT Design Power'] = gt_design_power
    kwargs = dict(kwargs); kwargs['EnergyInput'] = energy
    aircraft = pg.build_aircraft()
    aircraft.Configuration = 'Traditional'; aircraft.AircraftType = 'ATR'
    aircraft.weight.Class = 'I'
    aircraft.DesignAircraft(kwargs['AerodynamicsInput'], kwargs['ConstraintsInput'],
                            kwargs['MissionInput'], kwargs['EnergyInput'],
                            kwargs['MissionStages'], kwargs['DiversionStages'])
    return aircraft


def test_class_ii_gt_requires_nominal_power():
    flags, kwargs = sc.traditional_config()
    energy = dict(kwargs['EnergyInput']); energy['Eta Gas Turbine Model'] = 'ResponseSurface'
    aircraft = pg.build_aircraft()
    aircraft.Configuration = 'Traditional'; aircraft.AircraftType = 'ATR'; aircraft.weight.Class = 'I'
    with pytest.raises(ValueError, match="GT Design Power"):
        aircraft.DesignAircraft(kwargs['AerodynamicsInput'], kwargs['ConstraintsInput'],
                                kwargs['MissionInput'], energy,
                                kwargs['MissionStages'], kwargs['DiversionStages'])


@pytest.mark.slow
def test_adequate_nominal_is_not_undersized():
    # First a cheap estimate of DesignPW*WTO, then size the GT to it.
    pre = pg.build_aircraft()
    flags, kwargs = sc.traditional_config()
    pre.Configuration = 'Traditional'; pre.AircraftType = 'ATR'; pre.weight.Class = 'I'
    pre.DesignAircraft(kwargs['AerodynamicsInput'], kwargs['ConstraintsInput'],
                       kwargs['MissionInput'], kwargs['EnergyInput'],
                       kwargs['MissionStages'], kwargs['DiversionStages'])
    p_nominal = pre.DesignPW * pre.weight.WTO

    aircraft = _traditional_class_ii_gt(p_nominal)
    report = aircraft.powertrain.report_class_ii_sizing()['gas turbine']
    assert report['status'] != 'UNDERSIZED'
    assert report['actual'] <= report['nominal']


@pytest.mark.slow
def test_undersized_nominal_warns():
    pre = pg.build_aircraft()
    flags, kwargs = sc.traditional_config()
    pre.Configuration = 'Traditional'; pre.AircraftType = 'ATR'; pre.weight.Class = 'I'
    pre.DesignAircraft(kwargs['AerodynamicsInput'], kwargs['ConstraintsInput'],
                       kwargs['MissionInput'], kwargs['EnergyInput'],
                       kwargs['MissionStages'], kwargs['DiversionStages'])
    p_small = 0.5 * pre.DesignPW * pre.weight.WTO

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        aircraft = _traditional_class_ii_gt(p_small)
    assert any("undersized" in str(w.message) for w in caught)
    assert aircraft.powertrain.report_class_ii_sizing()['gas turbine']['status'] == 'UNDERSIZED'
