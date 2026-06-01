"""Prove the graph-based Traditional/Hybrid reproduce the legacy hand-coded solvers.

The public ``Powertrain.Traditional``/``Hybrid`` now delegate to the component graph; the
original matrix solvers are preserved as ``_traditional_legacy``/``_hybrid_legacy``. Here
we sweep flight conditions and the hybridization ratio and assert the power-ratio vectors
match. (The end-to-end design equivalence is additionally guarded by the golden masters.)
"""

import numpy as np
import pytest

import PhlyGreen as pg
import _sample_configs as sc

ALTS = [0.0, 4000.0, 8000.0]
VELS = [80.0, 120.0, 160.0]
PWRS = [1.0e5, 1.0e6]
PHIS = [0.0, 0.1, 0.3, 0.5]


def _configured_powertrain(configuration, hybrid_type):
    """Wire + ReadInput an aircraft so Powertrain.SetInput has populated efficiencies."""
    ac = pg.build_aircraft()
    ac.Configuration = configuration
    ac.HybridType = hybrid_type
    ac.AircraftType = 'ATR'
    ac.weight.Class = 'I'
    _, kwargs = sc.hybrid_parallel_config()
    ac.ReadInput(
        kwargs['AerodynamicsInput'], kwargs['ConstraintsInput'], kwargs['MissionInput'],
        kwargs['EnergyInput'], kwargs['MissionStages'], kwargs['DiversionStages'],
        WellToTankInput=kwargs['WellToTankInput'], CellInput=kwargs['CellInput'],
        ClimateImpactInput=kwargs['ClimateImpactInput'],
    )
    return ac.powertrain


def test_traditional_graph_matches_legacy():
    pt = _configured_powertrain('Traditional', None)
    for alt in ALTS:
        for vel in VELS:
            for pwr in PWRS:
                got = pt.Traditional(alt, vel, pwr)
                ref = pt._traditional_legacy(alt, vel, pwr)
                assert np.allclose(got, ref), f"alt={alt} vel={vel} pwr={pwr}"


@pytest.mark.parametrize("hybrid_type", ["Parallel", "Serial"])
def test_hybrid_graph_matches_legacy(hybrid_type):
    pt = _configured_powertrain('Hybrid', hybrid_type)
    for phi in PHIS:
        for alt in ALTS:
            for vel in VELS:
                for pwr in PWRS:
                    got = pt.Hybrid(phi, alt, vel, pwr)
                    ref = pt._hybrid_legacy(phi, alt, vel, pwr)
                    assert np.allclose(got, ref), \
                        f"{hybrid_type} phi={phi} alt={alt} vel={vel} pwr={pwr}"
