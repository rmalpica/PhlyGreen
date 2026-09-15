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


# ---------------------------------------------------------------------------
# Turbofan (CFM56-class) emission-index surrogate
# ---------------------------------------------------------------------------
# A combustor calibration does not transfer between engine classes, so the turbofan ships its
# own artifact alongside the PW127 one rather than replacing it. Every PW127 assertion above
# must keep passing.

import os as _os

from PhlyGreen.Systems.Powertrain.emissions_surrogate import default_model_path

_TF_PKL = default_model_path('Turbofan')
needs_tf = pytest.mark.skipif(
    not _os.path.isfile(_TF_PKL),
    reason="turbofan EI map not built (emissions_pipeline/build_turbofan_surrogate.py)")

# ICAO LTO reference for the CFM56-7B27E, the engine the CRN is calibrated to.
_ICAO_TF = {"approach": (0.30, 9.09, 2.82), "climb": (0.85, 17.89, 0.17),
            "takeoff": (1.00, 23.94, 0.31)}


def test_artifact_selection_is_by_configuration():
    """Picking the wrong combustor map silently would be worse than failing loudly."""
    assert default_model_path('Turbofan').endswith('Emission_Model_Turbofan.pkl')
    for cfg in ('Traditional', 'Hybrid', None):
        assert default_model_path(cfg).endswith('Emission_Model_PW127.pkl')


@needs_tf
def test_turbofan_surrogate_loads_with_the_same_interface():
    es = EmissionSurrogate(_TF_PKL)
    assert es.inputs == ['alt_ft', 'Mach', 'PC']      # keeps predict_op usable
    assert set(es.outputs) == {'EINOX', 'EICO', 'EIUHC'}
    lo, hi = es._ranges['PC']
    assert lo <= 0.30 and hi >= 1.0


@needs_tf
def test_turbofan_nox_brackets_the_cfm56_certification_value():
    """Unanchored: the CRN predicts the level, so this is a real check, not a tautology."""
    es = EmissionSurrogate(_TF_PKL)
    to = es.predict_op(0.0, 0.25, 1.00)
    assert 15.0 < to['EINOX'] < 36.0, f"take-off EINOx {to['EINOX']:.1f} vs ICAO 23.94"
    assert to['EICO'] > 0.0 and to['EIUHC'] >= 0.0


@needs_tf
def test_turbofan_nox_trends_are_physical():
    es = EmissionSurrogate(_TF_PKL)
    sl = es.predict_op(0.0, 0.25, 1.00)['EINOX']
    # NOx is thermal: it rises with combustor pressure and temperature, so it falls with
    # altitude and rises with thrust fraction.
    assert es.predict_op(30000.0, 0.75, 1.00)['EINOX'] < sl
    assert es.predict_op(0.0, 0.25, 0.30)['EINOX'] < sl


@needs_tf
def test_turbofan_nox_exceeds_the_turboprop_at_high_power():
    """A turbofan runs a hotter, richer combustor: its NOx index should be clearly higher."""
    tf = EmissionSurrogate(_TF_PKL).predict_op(0.0, 0.25, 1.00)['EINOX']
    tp = EmissionSurrogate(default_model_path('Traditional')).predict_op(0.0, 0.25, 1.00)['EINOX']
    assert tf > tp


@needs_tf
def test_turbofan_surrogate_reproduces_its_training_data():
    """Fit quality, measured the way the quantities are actually fitted.

    CO and UHC span two decades and are fitted in log10 space, so a *linear* correlation on
    them is dominated by a handful of large values and reads low (0.78 / 0.40) even when the
    fit is good. The honest metrics are the log-space correlation and the median relative
    error; NOx, which spans well under a decade, is checked in linear space as well.
    """
    import csv
    csv_path = _os.path.join(_os.path.dirname(_TF_PKL), 'Turbofan_Emission_Map.csv')
    rows = list(csv.DictReader(open(csv_path)))
    X = np.array([[float(r['alt_ft']), float(r['Mach']), float(r['PC'])] for r in rows])
    pred = EmissionSurrogate(_TF_PKL).predict(X)

    for col in ('EINOX', 'EICO', 'EIUHC'):
        truth = np.array([float(r[col]) for r in rows])
        got = np.asarray(pred[col])
        log_corr = np.corrcoef(np.log10(np.clip(truth, 1e-9, None)),
                               np.log10(np.clip(got, 1e-9, None)))[0, 1]
        median_err = float(np.median(np.abs(got - truth) / np.maximum(truth, 1e-12)))
        assert log_corr > 0.9, f"{col}: log-space correlation {log_corr:.3f}"
        assert median_err < 0.10, f"{col}: median relative error {100*median_err:.1f} %"

    nox = np.array([float(r['EINOX']) for r in rows])
    assert np.corrcoef(nox, np.asarray(pred['EINOX']))[0, 1] > 0.9


@needs_tf
@pytest.mark.slow
def test_climateimpact_surrogate_path_runs_for_a_turbofan():
    """The Phase-1 guard that refused this path for a Turbofan must now be gone."""
    import sys
    sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), '..', '..', 'examples'))
    import PhlyGreen as pg
    from PhlyGreen.config import ClimateImpactConfig
    from common import turbofan_config

    cfg = turbofan_config()
    cfg.climate_impact = ClimateImpactConfig(H=100, N=1.6e7, Y=30, einox_model='Surrogate',
                                             wtw_co2=8.30e-3, grid_co2=9.36e-2)
    ac = pg.build_aircraft()
    ac.configure(cfg)
    ac.MissionType = 'Continue'      # the EI path integrates the continuous mission
    ac.climateimpact.calculate_mission_emissions()
    e = ac.climateimpact.mission_emissions
    assert e['nox'] > 0 and e['co'] > 0 and e['uhc'] >= 0
    assert e['co2'] > 0
    # the surrogate must have been the turbofan one, not the packaged turboprop default
    assert 'Turbofan' in ac.climateimpact.emission_surrogate.tag or \
           ac.climateimpact.emission_surrogate.tag.startswith('CFM56')
