"""Unit tests of the Class-II cell model and of the P-number search, in isolation.

The battery is built from a stub aircraft that carries only a ``CellInput`` and a mission
namespace, so no aircraft design is needed.
"""

import types

import numpy as np
import pytest

from PhlyGreen.Systems.Battery.Battery import Battery, BatteryError, find_parallel_cells
from PhlyGreen.Systems.Battery.Cell_Models import Cell_Models


def _battery(**cell_input):
    """A Class-II battery built from ``CellInput`` alone (Finger-Cell-Thermal by default)."""
    ci = {'Class': 'II', 'Model': 'Finger-Cell-Thermal', 'Minimum SOC': 0.2,
          'Initial temperature': 25, 'Max operative temperature': 40}
    ci.update(cell_input)
    aircraft = types.SimpleNamespace(
        CellInput=ci, mission=types.SimpleNamespace(T_battery_limit=40.0))
    b = Battery(aircraft)
    b.SetInput()
    return b


# ---------------------------------------------------------------- voltage model

def test_open_circuit_voltage_of_a_full_cell_at_the_reference_temperature():
    b = _battery()
    cell = Cell_Models['Finger-Cell-Thermal']
    assert b.T == pytest.approx(b.Tref)
    # V(0, 0) = E0 + A at the reference temperature
    assert b._voltageModel(0.0, 0.0) == pytest.approx(
        cell['Voltage Constant'] + cell['Exp Amplitude'], rel=1e-12)


def test_voltage_model_matches_the_shepherd_equation():
    b = _battery()
    b.T = b.Tref + 15.0
    it, i = 2.0, 5.0
    E0 = b.voltage_ctt + b.E_slope * (b.T - b.Tref)
    Q = b.cell_capacity + b.Q_slope * (b.T - b.Tref)
    K = b.polarization_ctt * np.exp(b.K_arrhenius * (1 / b.T - 1 / b.Tref))
    R = b.cell_resistance * np.exp(b.R_arrhenius * (1 / b.T - 1 / b.Tref))
    expected = (E0 - (i + it) * K * Q / (Q - it) + b.exp_amplitude * np.exp(-b.exp_time_ctt * it)
                - i * R)
    assert b._voltageModel(it, i) == pytest.approx(expected, rel=1e-12)


def test_voltage_falls_with_current_and_with_spent_charge():
    b = _battery()
    assert b._voltageModel(0.0, 10.0) < b._voltageModel(0.0, 1.0)
    assert b._voltageModel(3.0, 1.0) < b._voltageModel(1.0, 1.0)


def test_cold_cell_has_a_higher_resistance():
    b = _battery()
    R_ref = b.R
    b.T = b.Tref - 20.0
    assert b.R > R_ref


# ---------------------------------------------------------------- power -> current

def test_power_to_current_round_trip():
    b = _battery()
    b.Configure(50)
    b.T, b.it = b.Tref, 0.3 * b.cell_capacity * b.P_number      # 30 % of the charge spent
    P_pack = 0.4 * b.pack_power_max
    I_pack = b.Power_2_current(P_pack)
    i_cell = I_pack / b.P_number
    V_cell = b._voltageModel(b.cell_it, i_cell)
    # every cell delivers the same power
    assert V_cell * i_cell * b.cells_total == pytest.approx(P_pack, rel=1e-10)
    assert i_cell > 0


def test_zero_power_draws_no_current_and_excess_power_has_no_solution():
    b = _battery()
    b.Configure(50)
    b.T, b.it = b.Tref, 0.0
    assert b.Power_2_current(0.0) == 0
    assert b.Power_2_current(1e3 * b.pack_power_max) is None
    with pytest.raises(BatteryError) as err:
        b.i = None
    assert err.value.code == "BATT_UNDERPOWERED"


# ---------------------------------------------------------------- heat

