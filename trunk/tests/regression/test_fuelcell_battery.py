"""Tests for the fuel-cell + battery hybrid configuration."""

import copy

import pytest

import PhlyGreen as pg
from PhlyGreen.config import (
    AircraftConfig, AerodynamicsConfig, ConstraintsConfig, MissionConfig,
    EnergyConfig, StagesConfig, ConfigError,
)
import _sample_configs as sc


def _fcb_config(cruise_phi=0.1):
    energy = EnergyConfig(
        Ef=120e6, eta_gearbox=0.96, eta_pmad=0.99, eta_electric_motor=0.96,
        eta_gas_turbine_model='constant', eta_gas_turbine=0.22,
        eta_propulsive_model='constant', eta_propulsive=0.9,
        specific_power_powertrain=[3900, 7700],
        fc_model='PEMFC_GoodPerformance', i_rated=2.5, v_cell_design=0.5,
        stack_power_density=3000, bop_mass_ratio=0.40,
        battery_specific_energy=250, battery_specific_power=1500, battery_usable_soc=0.8,
    )
    stages = copy.deepcopy(sc.MISSION_STAGES)
    stages['Cruise']['Supplied Power Ratio'] = {'phi_start': cruise_phi, 'phi_end': cruise_phi}
    return AircraftConfig(
        configuration='FuelCellBattery', aircraft_type='ATR', weight_class='I',
        aerodynamics=AerodynamicsConfig.from_dict(sc.AERODYNAMICS_INPUT),
        constraints=ConstraintsConfig.from_dict(sc.CONSTRAINTS_INPUT),
        mission=MissionConfig.from_dict(sc.MISSION_INPUT), energy=energy,
        mission_stages=StagesConfig.from_dict(stages),
        diversion_stages=StagesConfig.from_dict(sc.DIVERSION_STAGES),
    )


def test_fuelcell_battery_is_a_valid_configuration():
    _fcb_config()  # must not raise
    with pytest.raises(ConfigError):
        AircraftConfig(configuration='FuelCellPlusUnicorn', aircraft_type='ATR')


@pytest.mark.slow
def test_fuelcell_battery_design_closes_and_uses_both_sources():
    aircraft = pg.build_aircraft()
    aircraft.configure(_fcb_config(cruise_phi=0.1))
    r = aircraft.results()
    assert r.WTO > 0
    assert aircraft.weight.WH2_Fuel > 0     # fuel cell burns hydrogen
    assert r.WBat > 0                        # battery has mass (it is used)
    assert r.WPT > 0                         # fuel-cell system mass
    # mass breakdown sums to WTO
    w = aircraft.weight
    total = (w.WStructure + w.WPT + w.WBat + w.WH2_Fuel + w.WTank + w.WHeat_Exchanger
             + w.WPayload + w.WCrew + w.final_reserve)
    assert total == pytest.approx(w.WTO, rel=1e-3)


@pytest.mark.slow
def test_no_battery_when_phi_zero():
    aircraft = pg.build_aircraft()
    aircraft.configure(_fcb_config(cruise_phi=0.0))
    # With no battery share, the battery mass is zero and hydrogen does all the work.
    assert aircraft.weight.WBat == pytest.approx(0.0)
    assert aircraft.weight.WH2_Fuel > 0


@pytest.mark.slow
def test_more_hybridization_grows_the_battery():
    light = pg.run_design(_fcb_config(cruise_phi=0.05))
    heavy = pg.run_design(_fcb_config(cruise_phi=0.12))
    # On this cruise-dominated mission, more battery share -> a (much) bigger battery.
    assert heavy.WBat > light.WBat
