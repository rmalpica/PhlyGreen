"""Tests for the cryogenic LH2 tank model.

Requires CoolProp (para-hydrogen properties); skipped automatically if it is not
installed. Covers tank sizing and the transient time_step physics (self-pressurization,
venting at P_max, heater at P_min, mass depletion, vent accounting), plus a full hydrogen
design + tracked mission.
"""

import copy
import inspect
import sys
import warnings

import numpy as np
import pytest

pytest.importorskip("CoolProp")

import PhlyGreen as pg
import PhlyGreen.Systems.Tank.Tank as tank_module
from PhlyGreen.Systems.Tank import LH2_Tank, TANK_Database, get_isa_atmosphere
from PhlyGreen.Utilities.Atmosphere import atmosphere
from PhlyGreen.config import (
    AircraftConfig, AerodynamicsConfig, ConstraintsConfig, MissionConfig,
    EnergyConfig, StagesConfig, TankConfig, ConfigError,
)
import _sample_configs as sc


class _FakeMission:
    def __init__(self, DISA):
        self.DISA = DISA


class _FakeAircraft:
    """Minimal stand-in: the tank constructor only needs ``TankInput`` (and, for the
    ambient temperature, an optional ``mission.DISA``)."""
    def __init__(self, tankinput, DISA=None):
        self.TankInput = tankinput
        if DISA is not None:
            self.mission = _FakeMission(DISA)


TANK_INPUT = {'Max Diameter': 2.4, 'Number of Tanks': 1, 'Tank Model': 'Svensson_Default'}


def _make_tank(capacity_kg=500.0):
    return LH2_Tank(capacity_kg=capacity_kg, aircraft=_FakeAircraft(dict(TANK_INPUT)))


# --- sizing -----------------------------------------------------------------

def test_tank_sizing_is_physical():
    tank = _make_tank(500.0)
    assert tank.mass_system_empty > 0
    assert 0.0 < tank.gravimetric_index < 1.0
    assert tank.shape in ("Sphere", "Cylinder")
    assert tank.P_min < tank.P_max
    assert tank.D_outer > 0


def test_more_hydrogen_needs_a_bigger_tank():
    small = _make_tank(300.0)
    big = _make_tank(900.0)
    assert big.mass_system_empty > small.mass_system_empty


# --- transient time_step physics --------------------------------------------

def test_self_pressurization_and_venting():
    tank = _make_tank(500.0)
    P_start = tank.P_curr / 1e5
    # No hydrogen drawn: heat leak alone raises the pressure until the vent opens at P_max.
    for _ in range(800):
        tank.time_step(dt=10.0, m_dot_req_total=0.0, altitude=11000.0)
    P = np.array(tank.history['P'])
    assert P[10] > P_start                                        # self-pressurizes
    assert P.max() == pytest.approx(tank.P_max / 1e5, rel=1e-6)   # reaches the vent limit
    assert P.max() <= tank.P_max / 1e5 + 1e-6                     # never exceeds it
    assert tank.cum_vented_mass > 0                               # gas was vented


def test_drawing_hydrogen_depletes_mass():
    tank = _make_tank(500.0)
    m0 = tank.m_curr
    for _ in range(50):
        tank.time_step(dt=10.0, m_dot_req_total=0.05, altitude=6000.0)
    assert tank.m_curr < m0
    masses = np.array(tank.history['m_tot'])
    assert np.all(np.diff(masses) <= 1e-9)                        # monotone non-increasing


def test_heater_maintains_minimum_pressure():
    tank = _make_tank(500.0)
    # Heavy draw with low heat leak pulls pressure down -> heater must engage to hold P_min.
    for _ in range(60):
        tank.time_step(dt=5.0, m_dot_req_total=0.5, altitude=0.0)
    P = np.array(tank.history['P'])
    assert P.min() >= tank.P_min / 1e5 - 1e-6                     # never below P_min
    assert max(tank.history['Q_heater']) > 0                      # heater was used


# --- full hydrogen design with the tank -------------------------------------

