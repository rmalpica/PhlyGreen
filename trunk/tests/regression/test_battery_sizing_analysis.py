"""Class-II pack: post-design cycle-life and ground-charge analysis on the flown cycle, the
upper bound of the P-number search, and the serial-hybrid generator specific power.

- ``Battery.thermal_degradation_analysis`` takes the depth of discharge, the flight
  temperature and the recharge start from the mission flown by the sized pack.
- The ground-charge cooling peak counts only the charge heat; the heat the pack brings from
  the flight is a separate pull-down peak.
- ``find_parallel_cells`` stops at the pack as heavy as the aircraft with
  ``PACK_HEAVIER_THAN_AIRCRAFT``.
- ``EnergyConfig.specific_power_generator`` sizes the serial generator; its default is the
  motor value.
"""

import contextlib
import dataclasses
import io
import os
import sys
import warnings

import numpy as np
import pytest

import PhlyGreen as pg
from PhlyGreen.config import ConfigError, EnergyConfig
from PhlyGreen.Systems.Battery.Battery import BatteryError

TRUNK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(TRUNK, "examples"))
from common import hybrid_config                                   # noqa: E402


def _design(cfg):
    a = pg.build_aircraft()
    with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
        warnings.simplefilter("ignore")
        a.configure(cfg)
    return a


@pytest.fixture(scope="module")
def class_ii():
    return _design(hybrid_config('II'))


def _flown_cycle(a):
    """Lowest SOC (taxi-in included), time-averaged flight temperature and end state."""
    m, b = a.mission, a.battery
    t = np.concatenate([s.t for s in m.integral_solution])
    it = np.concatenate([s.y[3] for s in m.integral_solution])
    T = np.concatenate([s.y[4] for s in m.integral_solution])
    it_end, T_end = m.battery_end_state
    charge = b.cell_capacity * b.P_number * 3600.0
    soc_lowest = 1.0 - max(it.max(), it_end) / charge
    T_mean = np.trapezoid(T, t) / (t[-1] - t[0])
    return soc_lowest, 1.0 - it_end / charge, T_mean, T_end


# ---------------------------------------------------------------- cycle life

@pytest.mark.slow
def test_cycle_life_uses_the_flown_depth_and_the_mean_flight_temperature(class_ii):
    b = class_ii.battery
    soc_lowest, soc_end, T_mean, T_end = _flown_cycle(class_ii)
    r = b.thermal_degradation_analysis(charge_c_rate=1.0, discharge_c_rate=3.0)
    assert r["dod"] == pytest.approx(1.0 - soc_lowest, rel=1e-12)
    assert r["dod"] < 1.0 - b.SOC_min                # the sized pack stops just above SOC_min
    assert r["soc_start"] == pytest.approx(soc_end, rel=1e-12)
    assert r["T_flight"] == pytest.approx(T_mean, rel=1e-12)
    assert r["T_start"] == pytest.approx(T_end, rel=1e-12)
    # the result does not depend on the temperature left on the battery by other calls
    b.T = 400.0
    again = b.thermal_degradation_analysis(charge_c_rate=1.0, discharge_c_rate=3.0)
    assert again == r


@pytest.mark.slow
def test_cycle_life_explicit_overrides(class_ii):
    b = class_ii.battery
    r = b.thermal_degradation_analysis(charge_c_rate=1.0, discharge_c_rate=3.0,
                                       soc_start=0.3, flight_temp_k=300.0)
    assert r["soc_start"] == 0.3
    assert r["dod"] == pytest.approx(0.7, rel=1e-12)
    assert r["T_flight"] == 300.0
    hot = b.thermal_degradation_analysis(charge_c_rate=1.0, discharge_c_rate=3.0,
                                         soc_start=0.3, flight_temp_k=320.0)
    assert hot["n_cycles"] < r["n_cycles"]


# ---------------------------------------------------------------- ground charge

@pytest.mark.slow
def test_ground_charge_cooling_peak_is_charge_heat_only(class_ii):
    b = class_ii.battery
    rates = [0.5, 1.0, 2.0, 4.0]
    rows = [b.thermal_degradation_analysis(charge_c_rate=c, discharge_c_rate=3.0) for c in rates]
    for r in rows:
        # the charge-heat rejection never exceeds the Joule heat
        assert 0.0 < r["peak_cooling_w"] <= r["peak_heat_w"] * (1 + 1e-12)
    # it grows with the charge rate (no constant floor set by the arrival temperature)
    peaks = [r["peak_cooling_w"] for r in rows]
    assert all(p1 < p2 for p1, p2 in zip(peaks, peaks[1:]))
    # the pack arrives warmer than the coolant: at a slow charge the pull-down dominates
    assert rows[0]["T_start"] > 293.15
    assert rows[0]["peak_pulldown_w"] > rows[0]["peak_cooling_w"]
    # the first step splits the cold-plate heat flow into charge heat + pull-down
    cells = b.S_number * b.P_number
    q_plate0 = 150.0 * b.cell_area_surface * (rows[0]["T_start"] - 293.15) * cells
    assert rows[0]["peak_pulldown_w"] <= q_plate0


# ---------------------------------------------------------------- P-number bound

def test_pack_search_stops_at_the_aircraft_mass():
    cfg = hybrid_config('II')
    cfg.cell = dataclasses.replace(cfg.cell, specific_energy=20.0)   # needs > W_TO of cells
    a = pg.build_aircraft()
    with warnings.catch_warnings(), contextlib.redirect_stdout(io.StringIO()):
        warnings.simplefilter("ignore")
        a.configure(cfg, design=False)
        a.constraint.FindDesignPoint()
        WTO = 21630.0
        with pytest.raises(BatteryError) as err:
            a.mission.EvaluateMission(WTO)
    assert err.value.code == "PACK_HEAVIER_THAN_AIRCRAFT"
    b = a.battery
    n_limit = int(np.floor(WTO / (b.cell_mass * b.S_number)))
    assert max(a.mission.P_n_arr) == n_limit
    assert n_limit * b.S_number * b.cell_mass <= WTO


# ---------------------------------------------------------------- serial generator

def test_generator_specific_power_config():
    e = EnergyConfig(Ef=43.5e6, specific_power_generator=8000)
    assert e.to_dict()["Specific Power Generator"] == 8000
    assert "Specific Power Generator" not in EnergyConfig(Ef=43.5e6).to_dict()
    with pytest.raises(ConfigError):
        EnergyConfig(Ef=43.5e6, specific_power_generator=-1.0)


@pytest.mark.slow
def test_serial_generator_has_its_own_specific_power():
    base = hybrid_config('I', hybrid_type='Serial')
    default = dataclasses.replace(base, energy=dataclasses.replace(
        base.energy, specific_power_generator=None))
    light = dataclasses.replace(base, energy=dataclasses.replace(
        base.energy, specific_power_generator=10000.0))
    a_base, a_default, a_light = _design(base), _design(default), _design(light)

    # unset = the motor value, which is what common.py writes explicitly
    assert base.energy.specific_power_generator == base.energy.specific_power_powertrain[1]
    assert a_default.weight.WTO == a_base.weight.WTO

    pt, m = a_light.powertrain, a_light.mission
    motor = max(m.Max_PMotor, m.TO_PMotor)
    assert pt.WGenerator == pytest.approx(pt.engineRating / 10000.0, rel=1e-12)
    assert pt.WMotor == pytest.approx(motor / pt.SPowerPT[1] + pt.WGenerator, rel=1e-12)
    assert a_light.weight.WTO < a_base.weight.WTO
