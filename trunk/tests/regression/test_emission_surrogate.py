"""Tests for the gas-turbine emission-index surrogate and its ClimateImpact integration."""

import numpy as np
import pytest

import PhlyGreen as pg
from PhlyGreen.Systems.Powertrain.emissions_surrogate import EmissionSurrogate
import _sample_configs as sc


def _traditional_climate_config(einox):
    """A Traditional ATR design carrying a ClimateImpact model with the chosen NOx model."""
    from PhlyGreen.config import (AircraftConfig, AerodynamicsConfig, ConstraintsConfig,
                                  MissionConfig, EnergyConfig, StagesConfig, WellToTankConfig,
                                  ClimateImpactConfig)
    cd = dict(sc.CLIMATE_IMPACT_INPUT); cd['EINOx_model'] = einox
    return AircraftConfig(
        configuration='Traditional', aircraft_type='ATR', weight_class='I',
        aerodynamics=AerodynamicsConfig.from_dict(sc.AERODYNAMICS_INPUT),
        constraints=ConstraintsConfig.from_dict(sc.CONSTRAINTS_INPUT),
        mission=MissionConfig.from_dict(sc.MISSION_INPUT),
        energy=EnergyConfig.from_dict(sc.ENERGY_INPUT),
        mission_stages=StagesConfig.from_dict(sc.MISSION_STAGES),
        diversion_stages=StagesConfig.from_dict(sc.DIVERSION_STAGES),
        well_to_tank=WellToTankConfig.from_dict(sc.WELL_TO_TANK_INPUT),
        climate_impact=ClimateImpactConfig.from_dict(cd),
    )


def test_packaged_surrogate_loads_and_predicts():
    es = EmissionSurrogate()                       # packaged PW127 default (no path)
    assert es.inputs == ['alt_ft', 'Mach', 'PC']
    assert set(es.outputs) == {'EINOX', 'EICO', 'EIUHC'}
    to = es.predict_op(0.0, 0.0, 1.0)              # SLS take-off ~ certification NOx 19 g/kg
    assert 12.0 < to['EINOX'] < 26.0
    assert to['EICO'] > 0.0 and to['EIUHC'] >= 0.0
    # NOx falls with altitude (physical), and out-of-domain inputs stay finite (clipped)
    assert es.predict_op(30000, 0.45, 1.0)['EINOX'] < to['EINOX']
    assert np.isfinite(es.predict_op(0, 0, 0.0)['EINOX'])   # PC below training min -> clipped


def test_packaged_surrogate_reproduces_training_data():
    import pandas as pd
    from PhlyGreen.Systems.Powertrain import train_emission_surrogate as T
    df = pd.read_csv(T.CSV_PATH)
    pred = EmissionSurrogate().predict(df[['alt_ft', 'Mach', 'PC']].to_numpy(float))
    assert np.corrcoef(pred['EINOX'], df['EINOX'])[0, 1] > 0.9     # NOx
    assert np.corrcoef(pred['EICO'], df['EICO'])[0, 1] > 0.9       # CO


@pytest.mark.slow
def test_climateimpact_surrogate_path():
    a_f = pg.build_aircraft(); a_f.configure(_traditional_climate_config('Filippone'))
    a_f.MissionType = 'Continue'; a_f.climateimpact.calculate_mission_emissions()
    a_s = pg.build_aircraft(); a_s.configure(_traditional_climate_config('Surrogate'))
    a_s.MissionType = 'Continue'; a_s.climateimpact.calculate_mission_emissions()
    fil, sur = a_f.climateimpact.mission_emissions, a_s.climateimpact.mission_emissions

    # Filippone gives NOx only; the surrogate adds CO and UHC.
    assert fil.get('co') is None and fil.get('uhc') is None
    assert sur['nox'] > 0.0 and sur['co'] > 0.0 and sur['uhc'] >= 0.0
    assert sur['nox'] != pytest.approx(fil['nox'])
    # CO2 comes from the same fixed-EI path either way.
    assert sur['co2'] == pytest.approx(fil['co2'], rel=1e-6)


def test_einox_model_rejects_unknown():
    from PhlyGreen.ClimateImpact.ClimateImpact import ClimateImpact
    ci = ClimateImpact(aircraft=None)
    ci.EINOx_model = 'Surrogate'      # accepted
    with pytest.raises(ValueError):
        ci.EINOx_model = 'Nonsense'