def _hydrogen_config_with_tank():
    energy = EnergyConfig(
        Ef=141.87e6, eta_gearbox=0.96, eta_pmad=0.99, eta_electric_motor=0.96,
        eta_gas_turbine_model='constant', eta_gas_turbine=0.22,
        eta_propulsive_model='constant', eta_propulsive=0.9,
        specific_power_powertrain=[3900, 5000], specific_power_pmad=10000,
        fc_model='PEMFC_GoodPerformance', i_rated=2.5, v_cell_design=0.5,
        stack_power_density=3000, bop_mass_ratio=0.40,
    )
    return AircraftConfig(
        configuration='Hydrogen', aircraft_type='ATR', weight_class='I',
        aerodynamics=AerodynamicsConfig.from_dict(sc.AERODYNAMICS_INPUT),
        constraints=ConstraintsConfig.from_dict(sc.CONSTRAINTS_INPUT),
        mission=MissionConfig.from_dict(sc.MISSION_INPUT), energy=energy,
        mission_stages=StagesConfig.from_dict(sc.MISSION_STAGES),
        diversion_stages=StagesConfig.from_dict(sc.DIVERSION_STAGES),
        tank=TankConfig(max_diameter=2.4, number_of_tanks=1, tank_model='Svensson_Default'),
    )


@pytest.mark.slow
def test_hydrogen_design_with_tank_and_tracked_mission():
    aircraft = pg.build_aircraft()
    aircraft.configure(_hydrogen_config_with_tank())
    assert aircraft.tank is not None
    assert aircraft.weight.WTank == pytest.approx(aircraft.tank.mass_system_empty)

    aircraft.mission.track_tank = True
    aircraft.mission.EvaluateMission(aircraft.weight.WTO)
    h = aircraft.tank.history
    P = np.array(h['P'])
    assert len(h['t']) > 10
    # pressure regulated within [P_min, P_max] throughout the mission
    assert P.min() >= aircraft.tank.P_min / 1e5 - 1e-6
    assert P.max() <= aircraft.tank.P_max / 1e5 + 1e-6
    # hydrogen is consumed over the mission
    assert h['m_tot'][-1] < h['m_tot'][0]


# --- import, CoolProp fallbacks, atmosphere ----------------------------------

def test_database_is_imported_package_relative():
    source = inspect.getsource(tank_module)
    assert "Serbatoio_H2" not in source
    assert tank_module.TANK_Database is TANK_Database


def test_weight_warns_and_resets_tank_when_tank_module_cannot_be_imported(monkeypatch):
    aircraft = pg.build_aircraft()
    aircraft.TankInput = dict(TANK_INPUT)
    aircraft.tank = "stale tank from an earlier design"
    # Simulate a missing CoolProp: the Tank package import then raises ImportError.
    monkeypatch.setitem(sys.modules, "CoolProp", None)
    monkeypatch.setitem(sys.modules, "CoolProp.CoolProp", None)
    monkeypatch.delitem(sys.modules, "PhlyGreen.Systems.Tank", raising=False)
    monkeypatch.delitem(sys.modules, "PhlyGreen.Systems.Tank.Tank", raising=False)
    with pytest.warns(RuntimeWarning, match="TankConfig is given"):
        tank_class = aircraft.weight._physics_tank_class(0.35)
    assert tank_class is None
    assert aircraft.tank is None


def test_weight_tank_class_without_tank_input_resets_tank_silently():
    aircraft = pg.build_aircraft()
    aircraft.TankInput = None
    aircraft.tank = "stale tank from an earlier design"
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert aircraft.weight._physics_tank_class(0.35) is None
    assert aircraft.tank is None
    aircraft.TankInput = dict(TANK_INPUT)
    assert aircraft.weight._physics_tank_class(0.35) is LH2_Tank


def test_coolprop_failure_warns_in_sizing_and_time_step(monkeypatch):
    def failing_props(*args):
        raise ValueError("simulated CoolProp failure")
    monkeypatch.setattr(tank_module.CP, "PropsSI", failing_props)
    with pytest.warns(RuntimeWarning, match="fixed 70 kg/m"):
        tank = _make_tank(500.0)
    with pytest.warns(RuntimeWarning, match="fixed fallback properties"):
        tank.time_step(dt=10.0, m_dot_req_total=0.01, altitude=0.0)


def test_ambient_temperature_uses_package_isa_and_mission_disa():
    tank = LH2_Tank(capacity_kg=500.0, aircraft=_FakeAircraft(dict(TANK_INPUT), DISA=15.0))
    for alt in (0.0, 5000.0, 15000.0):
        assert tank._ambient_temperature(alt) == pytest.approx(atmosphere.Tstd(alt) + 15.0)
    # No mission: ISA (DISA = 0); above the tropopause the temperature is the ISA 216.65 K.
    assert _make_tank(500.0)._ambient_temperature(15000.0) == pytest.approx(216.65)
    T, P = get_isa_atmosphere(15000.0, DISA=10.0)
    assert T == pytest.approx(226.65)
    assert P == pytest.approx(atmosphere.Pstd(15000.0))


