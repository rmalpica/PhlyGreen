"""Baseline aircraft configurations shared by the examples.

These build a small regional turboprop (ATR-like) design specification using the typed
config objects from ``PhlyGreen.config``. Read the comments, then change numbers and re-run
an example to see how the design responds.

Two baselines are provided:

* :func:`traditional_config` — a conventional (fuel-only) aircraft. Fast to size; good for
  parameter sweeps, optimization and uncertainty studies.
* :func:`hybrid_config` — a parallel hybrid-electric aircraft with a battery.

Both return a fully-validated :class:`PhlyGreen.config.AircraftConfig`.
"""

from PhlyGreen.config import (
    AircraftConfig, AerodynamicsConfig, ConstraintsConfig, MissionConfig,
    EnergyConfig, CellConfig, WellToTankConfig, ClimateImpactConfig,
    StagesConfig, Segment,
)


# --- the constraint diagram (sizing requirements) ---------------------------
# Each entry is one point the aircraft must satisfy: a speed, the altitude, the weight
# fraction (Beta) at which it applies, and any phase-specific extras (takeoff distance,
# climb gradient, ...). DISA is the temperature offset from the standard atmosphere.
def _constraints():
    return ConstraintsConfig(disa=0.0, phases={
        'Cruise':       {'Speed': 0.5, 'Speed Type': 'Mach', 'Beta': 0.95, 'Altitude': 8000.},
        'AEO Climb':    {'Speed': 210, 'Speed Type': 'KCAS', 'Beta': 0.97, 'Altitude': 6000., 'ROC': 5},
        'OEI Climb':    {'Speed': 1.2 * 34.5, 'Speed Type': 'TAS', 'Beta': 1., 'Altitude': 0., 'Climb Gradient': 0.021},
        'Take Off':     {'Speed': 90, 'Speed Type': 'TAS', 'Beta': 1., 'Altitude': 100., 'kTO': 1.2, 'sTO': 950},
        'Landing':      {'Speed': 59., 'Speed Type': 'TAS', 'Altitude': 500.},
        'Turn':         {'Speed': 210, 'Speed Type': 'KCAS', 'Beta': 0.9, 'Altitude': 5000, 'Load Factor': 1.1},
        'Ceiling':      {'Speed': 0.5, 'Beta': 0.8, 'Altitude': 9500, 'HT': 0.5},
        'Acceleration': {'Mach 1': 0.3, 'Mach 2': 0.4, 'DT': 180, 'Altitude': 6000, 'Beta': 0.9},
    })


def _aerodynamics():
    # A simple quadratic drag polar: Cd = Cd0 + Cl^2 / (pi * AR * e).
    return AerodynamicsConfig(
        take_off_cl=1.9, landing_cl=1.9, minimum_cl=0.20, cd0=0.017,
        analytic_polar={'type': 'Quadratic', 'input': {'AR': 11, 'e_osw': 0.8}},
    )


def _mission():
    return MissionConfig(
        range_mission=750,     # design range [nautical miles]
        range_diversion=220,   # diversion range [nautical miles]
        beta_start=0.97,       # mass fraction at start of climb (taxi/takeoff already burnt)
        payload_weight=4560,   # [kg]
        crew_weight=500,       # [kg]
    )


# --- the flight profile: an ordered list of segments ------------------------
# Each segment is one phase of flight. Climbs/descents specify a gradient (CB) and a true
# airspeed; cruise specifies a Mach and altitude and automatically fills the remaining
# range. 'phi' (or phi_start/phi_end) is the hybrid supplied-power ratio — ignored for a
# Traditional aircraft, used for a Hybrid one.
def _mission_stages():
    return StagesConfig(segments=[
        Segment('Takeoff', phi=0.0),
        Segment('Climb1', 'ConstantRateClimb', {'CB': 0.16, 'Speed': 77,  'StartAltitude': 100,  'EndAltitude': 1500}, phi_start=0, phi_end=0),
        Segment('Climb2', 'ConstantRateClimb', {'CB': 0.08, 'Speed': 120, 'StartAltitude': 1500, 'EndAltitude': 4500}, phi_start=0, phi_end=0),
        Segment('Climb3', 'ConstantRateClimb', {'CB': 0.07, 'Speed': 125, 'StartAltitude': 4500, 'EndAltitude': 8000}, phi_start=0, phi_end=0),
        Segment('Cruise', 'ConstantMachCruise', {'Mach': 0.4, 'Altitude': 8000}, phi_start=0, phi_end=0.5),
        Segment('Descent1', 'ConstantRateDescent', {'CB': -0.04, 'Speed': 90, 'StartAltitude': 8000, 'EndAltitude': 200}, phi_start=0, phi_end=0),
    ])


def _diversion_stages():
    return StagesConfig(segments=[
        Segment('Climb1', 'ConstantRateClimb', {'CB': 0.08, 'Speed': 110, 'StartAltitude': 200, 'EndAltitude': 3100}, phi_start=0, phi_end=0),
        Segment('Cruise', 'ConstantMachCruise', {'Mach': 0.35, 'Altitude': 3100}, phi_start=0, phi_end=0),
        Segment('Descent1', 'ConstantRateDescent', {'CB': -0.04, 'Speed': 90, 'StartAltitude': 3100, 'EndAltitude': 200}, phi_start=0, phi_end=0),
    ])


def _energy():
    # Component efficiencies and specific powers of the propulsion chain.
    return EnergyConfig(
        Ef=43.5e6,                 # fuel specific energy [J/kg] (Jet-A)
        contingency_fuel=130,      # final reserve fuel [kg]
        eta_gas_turbine_model='constant', eta_gas_turbine=0.22,
        eta_gearbox=0.96,
        eta_propulsive_model='constant', eta_propulsive=0.9,
        eta_electric_motor=0.98, eta_pmad=0.99,
        eta_electric_motor_1=0.96, eta_electric_motor_2=0.96,
        specific_power_powertrain=[3900, 7700],  # [thermal, electric] W/kg
        specific_power_pmad=[2200, 2200, 2200],  # W/kg
    )


def traditional_config():
    """A conventional fuel-only ATR-like aircraft (fast to size)."""
    return AircraftConfig(
        configuration='Traditional', aircraft_type='ATR', weight_class='I',
        aerodynamics=_aerodynamics(), constraints=_constraints(),
        mission=_mission(), energy=_energy(),
        mission_stages=_mission_stages(), diversion_stages=_diversion_stages(),
    )


def hybrid_config():
    """A parallel hybrid-electric ATR-like aircraft with a battery pack."""
    cell = CellConfig(
        cell_class='II', model='Finger-Cell-Thermal',
        specific_power=8000, specific_energy=1500, minimum_soc=0.2,
        pack_voltage=800, initial_temperature=25, max_operative_temperature=50,
    )
    well_to_tank = WellToTankConfig(
        eta_charge=0.95, eta_grid=1., eta_extraction=1., eta_production=1., eta_transportation=0.25)
    climate = ClimateImpactConfig(H=100, N=1.6e7, Y=30, einox_model='Filippone',
                                  wtw_co2=8.30e-3, grid_co2=9.36e-2)
    return AircraftConfig(
        configuration='Hybrid', hybrid_type='Parallel', aircraft_type='ATR', weight_class='I',
        aerodynamics=_aerodynamics(), constraints=_constraints(),
        mission=_mission(), energy=_energy(),
        mission_stages=_mission_stages(), diversion_stages=_diversion_stages(),
        cell=cell, well_to_tank=well_to_tank, climate_impact=climate,
    )
