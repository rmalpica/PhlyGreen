"""ClimateImpact emissions per fuel, and the Profile short-range guard.

- Kerosene: unchanged, CO2 = 3.16 Wf + WTW_CO2 * 43.5 Wf (the examples use Ef = 43.5 MJ/kg).
- Hydrogen (fuel cell): no tank-to-wake CO2, SO4, soot or NOx; H2O = 8.94 kg per kg of H2
  burnt; upstream CO2 on the burnt H2 (not on the loaded mass, which carries the sizing margin).
- FuelCellBattery: the grid CO2 of the battery energy is counted (it was only for 'Hybrid').
- Profile: a range shorter than the climbs + descents raises instead of flying a negative cruise.
"""
import os
import sys

import pytest

import PhlyGreen as pg
from PhlyGreen.config import ClimateImpactConfig

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "examples"))
from common import traditional_config, hydrogen_config, fuelcell_battery_config  # noqa: E402

WTW, GRID = 8.30e-3, 9.36e-2       # kg CO2 / MJ


def _climate():
    return ClimateImpactConfig(H=100, N=1.6e7, Y=30, einox_model="Filippone",
                               wtw_co2=WTW, grid_co2=GRID)


def _design(cfg):
    cfg.climate_impact = _climate()
    a = pg.build_aircraft()
    a.configure(cfg)
    a.MissionType = "Continue"
    a.climateimpact.calculate_mission_emissions()
    return a


def test_kerosene_emissions_unchanged():
    a = _design(traditional_config())
    e, Wf = a.climateimpact.mission_emissions, a.weight.Wf
    assert a.weight.ef == pytest.approx(43.5e6)
    assert e["co2"] == pytest.approx(3.16 * Wf + WTW * 43.5 * Wf, rel=1e-12)
    assert e["h2o"] == pytest.approx(1.26 * Wf, rel=1e-12)
    assert e["nox"] > 0.0


@pytest.mark.slow
def test_hydrogen_fuel_cell_emissions():
    a = _design(hydrogen_config())
    e, w = a.climateimpact.mission_emissions, a.weight
    burnt = w.TotalEnergies[0] / w.ef
    assert burnt < w.Wf                                   # the loaded H2 carries the margin
    assert e["co2"] == pytest.approx(WTW * burnt * w.ef * 1e-6, rel=1e-12)   # upstream only
    assert e["h2o"] == pytest.approx(8.94 * burnt, rel=1e-12)
    assert e["so4"] == 0.0 and e["soot"] == 0.0 and e["nox"] == 0.0


@pytest.mark.slow
def test_fuel_cell_battery_counts_grid_co2():
    cfg = fuelcell_battery_config(cruise_phi=0.05)
    a = _design(cfg)
    e, w = a.climateimpact.mission_emissions, a.weight
    burnt = w.TotalEnergies[0] / w.ef
    assert w.TotalEnergies[1] > 0.0
    grid = GRID * w.TotalEnergies[1] * 1e-6          # no WellToTankInput: lossless pathway
    assert e["co2"] == pytest.approx(WTW * burnt * w.ef * 1e-6 + grid, rel=1e-12)


def test_profile_rejects_range_shorter_than_climb_and_descent():
    cfg = traditional_config()
    cfg.mission.range_mission = 150          # the climb to 8,000 m + descent need ~215 nm
    with pytest.raises(ValueError, match="shorter than its climbs and descents"):
        pg.build_aircraft().configure(cfg)
