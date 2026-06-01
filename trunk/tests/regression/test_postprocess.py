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