def test_mission_disa_raises_the_heat_leak():
    cold = LH2_Tank(capacity_kg=500.0, aircraft=_FakeAircraft(dict(TANK_INPUT), DISA=0.0))
    hot = LH2_Tank(capacity_kg=500.0, aircraft=_FakeAircraft(dict(TANK_INPUT), DISA=20.0))
    cold.time_step(dt=10.0, m_dot_req_total=0.0, altitude=3000.0)
    hot.time_step(dt=10.0, m_dot_req_total=0.0, altitude=3000.0)
    assert hot.history['Q_in'][0] > cold.history['Q_in'][0]


# --- structure ----------------------------------------------------------------

def test_jacket_buckling_uses_the_jacket_radius():
    tank = _make_tank(500.0)
    r_jacket = tank.r_inner + max(tank.t_wall_cyl, tank.t_wall_sphere) + tank.insulation_gap
    expected = r_jacket * np.sqrt(2.0 * 101325.0 * tank.sf_outer**2
                                  / (tank.buckling_knockdown * tank.E_al))
    assert tank.t_wall_outer_sphere == pytest.approx(max(expected, 0.0008))
    assert tank.t_wall_outer_sphere > tank.r_inner * np.sqrt(
        2.0 * 101325.0 * tank.sf_outer**2 / (tank.buckling_knockdown * tank.E_al))


def _with_model(monkeypatch, **changes):
    """Register a modified copy of the default tank model and return its TankInput."""
    params = dict(TANK_Database['Svensson_Default'])
    params.update(changes)
    monkeypatch.setitem(TANK_Database, 'Test_Model', params)
    return {'Max Diameter': 2.4, 'Number of Tanks': 1, 'Tank Model': 'Test_Model'}


def test_poisson_ratio_is_not_required(monkeypatch):
    tank_input = _with_model(monkeypatch)
    del TANK_Database['Test_Model']['nu_al']
    tank = LH2_Tank(capacity_kg=500.0, aircraft=_FakeAircraft(tank_input))
    assert tank.mass_system_empty == pytest.approx(_make_tank(500.0).mass_system_empty)


def test_low_database_minimum_pressure_is_raised_with_a_warning(monkeypatch):
    tank_input = _with_model(monkeypatch, min_p_bar=1.0)
    with pytest.warns(RuntimeWarning, match="1.2 bar floor"):
        tank = LH2_Tank(capacity_kg=500.0, aircraft=_FakeAircraft(tank_input))
    assert tank.P_min == pytest.approx(1.2e5)


def test_outer_diameter_is_checked_against_max_diameter(monkeypatch):
    # A 0.2 m insulation gap does not fit in the 0.15 m clearance at the radius limit.
    tank_input = _with_model(monkeypatch, insulation_gap=0.2)
    with pytest.raises(ValueError, match="exceeds 'Max Diameter'"):
        LH2_Tank(capacity_kg=900.0, aircraft=_FakeAircraft(tank_input))


def test_default_tank_respects_max_diameter():
    for capacity in (100.0, 500.0, 1500.0):
        tank = _make_tank(capacity)
        assert tank.D_outer <= TANK_INPUT['Max Diameter']


# --- number of tanks ------------------------------------------------------------

def test_number_of_tanks_is_capped():
    small = {'Max Diameter': 1.4, 'Number of Tanks': 1, 'Tank Model': 'Svensson_Default'}
    capped = LH2_Tank(capacity_kg=440.0, aircraft=_FakeAircraft(dict(small)))
    assert capped.n_tanks <= tank_module.DEFAULT_MAX_NUMBER_OF_TANKS
    uncapped = LH2_Tank(capacity_kg=440.0,
                        aircraft=_FakeAircraft(dict(small, **{'Max Number of Tanks': None})))
    assert uncapped.n_tanks > tank_module.DEFAULT_MAX_NUMBER_OF_TANKS


def test_aspect_limit_at_the_cap_keeps_the_cylinder_and_warns():
    tank_input = {'Max Diameter': 1.4, 'Number of Tanks': 1, 'Tank Model': 'Svensson_Default',
                  'Max Number of Tanks': 1}
    with pytest.warns(RuntimeWarning, match="capped"):
        tank = LH2_Tank(capacity_kg=1500.0, aircraft=_FakeAircraft(tank_input))
    assert tank.n_tanks == 1
    assert tank.shape == "Cylinder"
    assert tank.L_cyl > 20 * tank.r_inner


