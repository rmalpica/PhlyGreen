"""Prove the new Profile reproduces the legacy Profile numerically.

The new (clean, extensible) ``Profile`` must be a behavior-preserving drop-in for
``Profile_legacy``. We build both from the same inputs and compare the assembled arrays
and the altitude/velocity/power/phi time-series across a dense time grid.
"""

import numpy as np
import pytest

import PhlyGreen as pg
import _sample_configs as sc
from PhlyGreen.Mission.Profile import Profile
from PhlyGreen.Mission.Profile_legacy import Profile as LegacyProfile


def _prepare_aircraft(config_fn):
    """Wire an aircraft and run ReadInput (no design) so profiles can be built."""
    flags, kwargs = config_fn()
    ac = pg.build_aircraft()
    ac.Configuration = flags['Configuration']
    ac.HybridType = flags['HybridType']
    ac.AircraftType = flags['AircraftType']
    ac.weight.Class = flags['weight_class']
    ac.ReadInput(
        kwargs['AerodynamicsInput'], kwargs['ConstraintsInput'], kwargs['MissionInput'],
        kwargs['EnergyInput'], kwargs['MissionStages'], kwargs['DiversionStages'],
        WellToTankInput=kwargs.get('WellToTankInput'), CellInput=kwargs.get('CellInput'),
        ClimateImpactInput=kwargs.get('ClimateImpactInput'),
    )
    return ac


def _build_both(config_fn):
    ac = _prepare_aircraft(config_fn)
    new = Profile(ac)
    new.DefineMission()
    legacy = LegacyProfile(ac)
    legacy.DefineMission()
    return new, legacy


@pytest.mark.parametrize("config_fn", [sc.hybrid_parallel_config, sc.traditional_config],
                         ids=["hybrid", "traditional"])
def test_assembled_arrays_match_legacy(config_fn):
    new, legacy = _build_both(config_fn)
    assert np.allclose(np.asarray(new.Breaks, float), np.asarray(legacy.Breaks, float))
    assert new.MissionTime2 == pytest.approx(legacy.MissionTime2)
    assert new.MissionTime == pytest.approx(legacy.MissionTime)
    assert np.allclose(np.asarray(new.Velocities, float), np.asarray(legacy.Velocities, float))
    assert np.allclose(np.asarray(new.HTMission, float), np.asarray(legacy.HTMission, float))


@pytest.mark.parametrize("config_fn", [sc.hybrid_parallel_config, sc.traditional_config],
                         ids=["hybrid", "traditional"])
def test_timeseries_match_legacy(config_fn):
    new, legacy = _build_both(config_fn)
    grid = np.linspace(0, float(legacy.MissionTime2), 400)
    for t in grid:
        assert float(new.Altitude(t)) == pytest.approx(float(legacy.Altitude(t)), abs=1e-6)
        assert float(new.Velocity(t)) == pytest.approx(float(legacy.Velocity(t)), abs=1e-6)
        assert float(new.PowerExcess(t)) == pytest.approx(float(legacy.PowerExcess(t)), abs=1e-6)


def test_supplied_power_ratio_matches_legacy():
    new, legacy = _build_both(sc.hybrid_parallel_config)
    assert np.allclose(new.SPW, legacy.SPW)
    grid = np.linspace(1, float(legacy.MissionTime2) - 1, 400)
    for t in grid:
        assert float(new.SuppliedPowerRatio(t)) == pytest.approx(
            float(legacy.SuppliedPowerRatio(t)), abs=1e-9)