def test_heat_loss_is_bernardi_and_adiabatic_below_the_ceiling():
    b = _battery()
    b.Configure(50)
    b.T, b.it, b.phi = b.Tref + 5.0, 0.0, 0.5         # discharging, below the 40 C ceiling
    b.i = b.Power_2_current(0.3 * b.pack_power_max)
    i, V, Voc = b.cell_i, b.cell_Vout, b.cell_Voc
    dTdt, q = b.heatLoss(250.0, 0.8)
    assert q == pytest.approx((Voc - V) * i - b.E_slope * i * b.T, rel=1e-12)
    assert q > 0
    # the thermostat keeps the pack adiabatic: all the heat warms the cell
    assert dTdt == pytest.approx(q / b.Cth, rel=1e-12)


def test_idle_hot_cell_cools_toward_the_ambient():
    b = _battery()
    b.Configure(50)
    b.T, b.it, b.phi = b.Tref + 10.0, 0.0, 0.0
    b.i = b.Power_2_current(0.0)
    dTdt, q = b.heatLoss(273.15, 1.2)
    assert q == 0.0
    assert dTdt < 0.0


# ---------------------------------------------------------------- rescaling

def test_rescaling_to_a_target_specific_energy_keeps_the_curve_shape():
    base = _battery()
    b = _battery(SpecificEnergy=1500)
    ratio = b.cell_capacity / base.cell_capacity
    assert b.cell_capacity * b.Vnom / b.cell_mass == pytest.approx(1500, rel=1e-12)
    assert b.cell_mass == base.cell_mass
    # charge-proportional terms scale with the capacity, the exponential zone stretches
    assert b.Q_slope == pytest.approx(base.Q_slope * ratio, rel=1e-12)
    assert b.exp_time_ctt == pytest.approx(base.exp_time_ctt / ratio, rel=1e-12)
    # without a power target the power scales in the same proportion
    assert b.cell_resistance == pytest.approx(base.cell_resistance / ratio, rel=1e-12)
    assert b.cell_max_current == pytest.approx(base.cell_max_current * ratio, rel=1e-12)
    # the Arrhenius activation temperatures are not rescaled
    assert b.R_arrhenius == base.R_arrhenius and b.K_arrhenius == base.K_arrhenius


def test_rescaling_to_a_target_specific_power():
    b = _battery(SpecificEnergy=1500, SpecificPower=8000)
    p_cell = b.cell_max_current * b._voltageModel(0, b.cell_max_current)
    assert p_cell / b.cell_mass == pytest.approx(8000, rel=1e-10)


def test_series_count_from_the_pack_voltage():
    b = _battery(**{'Pack Voltage': 800})
    assert b.S_number == np.floor(800 / b.cell_Vmax)


# ---------------------------------------------------------------- P-number search

def _monotone(p_opt, calls):
    def evaluate(P):
        calls.append(P)
        return (P >= p_opt, None if P >= p_opt else "SOC_OUTSIDE_LIMITS")
    return evaluate


@pytest.mark.parametrize("p_opt", [1, 37, 64, 65, 128, 129, 1000])
def test_search_finds_the_smallest_feasible_P_from_a_cold_start(p_opt):
    calls = []
    assert find_parallel_cells(_monotone(p_opt, calls), 128, None, 10**6) == p_opt
    assert calls[-1] == p_opt                        # the last flight is the sized pack


@pytest.mark.parametrize("ratio", [0.9, 1.0, 1.02, 1.3])
def test_search_warm_start_from_the_scaled_previous_optimum(ratio):
    calls = []
    assert find_parallel_cells(_monotone(110, calls), 108, ratio, 10**6) == 110
    assert calls[-1] == 110


def test_search_stops_at_the_heaviest_acceptable_pack():
    calls = []
    with pytest.raises(BatteryError) as err:
        find_parallel_cells(_monotone(5000, calls), 128, None, 1603)
    assert err.value.code == "PACK_HEAVIER_THAN_AIRCRAFT"
    assert max(calls) == 1603                        # the limit itself is tried, nothing above


def test_search_reaches_a_feasible_P_at_the_limit():
    assert find_parallel_cells(_monotone(1603, []), 128, None, 1603) == 1603


def test_search_with_an_infeasible_guess_above_the_limit_raises():
    with pytest.raises(BatteryError) as err:
        find_parallel_cells(_monotone(10**6, []), 128, None, 100)
    assert err.value.code == "PACK_HEAVIER_THAN_AIRCRAFT"
