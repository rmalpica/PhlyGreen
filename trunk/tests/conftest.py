"""Shared pytest fixtures for the PhlyGreen test suite.

Provides a helper to run a full design from a sample config and session-scoped
fixtures for the two canonical designs (Hybrid/Parallel and Traditional), so the
(relatively slow) sizing loop runs once and is reused across tests.
"""

import pytest

import PhlyGreen as pg
import _sample_configs as sc


def design_from_config(flags, kwargs):
    """Build a wired aircraft, apply config flags, run ``DesignAircraft``, return it."""
    aircraft = pg.build_aircraft()
    aircraft.Configuration = flags['Configuration']
    aircraft.HybridType = flags['HybridType']
    aircraft.AircraftType = flags['AircraftType']
    aircraft.weight.Class = flags['weight_class']
    aircraft.DesignAircraft(
        kwargs['AerodynamicsInput'], kwargs['ConstraintsInput'], kwargs['MissionInput'],
        kwargs['EnergyInput'], kwargs['MissionStages'], kwargs['DiversionStages'],
        WellToTankInput=kwargs.get('WellToTankInput'),
        CellInput=kwargs.get('CellInput'),
        ClimateImpactInput=kwargs.get('ClimateImpactInput'),
    )
    return aircraft


@pytest.fixture
def wired_aircraft():
    """A freshly wired (not yet designed) aircraft."""
    return pg.build_aircraft()


@pytest.fixture(scope="session")
def hybrid_design():
    """A fully designed Hybrid/Parallel ATR aircraft (tutorial configuration)."""
    flags, kwargs = sc.hybrid_parallel_config()
    return design_from_config(flags, kwargs)


@pytest.fixture(scope="session")
def traditional_design():
    """A fully designed Traditional (thermal-only) ATR aircraft."""
    flags, kwargs = sc.traditional_config()
    return design_from_config(flags, kwargs)