def test_tank_config_cap_validation_and_dict():
    cfg = TankConfig(max_diameter=2.4)
    assert cfg.to_dict()['Max Number of Tanks'] == 4
    assert cfg.max_number_of_tanks == tank_module.DEFAULT_MAX_NUMBER_OF_TANKS
    with pytest.raises(ConfigError):
        TankConfig(max_diameter=2.4, number_of_tanks=5, max_number_of_tanks=4)
    with pytest.raises(ConfigError):
        TankConfig(max_diameter=2.4, max_number_of_tanks=0)


# --- history ---------------------------------------------------------------------

def test_log_state_records_the_full_tank_and_sets_the_clock():
    tank = _make_tank(500.0)
    tank.log_state(-100.0, 0.0)
    tank.time_step(dt=10.0, m_dot_req_total=0.0, altitude=0.0)
    assert tank.history['t'] == [-100.0, -90.0]
    assert tank.history['m_tot'][0] == pytest.approx(500.0)
    assert tank.history['Q_in'][0] > 0


def _check_tracked_history(aircraft):
    """Ground legs in the history and the end mass balance of a tracked mission."""
    m = aircraft.mission
    tank = aircraft.tank
    h = tank.history
    capacity = tank.capacity_single * tank.n_tanks
    t_taxi_out_takeoff = 60.0 * (m.taxi_out_time + m.takeoff_time)
    assert h['t'][0] == pytest.approx(-t_taxi_out_takeoff)
    assert h['m_tot'][0] == pytest.approx(capacity)
    assert h['t'][-1] == pytest.approx(m.profile.MissionTime2 + 60.0 * m.taxi_in_time)
    # Mass drawn by the tank = hydrogen burnt in flight and on the ground (E / ef).
    burnt = (m.Ef[-1] + m.E_ground) / m.ef
    vented = h['m_vent_cum'][-1]
    assert vented > 0
    assert h['m_tot'][-1] == pytest.approx(capacity - burnt - vented, rel=1e-9)
    # ... i.e. margin + reserve - vented (to the brentq tolerance of the sizing).
    w = aircraft.weight
    margin = w.WH2_Fuel - burnt
    assert h['m_tot'][-1] == pytest.approx(margin + w.final_reserve - vented, abs=0.1)


@pytest.mark.slow
def test_hydrogen_tracked_history_includes_ground_legs():
    aircraft = pg.build_aircraft()
    aircraft.configure(_hydrogen_config_with_tank())
    assert aircraft.results().tank_mass == pytest.approx(aircraft.weight.WTank)
    aircraft.mission.track_tank = True
    aircraft.mission.EvaluateMission(aircraft.weight.WTO)
    _check_tracked_history(aircraft)


@pytest.mark.slow
def test_fuelcell_battery_track_tank_fills_the_history():
    cfg = _hydrogen_config_with_tank()
    cfg.configuration = 'FuelCellBattery'
    cfg.energy.battery_specific_energy = 250
    cfg.energy.battery_specific_power = 1500
    cfg.energy.battery_usable_soc = 0.8
    stages = copy.deepcopy(sc.MISSION_STAGES)
    stages['Cruise']['Supplied Power Ratio'] = {'phi_start': 0.1, 'phi_end': 0.1}
    cfg.mission_stages = StagesConfig.from_dict(stages)
    aircraft = pg.build_aircraft()
    aircraft.configure(cfg)
    assert aircraft.weight.WTank == pytest.approx(aircraft.tank.mass_system_empty)
    aircraft.mission.track_tank = True
    aircraft.mission.EvaluateMission(aircraft.weight.WTO)
    assert len(aircraft.tank.history['t']) > 10
    _check_tracked_history(aircraft)


@pytest.mark.slow
def test_track_tank_without_a_physics_tank_warns():
    cfg = _hydrogen_config_with_tank()
    cfg.tank = None                       # gravimetric-index storage: no physics tank
    aircraft = pg.build_aircraft()
    aircraft.configure(cfg)
    assert aircraft.tank is None
    aircraft.mission.track_tank = True
    with pytest.warns(RuntimeWarning, match="no physics LH2"):
        aircraft.mission.EvaluateMission(aircraft.weight.WTO)
