"""Class-II efficiency models feeding the powertrain graph.

Verifies that (a) with no model set the graph uses the constant EtaEM (so legacy/golden
behavior is preserved), and (b) attaching a Class-II model makes the electric-motor
efficiency — and hence the solved power ratios — depend on the operating point. Also
exercises the fuel-cell + battery architecture at the power-ratio level.
"""

import numpy as np
import pytest

import PhlyGreen as pg
import _sample_configs as sc
from PhlyGreen.Systems.Powertrain.efficiency import MotorEfficiencyModel, ConstantEfficiency


def _parallel_powertrain():
    ac = pg.build_aircraft()
    ac.Configuration = 'Hybrid'
    ac.HybridType = 'Parallel'
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


def test_no_model_uses_constant_eta_em():
    pt = _parallel_powertrain()
    assert pt.em_model is None
    # the electric-motor efficiency falls back to the constant EtaEM from EnergyInput.
    assert pt.eta('electric_motor', 8000, 120, 1e6) == pt.EtaEM


def test_constant_model_matches_constant_eta_em():
    pt = _parallel_powertrain()
    baseline = pt.Hybrid(0.3, 8000, 120, 1e6)
    pt.em_model = ConstantEfficiency(pt.EtaEM)
    assert np.allclose(pt.Hybrid(0.3, 8000, 120, 1e6), baseline)


def test_class_ii_motor_makes_ratios_operating_point_dependent():
    pt = _parallel_powertrain()
    pt.em_model = MotorEfficiencyModel(design_kw=2000, design_v=800, design_rpm=1200)
    # Battery power ratio (index 5) should differ between two power levels because the
    # motor efficiency now varies with load.
    low = pt.Hybrid(0.3, 8000, 120, 3e5)[5]
    high = pt.Hybrid(0.3, 8000, 120, 3e6)[5]
    assert low != pytest.approx(high)


def test_fuelcell_battery_power_ratios():
    pt = _parallel_powertrain()
    pt.EtaFC = 0.55
    # phi = 0 -> no battery contribution; hydrogen supplies everything.
    ratios = pt.PowerRatioFuelCellBattery(0.0, 6000, 120, 1e6)
    assert len(ratios) == 7
    assert ratios[6] == pytest.approx(1.0)   # Pp1 normalized
    assert ratios[2] == pytest.approx(0.0)   # Pbat
    # phi > 0 -> battery is used and hydrogen demand drops.
    ratios_hybrid = pt.PowerRatioFuelCellBattery(0.3, 6000, 120, 1e6)
    assert ratios_hybrid[2] > 0
    assert ratios_hybrid[0] < ratios[0]


def test_fuelcell_database_available():
    from PhlyGreen.Systems.FuelCell import FC_Database
    assert "PEMFC_GoodPerformance" in FC_Database
    assert FC_Database["PEMFC_GoodPerformance"]["Voc"] == pytest.approx(1.145)


def test_gas_turbine_universal_map_scales_with_engine_size():
    """The map is universal; runtime applies the size penalty keyed on nominal power."""
    from PhlyGreen.Systems.Powertrain.gas_turbine_surrogate import GasTurbineResponseSurface
    gt = GasTurbineResponseSurface()
    # Same operating point (SL, M0.2, ~70 % load) -> smaller engine is less efficient.
    etas = [gt.predict(hp, 0.0, 0.2, 0.7 * hp)[0] for hp in (500, 1000, 2750, 6000)]
    assert all(a < b for a, b in zip(etas, etas[1:]))     # monotonically increasing with size
    # At the reference size the scaling is a no-op (factor 1).
    assert 0.05 < etas[2] < 0.45


def test_gas_turbine_power_lapses_with_altitude():
    from PhlyGreen.Systems.Powertrain.gas_turbine_surrogate import GasTurbineResponseSurface
    gt = GasTurbineResponseSurface()
    pmax_sl = gt.predict(2750, 0.0, 0.3, 1500)[2]
    pmax_alt = gt.predict(2750, 20000, 0.3, 1500)[2]
    assert pmax_alt < pmax_sl                              # available power lapses
    assert gt.predict(2750, 20000, 0.3, 1500)[3] is True   # and becomes power-limited
