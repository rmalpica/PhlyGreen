"""Ground segments (taxi-out, take-off, taxi-in), the hydrogen reserve in the tank, and the
explicit hydrogen fuel margin."""

import copy
import warnings

import pytest

import PhlyGreen as pg
from PhlyGreen.config import MissionConfig, ConfigError
import _sample_configs as sc

from test_hydrogen import _hydrogen_config


def _design_traditional(mission_extra=None):
    mission = copy.deepcopy(sc.MISSION_INPUT)
    mission.update(mission_extra or {})
    a = pg.build_aircraft()
    a.Configuration, a.AircraftType = 'Traditional', 'ATR'
    a.DesignAircraft(sc.AERODYNAMICS_INPUT, sc.CONSTRAINTS_INPUT, mission,
                     sc.ENERGY_INPUT, sc.MISSION_STAGES, sc.DIVERSION_STAGES)
    return a


@pytest.fixture(scope="module")
def traditional():
    return _design_traditional()


@pytest.fixture(scope="module")
def hydrogen():
    a = pg.build_aircraft()
    a.configure(_hydrogen_config())
    return a


@pytest.mark.slow
def test_start_mass_fraction_follows_from_taxi_out_and_takeoff_fuel(traditional):
    m, w = traditional.mission, traditional.weight
    assert 0 < m.E_taxi_out_takeoff < m.E_ground
    assert m.beta0 == pytest.approx(1.0 - m.E_taxi_out_takeoff / (m.ef * m.WTO), rel=1e-12)
    # a physical taxi + take-off burn is a small fraction of the mission fuel
    assert m.E_ground / m.ef < 0.1 * w.Wf


@pytest.mark.slow
def test_ground_fuel_is_part_of_the_fuel_load(traditional):
    m, w = traditional.mission, traditional.weight
    flown = m.Ef[-1]                       # profile only
    assert w.Wf == pytest.approx((flown + m.E_ground) / m.ef, rel=1e-9)


@pytest.mark.slow
def test_longer_taxi_burns_more_fuel(traditional):
    long_taxi = _design_traditional({'Taxi Out Time': 30.0, 'Taxi In Time': 30.0})
    assert long_taxi.mission.E_ground > traditional.mission.E_ground
    assert long_taxi.weight.WTO > traditional.weight.WTO


@pytest.mark.slow
def test_beta_start_input_is_deprecated_and_ignored(traditional):
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        a = _design_traditional({'Beta start': 0.9})
    assert any(issubclass(r.category, DeprecationWarning) and 'Beta start' in str(r.message)
               for r in rec)
    assert a.weight.WTO == pytest.approx(traditional.weight.WTO, rel=1e-12)


@pytest.mark.slow
def test_hydrogen_tank_holds_the_reserve(hydrogen):
    w = hydrogen.weight
    gi = hydrogen.EnergyInput.get('H2 Gravimetric Index', 0.35)
    assert w.final_reserve > 0
    assert w.WTank == pytest.approx((w.WH2_Fuel + w.final_reserve) * (1 / gi - 1), rel=1e-9)


@pytest.mark.slow
def test_hydrogen_fuel_margin_is_an_explicit_input(hydrogen):
    m, w = hydrogen.mission, hydrogen.weight
    E = m.Ef[-1] + m.E_ground
    assert w.WH2_Fuel == pytest.approx(E / m.ef * 1.05, rel=1e-9)      # default 0.05
    cfg = _hydrogen_config()
    cfg.energy.h2_fuel_margin = 0.0
    a = pg.build_aircraft()
    a.configure(cfg)
    E0 = a.mission.Ef[-1] + a.mission.E_ground
    assert a.weight.WH2_Fuel == pytest.approx(E0 / a.mission.ef, rel=1e-9)
    assert a.weight.WTO < w.WTO


def test_ground_segment_inputs_are_validated():
    with pytest.raises(ConfigError):
        MissionConfig(range_mission=750, range_diversion=220, payload_weight=1, crew_weight=1,
                      taxi_power_fraction=1.5)
    with pytest.raises(ConfigError):
        MissionConfig(range_mission=750, range_diversion=220, payload_weight=1, crew_weight=1,
                      taxi_out_time=-1.0)
    d = MissionConfig(range_mission=750, range_diversion=220, payload_weight=1, crew_weight=1,
                      taxi_out_time=10.0, takeoff_time=1.0).to_dict()
    assert d['Taxi Out Time'] == 10.0 and d['Takeoff Time'] == 1.0
