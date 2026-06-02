"""Unit tests for the opt-in Class-II battery thermal-management + degradation analysis.

Uses a lightweight stub pack (only the attributes the ageing model reads) so the tests are
fast and independent of a full aircraft design.
"""

import types

import pytest

from PhlyGreen.Systems.Battery.degradation import BatteryAgeingModel


def _stub_pack(T=298.15):
    # A representative 18650-class cell pack.
    return types.SimpleNamespace(
        SOC_min=0.2, T=T, Tref=298.15,
        cell_capacity=3.0,            # Ah
        S_number=100, P_number=200,
        cell_resistance=0.03,         # ohm
        R_arrhenius=2000.0,
        cell_area_surface=2 * 3.14159 * 0.009 * 0.065,   # m^2
        Cth=1000 * 0.045,             # J/K
    )


def test_recharge_and_cooling_are_physical():
    m = BatteryAgeingModel(_stub_pack(), charge_c_rate=2.0)
    r = m.simulate_ground_recharge()
    assert r["recharge_time_min"] == pytest.approx((1.0 - 0.2) / 2.0 * 60.0)
    assert r["peak_cooling_w"] >= 0.0
    assert r["peak_heat_w"] >= 0.0
    # Final temperature stays physical: not below the coolant, not runaway.
    assert 293.15 - 1.0 <= r["T_final"] <= 360.0


def test_higher_charge_rate_needs_more_cooling():
    slow = BatteryAgeingModel(_stub_pack(), charge_c_rate=1.0).simulate_ground_recharge()
    fast = BatteryAgeingModel(_stub_pack(), charge_c_rate=4.0).simulate_ground_recharge()
    assert fast["peak_cooling_w"] > slow["peak_cooling_w"]
    assert fast["T_final"] > slow["T_final"]


def test_cycle_life_finite_and_decreases_with_temperature():
    cool = BatteryAgeingModel(_stub_pack(T=290.0), charge_c_rate=2.0).analyze()["n_cycles"]
    hot = BatteryAgeingModel(_stub_pack(T=320.0), charge_c_rate=2.0).analyze()["n_cycles"]
    assert cool > 0 and hot > 0
    assert hot < cool          # higher temperature -> faster fade -> fewer cycles


def test_zero_charge_rate_is_infinite_time():
    m = BatteryAgeingModel(_stub_pack(), charge_c_rate=0.0)
    assert m.recharge_time_min() == float("inf")
    r = m.simulate_ground_recharge()
    assert r["peak_cooling_w"] == 0.0
