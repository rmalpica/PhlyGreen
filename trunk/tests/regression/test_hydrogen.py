"""Tests for the hydrogen fuel-cell configuration.

Covers the fuel-cell physics in isolation (polarization curve, sizing, operating point)
and a full hydrogen aircraft design closing end to end.
"""

import numpy as np
import pytest

import PhlyGreen as pg
from PhlyGreen.config import (
    AircraftConfig, AerodynamicsConfig, ConstraintsConfig, MissionConfig,
    EnergyConfig, StagesConfig, ConfigError,
)
import _sample_configs as sc


def _hydrogen_config(v_cell_design=0.5):
    energy = EnergyConfig(
        Ef=120e6, eta_gearbox=0.96, eta_pmad=0.99, eta_electric_motor=0.96,
        eta_gas_turbine_model='constant', eta_gas_turbine=0.22,
        eta_propulsive_model='constant', eta_propulsive=0.9,
        specific_power_powertrain=[3900, 7700],
        fc_model='PEMFC_GoodPerformance', i_rated=2.5, v_cell_design=v_cell_design,
        stack_power_density=3000, bop_mass_ratio=0.40, h2_gravimetric_index=0.35,
    )
    return AircraftConfig(
        configuration='Hydrogen', aircraft_type='ATR', weight_class='I',
        aerodynamics=AerodynamicsConfig.from_dict(sc.AERODYNAMICS_INPUT),
        constraints=ConstraintsConfig.from_dict(sc.CONSTRAINTS_INPUT),
        mission=MissionConfig.from_dict(sc.MISSION_INPUT),
        energy=energy,
        mission_stages=StagesConfig.from_dict(sc.MISSION_STAGES),
        diversion_stages=StagesConfig.from_dict(sc.DIVERSION_STAGES),
    )


# --- fuel-cell physics in isolation -----------------------------------------

def _ready_fuelcell():
    aircraft = pg.build_aircraft()
    aircraft.configure(_hydrogen_config(), design=False)  # runs fuelcell.SetInput()
    return aircraft.fuelcell


def test_polarization_curve_decreases_with_current():
    fc = _ready_fuelcell()
    voltages = [fc.PolarizationCurve(i, fc.Target_Press) for i in (0.1, 0.5, 1.0, 1.5)]
    assert all(v2 < v1 for v1, v2 in zip(voltages, voltages[1:]))  # monotone down
    assert voltages[0] < fc.Voc                                    # below open-circuit


def test_fuelcell_sizing_sets_geometry_and_positive_mass():
    fc = _ready_fuelcell()
    fc.aircraft.DesignPW = 200.0   # needed by the sizing heuristic
    mass = fc.ComputeAndStoreWeights(WTO=20000.0)
    assert mass > 0
    assert fc.N_cells > 0
    assert fc.A_cell_reale > 0
    assert fc.P_fc_rated > 0


def test_system_efficiency_is_a_sensible_fraction():
    fc = _ready_fuelcell()
    fc.aircraft.DesignPW = 200.0
    fc.ComputeAndStoreWeights(WTO=20000.0)
    eta = fc.ComputeSystemEfficiency(i_dens=1.0, alt=6000.0)
    assert 0.0 < eta < 1.0


# --- full hydrogen design ---------------------------------------------------

@pytest.mark.slow
def test_hydrogen_design_closes():
    aircraft = pg.build_aircraft()
    aircraft.configure(_hydrogen_config())
    r = aircraft.results()
    assert r.WTO > 0
    assert aircraft.weight.WH2_Fuel > 0          # burns hydrogen
    assert aircraft.weight.WPT > 0               # fuel-cell system has mass
    assert aircraft.weight.WTank > 0             # hydrogen storage has mass
    # mass breakdown should add up to the take-off weight
    w = aircraft.weight
    total = (w.WStructure + w.WPT + w.WH2_Fuel + w.WTank + w.WHeat_Exchanger
             + w.WPayload + w.WCrew + w.final_reserve)
    assert total == pytest.approx(w.WTO, rel=1e-3)


@pytest.mark.slow
def test_design_voltage_changes_the_design():
    wto_low = pg.run_design(_hydrogen_config(v_cell_design=0.45)).WTO
    wto_high = pg.run_design(_hydrogen_config(v_cell_design=0.60)).WTO
    assert wto_low != pytest.approx(wto_high)    # design voltage matters


def test_hydrogen_is_a_valid_configuration():
    # 'Hydrogen' is accepted; nonsense is still rejected.
    _hydrogen_config()  # must not raise
    with pytest.raises(ConfigError):
        AircraftConfig(configuration='Kerosene', aircraft_type='ATR')
