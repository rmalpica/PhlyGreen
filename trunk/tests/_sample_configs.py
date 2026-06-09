"""Reusable sample input configurations for tests and golden-master generation.

These mirror the dictionaries used in ``trunk/tutorial/tutorial.ipynb`` (the canonical
worked example). They are intentionally expressed as plain dicts so they exercise the
current (legacy) dict-based API; later phases add typed-dataclass equivalents and assert
both paths agree.
"""

# --- shared building blocks -------------------------------------------------

CONSTRAINTS_INPUT = {
    'DISA': 0.,
    'Cruise': {'Speed': 0.5, 'Speed Type': 'Mach', 'Beta': 0.95, 'Altitude': 8000.},
    'AEO Climb': {'Speed': 210, 'Speed Type': 'KCAS', 'Beta': 0.97, 'Altitude': 6000., 'ROC': 5},
    'OEI Climb': {'Speed': 1.2 * 34.5, 'Speed Type': 'TAS', 'Beta': 1., 'Altitude': 0., 'Climb Gradient': 0.021},
    'Take Off': {'Speed': 90, 'Speed Type': 'TAS', 'Beta': 1., 'Altitude': 100., 'kTO': 1.2, 'sTO': 950},
    'Landing': {'Speed': 59., 'Speed Type': 'TAS', 'Altitude': 500.},
    'Turn': {'Speed': 210, 'Speed Type': 'KCAS', 'Beta': 0.9, 'Altitude': 5000, 'Load Factor': 1.1},
    'Ceiling': {'Speed': 0.5, 'Beta': 0.8, 'Altitude': 9500, 'HT': 0.5},
    'Acceleration': {'Mach 1': 0.3, 'Mach 2': 0.4, 'DT': 180, 'Altitude': 6000, 'Beta': 0.9},
}

MISSION_INPUT = {
    'Range Mission': 750,    # nautical miles
    'Range Diversion': 220,  # nautical miles
    'Beta start': 0.97,
    'Payload Weight': 4560,  # kg
    'Crew Weight': 500,      # kg
}

MISSION_STAGES = {
    'Takeoff': {'Supplied Power Ratio': {'phi': 0.}},
    'Climb1': {'type': 'ConstantRateClimb', 'input': {'CB': 0.16, 'Speed': 77, 'StartAltitude': 100, 'EndAltitude': 1500}, 'Supplied Power Ratio': {'phi_start': 0, 'phi_end': 0}},
    'Climb2': {'type': 'ConstantRateClimb', 'input': {'CB': 0.08, 'Speed': 120, 'StartAltitude': 1500, 'EndAltitude': 4500}, 'Supplied Power Ratio': {'phi_start': 0, 'phi_end': 0}},
    'Climb3': {'type': 'ConstantRateClimb', 'input': {'CB': 0.07, 'Speed': 125, 'StartAltitude': 4500, 'EndAltitude': 8000}, 'Supplied Power Ratio': {'phi_start': 0, 'phi_end': 0}},
    'Cruise': {'type': 'ConstantMachCruise', 'input': {'Mach': 0.4, 'Altitude': 8000}, 'Supplied Power Ratio': {'phi_start': 0, 'phi_end': 0.5}},
    'Descent1': {'type': 'ConstantRateDescent', 'input': {'CB': -0.04, 'Speed': 90, 'StartAltitude': 8000, 'EndAltitude': 200}, 'Supplied Power Ratio': {'phi_start': 0.0, 'phi_end': 0.0}},
}

DIVERSION_STAGES = {
    'Climb1': {'type': 'ConstantRateClimb', 'input': {'CB': 0.08, 'Speed': 110, 'StartAltitude': 200, 'EndAltitude': 3100}, 'Supplied Power Ratio': {'phi_start': 0.0, 'phi_end': 0.0}},
    'Cruise': {'type': 'ConstantMachCruise', 'input': {'Mach': 0.35, 'Altitude': 3100}, 'Supplied Power Ratio': {'phi_start': 0.0, 'phi_end': 0.0}},
    'Descent1': {'type': 'ConstantRateDescent', 'input': {'CB': -0.04, 'Speed': 90, 'StartAltitude': 3100, 'EndAltitude': 200}, 'Supplied Power Ratio': {'phi_start': 0.0, 'phi_end': 0.0}},
}

ENERGY_INPUT = {
    'Ef': 43.5 * 10**6,  # [J/kg]
    'Contingency Fuel': 130,  # [kg]
    'Eta Gas Turbine Model': 'constant',
    'Eta Gas Turbine': 0.22,
    'Eta Gearbox': 0.96,
    'Eta Propulsive Model': 'constant',
    'Eta Propulsive': 0.9,
    'Eta Electric Motor 1': 0.96,
    'Eta Electric Motor 2': 0.96,
    'Eta Electric Motor': 0.98,
    'Eta PMAD': 0.99,
    'Specific Power Powertrain': [3900, 5000],  # [thermal, electric motor] [W/kg]
    'Specific Power PMAD': 10000,               # power-management / inverter [W/kg]
}

CELL_INPUT = {
    'Class': 'II',
    'Model': 'Finger-Cell-Thermal',
    'SpecificPower': 8000,    # [W/kg]
    'SpecificEnergy': 1500,   # [Wh/kg]
    'Minimum SOC': 0.2,
    'Pack Voltage': 800,      # [V]
    'Initial temperature': 25,        # [C]
    'Max operative temperature': 50,  # [C]
}

AERODYNAMICS_INPUT = {
    'AnalyticPolar': {'type': 'Quadratic', 'input': {'AR': 11, 'e_osw': 0.8}},
    'Take Off Cl': 1.9,
    'Landing Cl': 1.9,
    'Minimum Cl': 0.20,
    'Cd0': 0.017,
}

