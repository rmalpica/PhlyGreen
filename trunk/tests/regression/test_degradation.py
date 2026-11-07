"""Degradation (state of health) of the fuel cell and the battery, and the power-limited
operating point of the fuel cell.

- ``FuelCell.set_state_of_health``: uniform cell-voltage loss and drift of R_ohm / i_star,
  relative to beginning of life (BOL). The stack mass stays referenced to the BOL curve.
- ``Battery.set_state_of_health``: capacity fraction and resistance factor (Class I and II).
- ``EnergyConfig`` fields size the aircraft at end of life; ``fly_off_design(...,
  state_of_health=...)`` flies a sized aircraft degraded.
- A stack that cannot meet the demand runs at its maximum-power point, scaled to the demand
  (no fixed-efficiency fallback), and is flagged power-limited.
"""

import copy
import importlib.util
import os
import sys

import numpy as np
import pytest

import PhlyGreen as pg
from PhlyGreen.config import EnergyConfig, ConfigError

from test_hydrogen import _hydrogen_config

TRUNK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXAMPLES = os.path.join(TRUNK, "examples")
sys.path.insert(0, EXAMPLES)
from common import hybrid_config                                   # noqa: E402


@pytest.fixture(scope="module")
def ex30():
    spec = importlib.util.spec_from_file_location(
        "ex30", os.path.join(EXAMPLES, "30_off_design_mission.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def hydrogen():
    a = pg.build_aircraft()
    a.configure(_hydrogen_config())
    return a


def _ready_fuelcell():
    a = pg.build_aircraft()
    a.configure(_hydrogen_config(), design=False)
    return a.fuelcell


# --- fuel cell: state of health -------------------------------------------------------

def test_voltage_loss_shifts_the_polarization_curve():
    fc = _ready_fuelcell()
    i = np.array([0.1, 0.5, 1.0, 1.5])
    v_bol = np.array([fc.PolarizationCurve(x, fc.Target_Press) for x in i])
    fc.set_state_of_health(voltage_loss=0.03)
    v_eol = np.array([fc.PolarizationCurve(x, fc.Target_Press) for x in i])
    assert v_eol == pytest.approx(v_bol - 0.03, abs=1e-12)
    # the BOL curve stays available (stack-mass reference)
    v_ref = np.array([fc.PolarizationCurve(x, fc.Target_Press, bol=True) for x in i])
    assert v_ref == pytest.approx(v_bol, abs=1e-12)


def test_parameter_drift_lowers_the_curve_and_resets_to_bol():
    fc = _ready_fuelcell()
    v_bol = fc.PolarizationCurve(1.0, fc.Target_Press)
    fc.set_state_of_health(ohmic_resistance_factor=1.5)
    assert fc.PolarizationCurve(1.0, fc.Target_Press) < v_bol
    fc.set_state_of_health(exchange_current_factor=0.5)        # resistance back to BOL
    assert fc.R_ohm == fc.R_ohm_bol
    assert fc.PolarizationCurve(1.0, fc.Target_Press) < v_bol
    fc.set_state_of_health()
    assert fc.PolarizationCurve(1.0, fc.Target_Press) == v_bol


def test_state_of_health_inputs_are_validated_and_read():
    with pytest.raises(ConfigError):
        EnergyConfig(Ef=141.87e6, fc_voltage_loss=-0.01)
    with pytest.raises(ConfigError):
        EnergyConfig(Ef=141.87e6, battery_capacity_fraction=1.2)
    with pytest.raises(ConfigError):
        EnergyConfig(Ef=141.87e6, fc_ohmic_resistance_factor=0.0)
    cfg = _hydrogen_config()
    cfg.energy.fc_voltage_loss = 0.02
    cfg.energy.fc_ohmic_resistance_factor = 1.2
    a = pg.build_aircraft()
    a.configure(cfg, design=False)
    assert a.fuelcell.voltage_loss == 0.02
    assert a.fuelcell.R_ohm == pytest.approx(1.2 * a.fuelcell.R_ohm_bol, rel=1e-15)


# --- fuel cell: power-limited operating point ------------------------------------------

@pytest.mark.slow
def test_power_limited_point_is_continuous_and_monotone(hydrogen):
    fc = copy.deepcopy(hydrogen.fuelcell)
    alt, vel = 0.0, 70.0
    fc.reset_adequacy()
    P_probe = 2.0e7                                   # far beyond the stack: refined maximum
    fc.ComputePRatio(alt, vel, P_probe)
    assert fc._power_limited
    P_lim = P_probe / fc._worst_load_ratio            # propulsive power the stack can deliver

    def state(P):
        fc.reset_adequacy()
        fc.ComputePRatio(alt, vel, P)
        return fc.mdot_h2, fc.Q_thermal, fc._power_limited

    m_below, q_below, lim_below = state(0.9999 * P_lim)
    m_above, q_above, lim_above = state(1.0001 * P_lim)
    assert not lim_below and lim_above
    # continuous across the limit (no jump to a fixed-efficiency fallback); near the top of
    # the power curve the current, hence the hydrogen, varies as the square root of the margin
    assert 1.0 < m_above / m_below < 1.03
    assert 1.0 < q_above / q_below < 1.05
    # beyond it, hydrogen and heat keep growing with demand and with degradation
    m_far, q_far, _ = state(1.2 * P_lim)
    assert m_far > m_above and q_far > q_above
    fc.set_state_of_health(voltage_loss=0.10)
    m_deg, q_deg, _ = state(1.2 * P_lim)
    assert m_deg > m_far and q_deg > q_far


# --- fuel cell: end-of-life sizing and degraded flight ----------------------------------

@pytest.mark.slow
def test_end_of_life_sizing_enlarges_the_stack_and_the_tms(hydrogen):
    cfg = _hydrogen_config()
    cfg.energy.fc_voltage_loss = 0.05
    eol = pg.build_aircraft()
    eol.configure(cfg)
    bol_fc, eol_fc = hydrogen.fuelcell, eol.fuelcell
    # sized at the same design voltage on the degraded curve: lower design current density,
    # hence more active area; the mass per area is the BOL hardware figure, so a heavier stack
    assert eol_fc.i_max_density < bol_fc.i_max_density
    assert eol_fc.A_cell_reale * eol_fc.N_cells > bol_fc.A_cell_reale * bol_fc.N_cells
    assert eol.weight.WPT > hydrogen.weight.WPT
    assert eol.weight.WHeat_Exchanger > hydrogen.weight.WHeat_Exchanger
    assert eol.weight.WTO > hydrogen.weight.WTO


@pytest.mark.slow
def test_degraded_flight_reports_the_binding_constraints(ex30, hydrogen):
    rng = hydrogen.MissionInput["Range Mission"]
    bol = ex30.fly_off_design(hydrogen, rng)
    assert bol.feasible
    eol = ex30.fly_off_design(hydrogen, rng, state_of_health={"fc_voltage_loss": 0.05})
    assert eol.trip_fuel > bol.trip_fuel
    assert any("TMS design heat" in v for v in eol.violations)
    # a fuel-cell design is limited by the stack's own maximum power, not by its design peak
    assert not any("engine power" in v for v in eol.violations)
    # the design aircraft is not modified
    assert hydrogen.fuelcell.voltage_loss == 0.0
    with pytest.raises(ValueError, match="unknown state-of-health"):
        ex30.fly_off_design(hydrogen, rng, state_of_health={"fc_voltage": 0.05})


# --- battery: state of health -----------------------------------------------------------

def test_class_i_battery_state_of_health():
    a = pg.build_aircraft()
    a.configure(hybrid_config('I'), design=False)
    b = a.battery
    E0, p0 = b.Ebat, b.pbat
    b.set_state_of_health(capacity_fraction=0.8, resistance_factor=1.6)
    assert b.Ebat == pytest.approx(0.8 * E0) and b.pbat == pytest.approx(p0 / 1.6)
    b.set_state_of_health()
    assert (b.Ebat, b.pbat) == (E0, p0)


def test_class_ii_battery_state_of_health():
    a = pg.build_aircraft()
    a.configure(hybrid_config('II'), design=False)
    b = a.battery
    C0, R0, K0 = b.cell_capacity, b.cell_resistance, b.polarization_ctt
    b.set_state_of_health(capacity_fraction=0.8, resistance_factor=1.5)
    assert b.cell_capacity == pytest.approx(0.8 * C0)
    assert b.cell_resistance == pytest.approx(1.5 * R0)
    assert b.polarization_ctt == pytest.approx(1.5 * K0)
    b.set_state_of_health()
    assert (b.cell_capacity, b.cell_resistance, b.polarization_ctt) == (C0, R0, K0)
    with pytest.raises(ValueError):
        b.set_state_of_health(capacity_fraction=0.0)


@pytest.mark.slow
def test_end_of_life_battery_sizing_enlarges_the_pack():
    bol = pg.build_aircraft()
    bol.configure(hybrid_config('I'))
    cfg = hybrid_config('I')
    cfg.energy.battery_capacity_fraction = 0.8
    eol = pg.build_aircraft()
    eol.configure(cfg)
    assert eol.weight.WBat > bol.weight.WBat


# --- fuel-cell mission bookkeeping ------------------------------------------------------

@pytest.mark.slow
def test_running_stack_burns_hydrogen_at_zero_propulsive_power(hydrogen):
    # the fixed auxiliaries and the air system are fed even with no propulsive demand
    m = hydrogen.mission
    assert m._fuel_cell_chemical_power(3000.0, 100.0, 0.0) > 0.0


def test_fc_battery_chain_includes_the_propeller():
    from common import fuelcell_battery_config
    a = pg.build_aircraft()
    a.configure(fuelcell_battery_config(), design=False)
    fc = a.fuelcell
    assert a.mission._fc_battery_eta_elec(3000.0, 100.0, 1e5) == pytest.approx(
        fc.EtaEM * fc.EtaPM * fc.EtaGB * fc.EtaProp, rel=1e-12)


@pytest.mark.slow
def test_fc_battery_energy_and_power_are_terminal_quantities():
    from common import fuelcell_battery_config
    a = pg.build_aircraft()
    a.configure(fuelcell_battery_config(cruise_phi=0.15))
    m, fc = a.mission, a.fuelcell
    chain = fc.EtaEM * fc.EtaPM * fc.EtaGB * fc.EtaProp
    # battery energy = integral of phi * PP / chain over the flown profile (+ ground legs)
    e = 0.0
    for sol in m.integral_solution:
        pp = np.array([max(a.weight.WTO * a.performance.PoWTO(
            a.DesignWTOoS, b, m.profile.PowerExcess(t), 1, m.profile.Altitude(t), m.DISA,
            m.profile.Velocity(t), 'TAS'), 0.0) for t, b in zip(sol.t, sol.y[1])])
        phi = np.array([float(m.profile.SuppliedPowerRatio(t)) for t in sol.t])
        e += np.trapezoid(phi * pp / chain, sol.t)
    assert a.weight.TotalEnergies[1] == pytest.approx(e + m.EBat_ground, rel=1e-5)
    # the battery is sized on its terminal power
    w = a.weight
    spec_p = a.EnergyInput.get('Battery Specific Power', 1500.0)
    assert w.WBat >= m.Max_PBat / spec_p * (1 - 1e-12)


@pytest.mark.slow
def test_degraded_flight_rates_the_class_ii_tms_hardware(ex30):
    from PhlyGreen.config import TMSConfig
    cfg = _hydrogen_config()
    cfg.tms = TMSConfig(tms_class='II')
    a = pg.build_aircraft()
    a.configure(cfg)
    rng = a.MissionInput["Range Mission"]
    assert ex30.fly_off_design(a, rng).feasible
    eol = ex30.fly_off_design(a, rng, state_of_health={"fc_voltage_loss": 0.05})
    assert any("Class-II TMS hardware short" in v for v in eol.violations)
