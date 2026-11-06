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


# --- battery share of the ground segments (taxi split, take-off split, Class I and II) -------

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "examples"))
from common import hybrid_config, fuelcell_battery_config      # noqa: E402


def _with_ground_split(cfg, takeoff_phi=0.0, taxi_phi=None):
    for seg in cfg.mission_stages.segments:
        if seg.name == 'Takeoff':
            seg.phi = takeoff_phi
    cfg.mission.taxi_phi = taxi_phi
    return cfg


def _design(cfg):
    a = pg.build_aircraft()
    a.configure(cfg)
    return a


@pytest.fixture(scope="module")
def hybrid_fuel_taxi():
    return _design(_with_ground_split(hybrid_config('I')))


@pytest.fixture(scope="module")
def hybrid_electric_taxi():
    return _design(_with_ground_split(hybrid_config('I'), taxi_phi=1.0))


def test_ground_split_inputs_are_validated_and_serialized():
    base = dict(range_mission=750, range_diversion=220, payload_weight=1, crew_weight=1)
    with pytest.raises(ConfigError):
        MissionConfig(**base, taxi_phi=1.5)
    with pytest.raises(ConfigError):
        MissionConfig(**base, takeoff_power_fraction=-0.1)
    d = MissionConfig(**base, taxi_phi=1.0, takeoff_power_fraction=0.9).to_dict()
    assert d['Taxi Supplied Power Ratio'] == 1.0 and d['Takeoff Power Fraction'] == 0.9


def test_taxi_split_needs_a_battery():
    mission = copy.deepcopy(sc.MISSION_INPUT)
    mission['Taxi Supplied Power Ratio'] = 1.0
    a = pg.build_aircraft()
    a.Configuration, a.AircraftType = 'Traditional', 'ATR'
    with pytest.raises(ValueError, match='no battery'):
        a.ReadInput(sc.AERODYNAMICS_INPUT, sc.CONSTRAINTS_INPUT, mission,
                    sc.ENERGY_INPUT, sc.MISSION_STAGES, sc.DIVERSION_STAGES)


@pytest.mark.slow
def test_fuel_taxi_draws_no_battery(hybrid_fuel_taxi):
    m = hybrid_fuel_taxi.mission
    assert m.EBat_ground == 0.0 and m.Taxi_PBat == 0.0


@pytest.mark.slow
def test_electric_taxi_moves_ground_energy_to_the_battery(hybrid_fuel_taxi, hybrid_electric_taxi):
    m, w = hybrid_electric_taxi.mission, hybrid_electric_taxi.weight
    # the battery covers the whole taxi: its energy is the taxi power over both taxi legs ...
    (_, t_out, P_out, _, _), (_, t_to, P_to, _, _) = m._ground_battery_legs_out
    (_, t_in, P_in, _, _), = m._ground_battery_legs_in
    assert P_to == 0.0 and P_out == P_in > 0
    assert m.EBat_ground == pytest.approx(P_out * (t_out + t_in), rel=1e-12)
    # ... it is part of the battery energy the weight loop sizes on ...
    assert w.TotalEnergies[1] == pytest.approx(m.EBat[-1] + m.EBat_ground, rel=1e-12)
    # ... its power enters the battery peak power ...
    assert m.Max_PBat >= m.Taxi_PBat > 0
    # ... and the ground fuel drops to the take-off run alone
    assert m.E_ground < hybrid_fuel_taxi.mission.E_ground
    assert m.E_ground == pytest.approx(m.E_taxi_out_takeoff, rel=1e-12)    # no taxi-in fuel
    assert w.WBat > hybrid_fuel_taxi.weight.WBat


@pytest.mark.slow
def test_taxi_split_defaults_to_the_takeoff_split():
    a = _design(_with_ground_split(hybrid_config('I'), takeoff_phi=0.3))
    m = a.mission
    assert m.Taxi_PBat > 0 and m.Takeoff_PBat > 0
    assert m.Takeoff_PBat <= m.TO_PBat                  # the take-off run is within the sizing case
    b = _design(_with_ground_split(hybrid_config('I'), takeoff_phi=0.3, taxi_phi=0.3))
    assert b.weight.WTO == pytest.approx(a.weight.WTO, rel=1e-12)


@pytest.mark.slow
def test_takeoff_power_fraction_scales_the_takeoff_run(hybrid_fuel_taxi):
    derated = hybrid_config('I')
    derated.mission.takeoff_power_fraction = 0.8
    d = _design(_with_ground_split(derated))
    assert d.mission.E_taxi_out_takeoff < hybrid_fuel_taxi.mission.E_taxi_out_takeoff


@pytest.mark.slow
def test_fuel_cell_battery_electric_taxi():
    base = _design(_with_ground_split(fuelcell_battery_config()))
    a = _design(_with_ground_split(fuelcell_battery_config(), taxi_phi=1.0))
    m = a.mission
    assert base.mission.EBat_ground == 0.0
    assert m.EBat_ground > 0
    assert a.weight.TotalEnergies[1] == pytest.approx(m.EBat + m.EBat_ground, rel=1e-12)
    assert m.Max_PBat >= m.Taxi_PBat > 0


@pytest.mark.slow
def test_class_ii_pack_starts_the_climb_after_taxi_out():
    fuel = _design(_with_ground_split(hybrid_config('II')))
    elec = _design(_with_ground_split(hybrid_config('II'), taxi_phi=1.0))
    # spent charge [A s] at the start of the climb
    assert fuel.mission.integral_solution[0].y[3][0] == 0.0
    assert elec.mission.integral_solution[0].y[3][0] > 0.0
    assert elec.weight.TotalEnergies[1] > fuel.weight.TotalEnergies[1]
    assert elec.battery.pack_weight >= fuel.battery.pack_weight
