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
