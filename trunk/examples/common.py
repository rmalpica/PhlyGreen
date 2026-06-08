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

import PhlyGreen.Utilities.Units as Units
from PhlyGreen.config import (
    AircraftConfig, AerodynamicsConfig, ConstraintsConfig, MissionConfig,
    EnergyConfig, CellConfig, WellToTankConfig, ClimateImpactConfig,
    StagesConfig, Segment, TankConfig,
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
# The climb is split into five short segments whose climb gradient (CB) *decreases* with
# altitude. This approximates a **constant-throttle climb**: a turbine's available power lapses
# with altitude, so a single fixed-rate climb would run the engine from light part-load near the
# ground up to a power-limited 100% near cruise (see the throttle plot in example 16). Tapering
# the climb rate keeps the gas-turbine throttle roughly constant (~0.65-0.87 on the Class-II GT,
# never power-limited). The rates run ~2400 ft/min near the ground down to ~600 ft/min approaching
# cruise; the *initial* rate matches a normal climb, so the peak power (and the sizing of
# power-limited fuel cells / batteries) is unchanged.
def _mission_stages():
    return StagesConfig(segments=[
        Segment('Takeoff', phi=0.0),
        Segment('Climb1', 'ConstantRateClimb', {'CB': 0.152, 'Speed': 80,  'StartAltitude': 100,  'EndAltitude': 1200}, phi_start=0, phi_end=0),
        Segment('Climb2', 'ConstantRateClimb', {'CB': 0.097, 'Speed': 100, 'StartAltitude': 1200, 'EndAltitude': 2600}, phi_start=0, phi_end=0),
        Segment('Climb3', 'ConstantRateClimb', {'CB': 0.062, 'Speed': 115, 'StartAltitude': 2600, 'EndAltitude': 4200}, phi_start=0, phi_end=0),
        Segment('Climb4', 'ConstantRateClimb', {'CB': 0.039, 'Speed': 125, 'StartAltitude': 4200, 'EndAltitude': 6000}, phi_start=0, phi_end=0),
        Segment('Climb5', 'ConstantRateClimb', {'CB': 0.024, 'Speed': 130, 'StartAltitude': 6000, 'EndAltitude': 8000}, phi_start=0, phi_end=0),
        Segment('Cruise', 'ConstantMachCruise', {'Mach': 0.4, 'Altitude': 8000}, phi_start=0, phi_end=0.5),
        Segment('Descent1', 'ConstantRateDescent', {'CB': -0.04, 'Speed': 90, 'StartAltitude': 8000, 'EndAltitude': 200}, phi_start=0, phi_end=0),
    ])


def _diversion_stages():
    # Same constant-throttle idea for the diversion climb (200 -> 3100 m): the climb gradient
    # tapers with altitude so the turbine throttle stays roughly constant instead of ramping up.
    return StagesConfig(segments=[
        Segment('Climb1', 'ConstantRateClimb', {'CB': 0.152, 'Speed': 80,  'StartAltitude': 200,  'EndAltitude': 1200}, phi_start=0, phi_end=0),
        Segment('Climb2', 'ConstantRateClimb', {'CB': 0.097, 'Speed': 100, 'StartAltitude': 1200, 'EndAltitude': 2600}, phi_start=0, phi_end=0),
        Segment('Climb3', 'ConstantRateClimb', {'CB': 0.062, 'Speed': 115, 'StartAltitude': 2600, 'EndAltitude': 3100}, phi_start=0, phi_end=0),
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


def _energy_hydrogen(v_cell_design=0.5):
    """Energy/efficiency inputs for a hydrogen fuel-cell aircraft.

    Note `Ef` is now the hydrogen lower heating value (~120 MJ/kg). The fuel-cell stack is
    described by a model in the FC database plus a few design knobs.
    """
    return EnergyConfig(
        Ef=120e6,                          # hydrogen LHV [J/kg]
        eta_gearbox=0.96, eta_pmad=0.99, eta_electric_motor=0.96,
        eta_gas_turbine_model='constant', eta_gas_turbine=0.22,
        eta_propulsive_model='constant', eta_propulsive=0.9,
        specific_power_powertrain=[3900, 7700],
        # --- fuel-cell stack ---
        fc_model='PEMFC_GoodPerformance',  # see PhlyGreen.Systems.FuelCell.FC_Database
        i_rated=2.5,                       # rated current density [A/cm^2]
        v_cell_design=v_cell_design,       # design cell voltage [V] (try sweeping this)
        stack_power_density=3000,          # [W/kg]
        bop_mass_ratio=0.40,               # balance-of-plant mass / stack mass
        h2_gravimetric_index=0.35,         # usable H2 / (H2 + tank) mass
    )


def hydrogen_config(v_cell_design=0.5, tank=False):
    """A hydrogen fuel-cell (electric) ATR-like aircraft — no battery, no gas turbine.

    With ``tank=True`` a cryogenic LH2 tank (TankConfig) is attached, enabling the
    physics-based tank sizing and the transient tank thermodynamics (requires CoolProp).
    Without it, hydrogen storage uses a simple gravimetric-index mass model.
    """
    tank_cfg = None
    if tank:
        tank_cfg = TankConfig(max_diameter=2.4, number_of_tanks=1,
                              tank_model='Svensson_Default', fuselage_diameter=2.8)
    return AircraftConfig(
        configuration='Hydrogen', aircraft_type='ATR', weight_class='I',
        aerodynamics=_aerodynamics(), constraints=_constraints(),
        mission=_mission(), energy=_energy_hydrogen(v_cell_design),
        mission_stages=_mission_stages(), diversion_stages=_diversion_stages(),
        tank=tank_cfg,
    )


def _mission_stages_with_cruise_phi(cruise_phi):
    """Mission stages where the cruise battery fraction (phi) is set to ``cruise_phi``."""
    stages = _mission_stages()
    for seg in stages.segments:
        if seg.name == 'Cruise':
            seg.phi_start = cruise_phi
            seg.phi_end = cruise_phi
    return stages


def fuelcell_battery_config(cruise_phi=0.15, tank=False):
    """A fuel-cell + battery hybrid: the battery supplies ``cruise_phi`` of cruise power.

    Demonstrates hybridizing a hydrogen fuel cell with a battery. ``phi`` is the fraction of
    propulsive power taken from the battery (the fuel cell supplies the rest). With ``tank=True``
    a cryogenic LH2 tank (TankConfig) is attached, so the hydrogen storage is sized with the
    physics tank model and its thermodynamic state can be tracked (requires CoolProp).
    """
    energy = _energy_hydrogen()
    energy.battery_specific_energy = 250.0   # Wh/kg
    energy.battery_specific_power = 1500.0    # W/kg
    energy.battery_usable_soc = 0.8
    tank_cfg = TankConfig(max_diameter=2.4, number_of_tanks=1, tank_model='Svensson_Default',
                          fuselage_diameter=2.8) if tank else None
    return AircraftConfig(
        configuration='FuelCellBattery', aircraft_type='ATR', weight_class='I',
        aerodynamics=_aerodynamics(), constraints=_constraints(),
        mission=_mission(), energy=energy,
        mission_stages=_mission_stages_with_cruise_phi(cruise_phi),
        diversion_stages=_diversion_stages(), tank=tank_cfg,
    )


def hybrid_config(battery_class='II', hybrid_type='Parallel'):
    """A hybrid-electric ATR-like aircraft with a battery pack.

    ``battery_class='II'`` uses the detailed cell-level thermal model; ``'I'`` uses the
    simple specific-energy/specific-power model.

    ``hybrid_type`` selects the powertrain topology:

    - ``'Parallel'`` (default): the gas turbine and the electric motor both drive the
      propeller; ``eta_electric_motor`` is the motor efficiency.
    - ``'Serial'``: the gas turbine drives a generator that feeds the electric bus, and an
      electric motor drives the propeller; all shaft power flows through the electric chain.
      The two conversions use ``eta_electric_motor_1`` (generator) and
      ``eta_electric_motor_2`` (motor), already set in ``_energy()``.
    """
    if battery_class == 'I':
        cell = CellConfig(cell_class='I', specific_energy=1500, specific_power=8000,
                          minimum_soc=0.2)
    else:
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
        configuration='Hybrid', hybrid_type=hybrid_type, aircraft_type='ATR', weight_class='I',
        aerodynamics=_aerodynamics(), constraints=_constraints(),
        mission=_mission(), energy=_energy(),
        mission_stages=_mission_stages(), diversion_stages=_diversion_stages(),
        cell=cell, well_to_tank=well_to_tank, climate_impact=climate,
    )


def atr_flops_input():
    """FLOPS (Class-II structural) input for an ATR42-like aircraft (imperial units).

    Set this on the aircraft (`aircraft.FLOPSInput = atr_flops_input()`) and use
    `weight_class='II'` to size the airframe with the FLOPS component-mass model instead of
    the Class-I regression.
    """
    return {
        'WING': {'N_ENGINES': 2., 'STRUT_BRACING_FACTOR': 0., 'SPAN': Units.mToft(24.5),
                 'TAPER_RATIO': 0.54, 'THICKNESS_TO_CHORD': 0.15,
                 'AEROELASTIC_TAILORING_FACTOR': 0., 'SWEEP': 0, 'COMPOSITE_FRACTION': 0.2,
                 'ULTIMATE_LOAD_FACTOR': 3.75, 'VAR_SWEEP_MASS_PENALTY': 0.,
                 'LOAD_FRACTION': 1.0, 'SCALER': 1.23},
        'VERTICAL_TAIL': {'AREA': Units.m2toft2(12.7), 'TAPER_RATIO': 0.33,
                          'N_VERTICAL_TAILS': 1., 'SCALER': 1.0},
        'HORIZONTAL_TAIL': {'AREA': Units.m2toft2(11.5), 'TAPER_RATIO': 0.54, 'SCALER': 1.2},
        'FUSELAGE': {'LENGTH': Units.mToft(22.7), 'MAX_HEIGHT': Units.mToft(2.7),
                     'MAX_WIDTH': Units.mToft(2.7), 'NUM_FUSELAGES': 1.,
                     'TOTAL_NUM_FUSELAGE_ENGINES': 0., 'MILITARY_CARGO_FLOOR': False,
                     'SCALER': 1.05},
        'LANDING_GEAR': {'MAIN_GEAR_LENGTH': 102., 'NOSE_GEAR_LENGTH': 67,
                         'MAIN_SCALER': 1.1, 'NOSE_SCALER': 1.0},
        'NACELLE': {'AVG_DIAM': Units.mToft(0.8), 'AVG_LENGTH': Units.mToft(2.1), 'SCALER': 1.0},
        'SYSTEM_EQUIPMENT': {'PLANFORM_AREA': Units.mToft(22.7) * Units.mToft(2.7),
                             'N_PAX': 48, 'N_CREW': 3, 'N_FIRST_CLASS': 6,
                             'N_BUSINESS_CLASS': 0., 'N_TOURIST_CLASS': 42,
                             'PASSENGER_COMPARTMENT_LENGTH': Units.mToft(22.7) * 0.7,
                             'SYSTEM_PRESSURE': 3000, 'CONTROL_SURFACE_AREA_RATIO': 0.1,
                             'ANTIICING_SCALER': 1., 'APU_SCALER': 1.1, 'AVIONICS_SCALER': 1.2,
                             'AC_SCALER': 1.0, 'ELECTRICAL_SCALER': 1.25,
                             'FURNISHING_SCALER': 1.1, 'HYDRAULICS_SCALER': 1.0,
                             'SURFACE_CONTROLS_SCALER': 1.0},
        'PAINT': {'MASS_PER_AREA': 0.037},
        'ENGINE': {'N_ENGINES': 2., 'MAX_SLS_THRUST': 26000, 'MAX_SLS_POWER': 2500,
                   'N_WING_ENGINES': 2, 'N_FUSELAGE_ENGINES': 0},
        'PROPELLER': {'N_BLADES': 6., 'DIAMETER': 13, 'SCALER': 1.},
    }


# ===========================================================================
# Shared output / plotting helpers (used by all the examples)
# ===========================================================================
import os as _os

# All figures land here, resolved relative to this file so the examples work from any CWD.
OUTPUT_DIR = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "_output")


def savefig(fig, name):
    """Save a matplotlib figure into ``examples/_output/`` and print the path."""
    _os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = _os.path.join(OUTPUT_DIR, name)
    fig.savefig(path, dpi=120, bbox_inches="tight")
    print(f"  saved {path}")
    return path


def print_results(aircraft, title="Design results"):
    """Print a rich, human-readable summary of a *designed* aircraft.

    Covers the common scalar outputs plus the full take-off mass breakdown and (when the
    aircraft carries the relevant inputs) the battery pack, hydrogen/tank and well-to-wake
    quantities — so every example is verbose about what it produced.
    """
    from PhlyGreen import postprocess as pp
    r = aircraft.results()
    w = aircraft.weight
    print(f"\n=== {title} ===")
    print(f"  Take-off weight   : {r.WTO:10.1f} kg")
    if r.empty_weight is not None:
        print(f"  Operating empty   : {r.empty_weight:10.1f} kg")
    if r.zero_fuel_weight is not None:
        print(f"  Zero-fuel weight  : {r.zero_fuel_weight:10.1f} kg")
    print(f"  Structure         : {r.WStructure:10.1f} kg")
    print(f"  Powertrain        : {r.WPT:10.1f} kg")
    if r.Wf is not None:
        label = "Hydrogen fuel" if getattr(w, "WH2_Fuel", None) else "Mission fuel"
        print(f"  {label:17s} : {r.Wf:10.1f} kg")
    if r.WBat:
        print(f"  Battery           : {r.WBat:10.1f} kg")
    if getattr(w, "WTank", None):
        print(f"  H2 tank (empty)   : {w.WTank:10.1f} kg")
    if r.WingSurface is not None:
        print(f"  Wing area         : {r.WingSurface:10.1f} m^2")
    if r.engineRating is not None:
        # engineRating is the TOTAL thermal shaft rating (all engines summed).
        n_eng = (aircraft.PropellerInput or {}).get('Number of Engines', 1) \
            if getattr(aircraft, 'PropellerInput', None) else 1
        print(f"  Engine rating     : {r.engineRating/1000:10.1f} kW (total, all engines"
              + (f"; {r.engineRating/1000/n_eng:.1f} kW/engine for {int(n_eng)})" if n_eng and n_eng > 1 else ")"))
    if r.pack_energy is not None:
        # pack_energy is in Wh (cell nominal voltage x capacity); WBat in kg.
        print(f"  Battery pack      : {r.pack_energy/1000:.1f} kWh, {r.pack_power_max/1000:.1f} kW")
        print(f"  Battery config    : S{r.S_number:.0f} / P{r.P_number:.0f} cells, "
              f"{r.pack_energy/r.WBat:.0f} Wh/kg (cell-level specific energy)")
    if r.SourceEnergy is not None:
        print(f"  Well-to-wake      : {r.SourceEnergy/1e6:.1f} MJ source energy, Psi {r.Psi:.4f}")
    print("  --- take-off mass breakdown ---")
    for name, mass in pp.mass_breakdown(aircraft).items():
        print(f"    {name:14s}: {mass:9.1f} kg  ({100*mass/r.WTO:4.1f} %)")
    return r


def design_dashboard(aircraft, name, title=None):
    """Save a 4-panel dashboard for a *designed* aircraft (mission, energy, sizing, mass).

    Uses the generic :mod:`PhlyGreen.postprocess` helpers so it works for every
    configuration (Traditional / Hybrid / Hydrogen / FuelCellBattery). Returns the figure
    path, or ``None`` if matplotlib is unavailable or the mission was not solved.
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from PhlyGreen import postprocess as pp
    except Exception:
        print("  (matplotlib unavailable — skipping dashboard)")
        return None

    try:
        ts = pp.mission_timeseries(aircraft)
    except Exception:
        print("  (no mission solution — skipping dashboard)")
        return None

    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    if title:
        fig.suptitle(title, fontsize=13)

    # (0,0) altitude + true airspeed vs time
    t_min = ts["time"] / 60.0
    ax = axes[0, 0]
    ax.plot(t_min, ts["altitude"], color="tab:blue", label="altitude [m]")
    ax.set_xlabel("time [min]"); ax.set_ylabel("altitude [m]", color="tab:blue")
    axv = ax.twinx()
    axv.plot(t_min, ts["velocity"], color="tab:orange", label="TAS [m/s]")
    axv.set_ylabel("TAS [m/s]", color="tab:orange")
    ax.set_title("Flight profile"); ax.grid(alpha=0.3)

    # (0,1) energy / SOC time series
    try:
        pp.plot_energy_timeseries(aircraft, ax=axes[0, 1])
        axes[0, 1].set_title("Energy / state of charge")
    except Exception:
        axes[0, 1].set_visible(False)

    # (1,0) constraint diagram with the design point
    try:
        pp.plot_constraint_diagram(aircraft, ax=axes[1, 0])
        axes[1, 0].set_title("Constraint diagram")
    except Exception:
        axes[1, 0].set_visible(False)

    # (1,1) take-off mass breakdown
    try:
        pp.plot_mass_breakdown(aircraft, ax=axes[1, 1])
        axes[1, 1].set_title("Take-off mass breakdown")
    except Exception:
        axes[1, 1].set_visible(False)

    fig.tight_layout()
    path = savefig(fig, name)
    plt.close(fig)
    return path
