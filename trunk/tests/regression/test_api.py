"""Tests for the stateless outer-loop API (run_design / evaluate)."""

import copy

import pytest

import PhlyGreen as pg
import _sample_configs as sc


def _hybrid_aircraft_config():
    return sc.hybrid_parallel_aircraft_config()


def _traditional_aircraft_config():
    return sc.traditional_aircraft_config()


@pytest.mark.slow
def test_run_design_matches_configure_path():
    config = _traditional_aircraft_config()
    api_results = pg.run_design(config).to_dict()
    manual = pg.build_aircraft().configure(copy.deepcopy(config)).results().to_dict()
    assert api_results["WTO"] == pytest.approx(manual["WTO"], rel=1e-9)


@pytest.mark.slow
def test_run_design_is_deterministic_and_pure():
    config = _traditional_aircraft_config()
    before = config.to_dict() if hasattr(config, "to_dict") else None
    r1 = pg.run_design(config).to_dict()
    r2 = pg.run_design(config).to_dict()
    assert r1["WTO"] == pytest.approx(r2["WTO"], rel=1e-12)
    # base config must be untouched (run_design works on a copy)
    assert config.configuration == "Traditional"
    assert config.mission.range_mission == 750


@pytest.mark.slow
def test_evaluate_applies_params_without_mutating_base():
    base = _traditional_aircraft_config()
    base_range = base.mission.range_mission

    def set_range(cfg, r):
        cfg.mission.range_mission = r

    short = pg.evaluate(base, set_range, 400).WTO
    long = pg.evaluate(base, set_range, 1000).WTO
    assert long > short                      # more range -> heavier aircraft
    assert base.mission.range_mission == base_range   # base untouched
