"""Tests for the post-processing helpers."""

import numpy as np
import pytest

import PhlyGreen as pg
from PhlyGreen import postprocess as pp
import _sample_configs as sc
from conftest import design_from_config


@pytest.mark.slow
def test_timeseries_traditional():
    aircraft = design_from_config(*sc.traditional_config())
    ts = pp.mission_timeseries(aircraft)
    n = len(ts["time"])
    for key in ("altitude", "velocity", "power_excess", "mass_fraction", "fuel_energy"):
        assert len(ts[key]) == n
    assert ts["time"][0] == pytest.approx(0.0)
    assert np.all(np.diff(ts["fuel_energy"]) >= -1e-6)   # cumulative fuel energy
    assert "battery_energy" not in ts                    # traditional has no battery


@pytest.mark.slow
def test_timeseries_hybrid_has_battery_and_phi():
    aircraft = design_from_config(*sc.hybrid_parallel_config())
    ts = pp.mission_timeseries(aircraft)
    assert "battery_energy" in ts and "phi" in ts
    assert len(ts["battery_energy"]) == len(ts["time"])


@pytest.mark.slow
def test_mass_breakdown_sums_to_wto():
    aircraft = design_from_config(*sc.traditional_config())
    total = sum(pp.mass_breakdown(aircraft).values())
    assert total == pytest.approx(aircraft.weight.WTO, rel=1e-3)


@pytest.mark.slow
def test_power_timeseries_traditional():
    aircraft = design_from_config(*sc.traditional_config())
    ps = pp.power_timeseries(aircraft)
    n = len(ps["time"])
    for k in ("propulsive_power", "gt_power", "em_power"):
        assert len(ps[k]) == n
    # Sane magnitudes (MW-class, not GW) and no battery on a fuel-only aircraft.
    assert 1e5 < np.nanmax(ps["propulsive_power"]) < 2e7
    # Gas-turbine shaft power exceeds propulsive (gearbox + propeller losses).
    assert np.nanmax(ps["gt_power"]) >= np.nanmax(ps["propulsive_power"])
    assert np.allclose(ps["em_power"], 0.0)


@pytest.mark.slow
def test_power_timeseries_hybrid_has_electric_and_sane_magnitudes():
    aircraft = design_from_config(*sc.hybrid_parallel_config())
    ps = pp.power_timeseries(aircraft)
    # Beta (mass fraction) must be read from the right ODE index even for the 5-state
    # Class-II hybrid, so the propulsive power stays MW-class (regression for that bug).
    assert np.nanmax(ps["propulsive_power"]) < 2e7
    assert np.nanmax(ps["em_power"]) > 0.0          # the battery does supply power


@pytest.mark.slow
def test_write_timeseries_includes_power_columns(tmp_path):
    aircraft = design_from_config(*sc.traditional_config())
    path = aircraft.results().write_timeseries(tmp_path / "ts.csv")
    with open(path) as f:
        header = f.readline().strip().split(",")
    for col in ("propulsive_power", "gt_power", "em_power"):
        assert col in header


@pytest.mark.slow
def test_write_timeseries_auto_detects_class_ii_components(tmp_path):
    aircraft = design_from_config(*sc.traditional_config())
    # A constant-efficiency design has no Class-II components.
    assert pp.class_ii_components(aircraft) == set()
    # "auto" (default): power columns present, but NO surrogate-based component columns.
    auto = aircraft.results().write_timeseries(tmp_path / "auto.csv")
    with open(auto) as f:
        header = f.readline().strip().split(",")
    assert {"propulsive_power", "gt_power", "em_power"}.issubset(header)
    assert "eta_gas_turbine" not in header and "eta_propeller" not in header
    # Forcing the components adds them.
    forced = aircraft.results().write_timeseries(tmp_path / "forced.csv", include_components=True)
    with open(forced) as f:
        fheader = f.readline().strip().split(",")
    assert "eta_gas_turbine" in fheader


@pytest.mark.slow
def test_write_timeseries_dumps_all_states(tmp_path):
    aircraft = design_from_config(*sc.traditional_config())
    path = aircraft.results().write_timeseries(tmp_path / "ts.csv")
    with open(path) as f:
        header = f.readline().strip().split(",")
    data = np.loadtxt(path, delimiter=",", skiprows=1)
    # time first; raw ODE states + derived mission columns are all present and aligned.
    assert header[0] == "time"
    nstates = aircraft.mission.integral_solution[0].y.shape[0]
    for i in range(nstates):
        assert f"state_{i}" in header
    for key in ("altitude", "velocity", "power_excess", "mass_fraction", "fuel_energy"):
        assert key in header
    n = len(pp.mission_timeseries(aircraft)["time"])
    assert data.shape == (n, len(header))


@pytest.mark.slow
def test_write_timeseries_requires_aircraft():
    from PhlyGreen.results import AircraftResults
    with pytest.raises(ValueError):
        AircraftResults().write_timeseries("/tmp/should_not_be_written.csv")