WELL_TO_TANK_INPUT = {
    'Eta Charge': 0.95,
    'Eta Grid': 1.,
    'Eta Extraction': 1.,
    'Eta Production': 1.,
    'Eta Transportation': 0.25,
}

CLIMATE_IMPACT_INPUT = {'H': 100, 'N': 1.6e7, 'Y': 30, 'EINOx_model': 'Filippone', 'WTW_CO2': 8.30e-3, 'Grid_CO2': 9.36e-2}

HYDROGEN_ENERGY_INPUT = {
    'Ef': 120 * 10**6,  # hydrogen LHV [J/kg]
    'Eta Gearbox': 0.96,
    'Eta PMAD': 0.99,
    'Eta Electric Motor': 0.96,
    'Eta Gas Turbine Model': 'constant',
    'Eta Gas Turbine': 0.22,
    'Eta Propulsive Model': 'constant',
    'Eta Propulsive': 0.9,
    'Specific Power Powertrain': [3900, 5000],
    'Specific Power PMAD': 10000,
    # --- fuel-cell stack ---
    'Model': 'PEMFC_GoodPerformance',
    'i Rated': 2.5,
    'V Cell Design': 0.5,
    'Stack Power Density': 3000,
    'BoP Mass Ratio': 0.40,
    'H2 Gravimetric Index': 0.35,
}


def hybrid_parallel_config():
    """Return (flags, read_input_kwargs) for the tutorial Hybrid/Parallel ATR design."""
    flags = {'Configuration': 'Hybrid', 'HybridType': 'Parallel', 'AircraftType': 'ATR', 'weight_class': 'I'}
    kwargs = dict(
        AerodynamicsInput=AERODYNAMICS_INPUT,
        ConstraintsInput=CONSTRAINTS_INPUT,
        MissionInput=MISSION_INPUT,
        EnergyInput=ENERGY_INPUT,
        MissionStages=MISSION_STAGES,
        DiversionStages=DIVERSION_STAGES,
        WellToTankInput=WELL_TO_TANK_INPUT,
        CellInput=CELL_INPUT,
        ClimateImpactInput=CLIMATE_IMPACT_INPUT,
    )
    return flags, kwargs


def traditional_config():
    """Return (flags, read_input_kwargs) for a Traditional (thermal-only) ATR design."""
    flags = {'Configuration': 'Traditional', 'HybridType': None, 'AircraftType': 'ATR', 'weight_class': 'I'}
    kwargs = dict(
        AerodynamicsInput=AERODYNAMICS_INPUT,
        ConstraintsInput=CONSTRAINTS_INPUT,
        MissionInput=MISSION_INPUT,
        EnergyInput=ENERGY_INPUT,
        MissionStages=MISSION_STAGES,
        DiversionStages=DIVERSION_STAGES,
    )
    return flags, kwargs


def hydrogen_config():
    """Return (flags, read_input_kwargs) for a Hydrogen fuel-cell ATR design."""
    flags = {'Configuration': 'Hydrogen', 'HybridType': None, 'AircraftType': 'ATR', 'weight_class': 'I'}
    kwargs = dict(
        AerodynamicsInput=AERODYNAMICS_INPUT,
        ConstraintsInput=CONSTRAINTS_INPUT,
        MissionInput=MISSION_INPUT,
        EnergyInput=HYDROGEN_ENERGY_INPUT,
        MissionStages=MISSION_STAGES,
        DiversionStages=DIVERSION_STAGES,
    )
    return flags, kwargs


# --- typed AircraftConfig equivalents (built from the same dicts) -----------

def hybrid_parallel_aircraft_config():
    """The tutorial Hybrid/Parallel design as a typed :class:`AircraftConfig`."""
    from PhlyGreen.config import (
        AircraftConfig, AerodynamicsConfig, ConstraintsConfig, MissionConfig,
        EnergyConfig, StagesConfig, WellToTankConfig, CellConfig, ClimateImpactConfig,
    )
    return AircraftConfig(
        configuration='Hybrid', hybrid_type='Parallel', aircraft_type='ATR', weight_class='I',
        aerodynamics=AerodynamicsConfig.from_dict(AERODYNAMICS_INPUT),
        constraints=ConstraintsConfig.from_dict(CONSTRAINTS_INPUT),
        mission=MissionConfig.from_dict(MISSION_INPUT),
        energy=EnergyConfig.from_dict(ENERGY_INPUT),
        mission_stages=StagesConfig.from_dict(MISSION_STAGES),
        diversion_stages=StagesConfig.from_dict(DIVERSION_STAGES),
        well_to_tank=WellToTankConfig.from_dict(WELL_TO_TANK_INPUT),
        cell=CellConfig.from_dict(CELL_INPUT),
        climate_impact=ClimateImpactConfig.from_dict(CLIMATE_IMPACT_INPUT),
    )


def traditional_aircraft_config():
    """The Traditional design as a typed :class:`AircraftConfig`."""
    from PhlyGreen.config import (
        AircraftConfig, AerodynamicsConfig, ConstraintsConfig, MissionConfig,
        EnergyConfig, StagesConfig,
    )
    return AircraftConfig(
        configuration='Traditional', aircraft_type='ATR', weight_class='I',
        aerodynamics=AerodynamicsConfig.from_dict(AERODYNAMICS_INPUT),
        constraints=ConstraintsConfig.from_dict(CONSTRAINTS_INPUT),
        mission=MissionConfig.from_dict(MISSION_INPUT),
        energy=EnergyConfig.from_dict(ENERGY_INPUT),
        mission_stages=StagesConfig.from_dict(MISSION_STAGES),
        diversion_stages=StagesConfig.from_dict(DIVERSION_STAGES),
    )
