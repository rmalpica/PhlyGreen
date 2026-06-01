"""Unit tests for the typed configuration objects (PhlyGreen.config).

Covers the lossless round-trip contract (dict -> dataclass -> dict) and validation.
The end-to-end equivalence (designing through the config path matches the dict path) is
checked in tests/regression/test_config_equivalence.py.
"""

import pytest

import _sample_configs as sc
from PhlyGreen.config import (
    ConfigError, MissionConfig, EnergyConfig, CellConfig, WellToTankConfig,
    ClimateImpactConfig, AerodynamicsConfig, ConstraintsConfig, StagesConfig, Segment,
)


# --- round-trip fidelity: from_dict(d).to_dict() == d -----------------------

ROUND_TRIP_CASES = [
    (MissionConfig, sc.MISSION_INPUT),
    (EnergyConfig, sc.ENERGY_INPUT),
    (CellConfig, sc.CELL_INPUT),
    (WellToTankConfig, sc.WELL_TO_TANK_INPUT),
    (ClimateImpactConfig, sc.CLIMATE_IMPACT_INPUT),
    (AerodynamicsConfig, sc.AERODYNAMICS_INPUT),
    (ConstraintsConfig, sc.CONSTRAINTS_INPUT),
    (StagesConfig, sc.MISSION_STAGES),
    (StagesConfig, sc.DIVERSION_STAGES),
]


@pytest.mark.parametrize("cls,sample", ROUND_TRIP_CASES,
                         ids=[c.__name__ + str(i) for i, (c, _) in enumerate(ROUND_TRIP_CASES)])
def test_dict_roundtrip_is_lossless(cls, sample):
    assert cls.from_dict(sample).to_dict() == sample


def test_aircraft_config_reproduces_read_input_args():
    config = sc.hybrid_parallel_aircraft_config()
    positional, kwargs = config.read_input_args()
    # positional order: aero, constraints, mission, energy, mission_stages, diversion_stages
    assert positional[0] == sc.AERODYNAMICS_INPUT
    assert positional[2] == sc.MISSION_INPUT
    assert positional[4] == sc.MISSION_STAGES
    assert kwargs["CellInput"] == sc.CELL_INPUT
    assert kwargs["WellToTankInput"] == sc.WELL_TO_TANK_INPUT


# --- validation -------------------------------------------------------------

def test_beta_start_out_of_range_raises():
    with pytest.raises(ConfigError):
        MissionConfig(range_mission=750, range_diversion=220, beta_start=1.5,
                      payload_weight=4560, crew_weight=500)


def test_negative_range_raises():
    with pytest.raises(ConfigError):
        MissionConfig(range_mission=-1, range_diversion=220, beta_start=0.97,
                      payload_weight=4560, crew_weight=500)


def test_efficiency_above_one_raises():
    with pytest.raises(ConfigError):
        EnergyConfig(Ef=43.5e6, eta_gearbox=1.2)


def test_cell_class_must_be_I_or_II():
    with pytest.raises(ConfigError):
        CellConfig(cell_class="III")


def test_aero_requires_a_polar():
    with pytest.raises(ConfigError):
        AerodynamicsConfig(take_off_cl=1.9, landing_cl=1.9, minimum_cl=0.2, cd0=0.017)


def test_constraints_missing_phase_raises():
    with pytest.raises(ConfigError):
        ConstraintsConfig(disa=0.0, phases={"Cruise": {}})


def test_segment_phi_out_of_range_raises():
    with pytest.raises(ConfigError):
        Segment(name="Cruise", segment_type="ConstantMachCruise",
                inputs={"Mach": 0.4, "Altitude": 8000}, phi_start=0.0, phi_end=2.0)


def test_segment_with_type_requires_inputs():
    with pytest.raises(ConfigError):
        Segment(name="Climb1", segment_type="ConstantRateClimb")


def test_takeoff_segment_serializes_to_phi_only():
    seg = Segment(name="Takeoff", phi=0.0)
    assert seg.to_stage_dict() == {"Supplied Power Ratio": {"phi": 0.0}}
