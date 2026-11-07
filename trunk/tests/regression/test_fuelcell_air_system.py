"""Fuel-cell air system: the expander takes the cathode exhaust, the ambient humidity reaches the
cathode through the compressor, and the ambient state follows the mission DISA input. Also pins
the take-off hydrogen power, which is the stack hydrogen flow at the take-off point."""

import os
import sys

import pytest

import PhlyGreen as pg

from test_hydrogen import _hydrogen_config

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "examples"))
from common import fuelcell_battery_config, hydrogen_config      # noqa: E402


def _fuelcell(**energy):
    cfg = _hydrogen_config()
    for k, v in energy.items():
        setattr(cfg.energy, k, v)
    a = pg.build_aircraft()
    a.configure(cfg, design=False)
    fc = a.fuelcell
    fc.N_cells = 400                                 # a stack geometry for the air-system balance
    return a, fc


def test_exhaust_mass_balance():
    # exhaust = dry air in - O2 consumed + product water as vapour (+ inlet water, none here)
    _, fc = _fuelcell()
    moles, x_v = fc.cathode_exhaust(101325.0, 288.15)
    M = fc.MOLAR_MASS
    air_in = 0.5 * fc.stoich * (M['O2'] + 0.79 / 0.21 * M['N2'])
    expected = air_in - 0.5 * M['O2'] + x_v * M['H2O']
    got = sum(n * M[k] for k, n in moles.items())
    assert got == pytest.approx(expected, rel=1e-12)
    assert moles['O2'] == pytest.approx(0.5 * (fc.stoich - 1.0))


def test_expander_works_on_the_exhaust_not_on_air():
    _, fc = _fuelcell()
    I = 500.0
    P_amb, T_amb = 60000.0, 260.0
    _, P_comp, P_turb = fc._compute_air_system_power(P_amb, T_amb, I)
    moles, _ = fc.cathode_exhaust(P_amb, T_amb)
    n_tot = sum(moles.values())
    cp_m = sum(n * fc.CP_MOLAR[k] for k, n in moles.items()) / n_tot
    M = sum(n * fc.MOLAR_MASS[k] for k, n in moles.items()) / n_tot
    n_h2 = fc.N_cells * I / (2 * fc.FARADAY_CONST)
    PR = 0.95 * fc.Target_Press / P_amb
    expected = n_h2 * n_tot * cp_m * fc.T_op * (1 - PR ** (-fc.R_GAS / cp_m)) * fc.turb_eta
    assert P_turb == pytest.approx(expected, rel=1e-12)
    # an air expander (dry-air cp and exponent, compressor flow) recovers less here
    m_air = 3.57e-7 * fc.N_cells * I * fc.stoich
    P_air = m_air * fc.CP_AIR * fc.T_op * (1 - PR ** -0.286) * fc.turb_eta
    assert P_turb > P_air


def test_ambient_humidity_reaches_the_cathode():
    _, dry = _fuelcell()
    _, wet = _fuelcell(fc_ambient_relative_humidity=1.0)
    assert dry.cathode_inlet_rh(101325.0, 288.15) == 0.0
    rh = wet.cathode_inlet_rh(101325.0, 288.15)
    p_w = wet.water_saturation_pressure(288.15) / 101325.0 * wet.Target_Press
    assert rh == pytest.approx(p_w / wet.water_saturation_pressure(wet.T_op), rel=1e-12)
    # a humidifier setting above the ambient-driven value wins
    _, hum = _fuelcell(fc_ambient_relative_humidity=1.0, fc_cathode_inlet_rh=0.6)
    assert hum.cathode_inlet_rh(101325.0, 288.15) == 0.6
    assert hum.vapour_fraction_at(101325.0, 288.15) < wet.vapour_fraction_at(101325.0, 288.15)


def test_mission_disa_input_reaches_the_mission_and_the_fuel_cell():
    a, fc = _fuelcell()
    assert a.mission.DISA == 0.0                     # default: no MissionInput 'DISA' key
    P0, T0 = fc._get_env(1000.0)
    cfg = _hydrogen_config()
    cfg.mission.disa = 20.0
    assert cfg.mission.to_dict()["DISA"] == 20.0     # legacy MissionInput key
    hot = pg.build_aircraft()
    hot.configure(cfg, design=False)
    assert hot.mission.DISA == 20.0
    assert hot.constraint.DISA == 0.0                # the constraint diagram keeps its own DISA
    P1, T1 = hot.fuelcell._get_env(1000.0)
    assert P1 == P0 and T1 == pytest.approx(T0 + 20.0)


def _design(cfg):
    a = pg.build_aircraft()
    a.configure(cfg)
    return a


def _takeoff_stack_chemical_power(a):
    """mdot_h2 * HHV of the sized stack at the take-off/OEI fuel-cell power."""
    m, fc = a.mission, a.fuelcell
    c = a.constraint
    to = c.TakeOffConstraints
    a.performance.set_speed(to['Altitude'], to['Speed'], to['Speed Type'], c.DISA)
    fc.ComputePRatio(to['Altitude'], float(a.performance.TAS), m.TO_PP)
    return fc.mdot_h2 * fc.HHV_H2


@pytest.mark.slow
def test_hot_day_changes_the_hydrogen_design():
    isa = _design(hydrogen_config())
    cfg = hydrogen_config()
    cfg.mission.disa = 20.0
    hot = _design(cfg)
    # ISA+20 on the mission only costs 0.42 % of the take-off mass on the reference design
    assert 100 * (hot.weight.WTO / isa.weight.WTO - 1) == pytest.approx(0.4214, abs=0.005)
    assert hot.mission.TO_FC_Thermal_Pwr > isa.mission.TO_FC_Thermal_Pwr
    # the take-off hydrogen power is the stack hydrogen flow there, larger on the hot day
    for a in (isa, hot):
        assert a.mission.TO_P_H2_Thermal == pytest.approx(_takeoff_stack_chemical_power(a),
                                                          rel=1e-9)
    assert hot.mission.TO_P_H2_Thermal > isa.mission.TO_P_H2_Thermal


@pytest.mark.slow
def test_fuelcell_battery_takeoff_hydrogen_power_is_the_stack_flow():
    a = _design(fuelcell_battery_config())
    assert a.mission.TO_PP > 0.0
    assert a.mission.TO_P_H2_Thermal == pytest.approx(_takeoff_stack_chemical_power(a), rel=1e-9)
    assert a.mission.TO_P_H2_Thermal > a.mission.TO_PP
