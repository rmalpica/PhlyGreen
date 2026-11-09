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
    aircraft.PropellerInput = {'Number of Engines': 2}
    aircraft.Configuration = 'Traditional'; aircraft.AircraftType = 'ATR'
    aircraft.weight.Class = 'I'
    aircraft.DesignAircraft(kwargs['AerodynamicsInput'], kwargs['ConstraintsInput'],
                            kwargs['MissionInput'], kwargs['EnergyInput'],
                            kwargs['MissionStages'], kwargs['DiversionStages'])
    return aircraft


def test_class_ii_gt_rating_uses_the_map_lapse():
    """A Class-II gas turbine is rated with the map's own lapse (the ISA pressure ratio of
    the deck); a constant-efficiency one keeps the Ruijgrok density**0.75 lapse."""
    import PhlyGreen.Utilities.Atmosphere as ISA
    import PhlyGreen.Utilities.Units as Units
    from PhlyGreen.Systems.Powertrain.gas_turbine_surrogate import _isa_pressure_ratio
    flags, kwargs = sc.traditional_config()
    for model in ('constant', 'ResponseSurface'):
        energy = dict(kwargs['EnergyInput']); energy['Eta Gas Turbine Model'] = model
        aircraft = pg.build_aircraft()
        aircraft.Configuration = 'Traditional'; aircraft.AircraftType = 'ATR'
        aircraft.ReadInput(kwargs['AerodynamicsInput'], kwargs['ConstraintsInput'],
                           kwargs['MissionInput'], energy, kwargs['MissionStages'],
                           kwargs['DiversionStages'])
        pt = aircraft.powertrain
        for alt in (0.0, 3000.0, 7000.0):
            if model == 'constant':
                ruijgrok = (ISA.atmosphere.RHOstd(alt, 10.0) / ISA.atmosphere.RHOstd(0.0, 10.0)) ** 0.75
                assert pt.PowerLapse(alt, 10.0) == ruijgrok
            else:
                # no DISA (or Mach) dependence, exactly as in the deck
                assert pt.PowerLapse(alt, 10.0) == _isa_pressure_ratio(Units.mToft(alt))
        # without 'GT Design Power' the Class-II nominal follows the sized rating
        assert pt.gt_design_power_follows_rating == (model == 'ResponseSurface')


@pytest.mark.slow
def test_class_ii_gt_nominal_follows_the_rating_and_is_never_power_limited():
    flags, kwargs = sc.traditional_config()
    energy = dict(kwargs['EnergyInput']); energy['Eta Gas Turbine Model'] = 'ResponseSurface'
    aircraft = pg.build_aircraft()
    aircraft.PropellerInput = {'Number of Engines': 2}
    aircraft.Configuration = 'Traditional'; aircraft.AircraftType = 'ATR'; aircraft.weight.Class = 'I'
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        aircraft.DesignAircraft(kwargs['AerodynamicsInput'], kwargs['ConstraintsInput'],
                                kwargs['MissionInput'], energy,
                                kwargs['MissionStages'], kwargs['DiversionStages'])
    pt = aircraft.powertrain
    assert pt.gt_design_power == pytest.approx(pt.engineRating, rel=1e-6)
    report = pt.report_class_ii_sizing()['gas turbine']
    assert report['n_power_limited_points'] == 0 and not report['power_limited']
    assert report['worst_load_ratio'] == pytest.approx(1.0, abs=1e-5)   # the sizing point
    messages = " ".join(str(w.message) for w in caught)
    assert "undersized" not in messages and "not the weighed one" not in messages


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

    # Size to the nominal needed to avoid power-limiting (altitude-aware), then check.
    tentative = _traditional_class_ii_gt(p_nominal).powertrain.report_class_ii_sizing()['gas turbine']
    aircraft = _traditional_class_ii_gt(1.05 * tentative['min_nominal'])
    report = aircraft.powertrain.report_class_ii_sizing()['gas turbine']
    assert report['status'] != 'UNDERSIZED'
    assert not report['power_limited']
    assert report['worst_load_ratio'] <= 1.0 + 1e-6


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


@pytest.mark.slow
def test_nominal_far_from_the_sized_rating_warns():
    """The engine mass follows engineRating, the map 'GT Design Power': warn when they differ."""
    aircraft = _traditional_class_ii_gt(8.0e6)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        report = aircraft.powertrain.report_class_ii_sizing()['gas turbine']
    assert report['rating'] == aircraft.powertrain.engineRating
    assert abs(report['nominal'] / report['rating'] - 1.0) > 0.05
    assert any("not the weighed one" in str(w.message) for w in caught)
    # a nominal equal to the rating does not warn
    aircraft.powertrain.gt_design_power = aircraft.powertrain.engineRating
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        aircraft.powertrain.report_class_ii_sizing()
    assert not any("not the weighed one" in str(w.message) for w in caught)


def test_rbf_propeller_rpm_reaches_the_model(monkeypatch):
    """'Propeller RPM' (EnergyConfig.propeller_rpm) sets the RBF propeller surrogate rpm."""
    from PhlyGreen.Systems.Powertrain import efficiency
    built = {}

    class FakePropeller:
        def __init__(self, rpm=1200.0, n_engines=1, surrogate=None):
            built['rpm'], built['n_engines'] = rpm, n_engines

        def eta(self, op):
            return 0.85
    monkeypatch.setattr(efficiency, 'PropellerSurrogateEfficiency', FakePropeller)
    flags, kwargs = sc.traditional_config()
    energy = dict(kwargs['EnergyInput'])
    energy['Eta Propulsive Model'] = 'Surrogate'
    energy['Propeller RPM'] = 1050.0
    aircraft = pg.build_aircraft()
    aircraft.Configuration = 'Traditional'; aircraft.AircraftType = 'ATR'
    aircraft.ReadInput(kwargs['AerodynamicsInput'], kwargs['ConstraintsInput'],
                       kwargs['MissionInput'], energy, kwargs['MissionStages'],
                       kwargs['DiversionStages'])
    assert built == {'rpm': 1050.0, 'n_engines': 2}
