"""Tests for the cryogenic LH2 tank model.

Requires CoolProp (para-hydrogen properties); skipped automatically if it is not
installed. Covers tank sizing and the transient time_step physics (self-pressurization,
venting at P_max, heater at P_min, mass depletion, vent accounting), plus a full hydrogen
design + tracked mission.
"""

import numpy as np
import pytest

pytest.importorskip("CoolProp")

import PhlyGreen as pg
from PhlyGreen.Systems.Tank import LH2_Tank
from PhlyGreen.config import (
    AircraftConfig, AerodynamicsConfig, ConstraintsConfig, MissionConfig,
    EnergyConfig, StagesConfig, TankConfig,
)
import _sample_configs as sc


class _FakeAircraft:
    """Minimal stand-in: the tank constructor only needs ``TankInput``."""
    def __init__(self, tankinput):
        self.TankInput = tankinput


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
        Ef=120e6, eta_gearbox=0.96, eta_pmad=0.99, eta_electric_motor=0.96,
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
