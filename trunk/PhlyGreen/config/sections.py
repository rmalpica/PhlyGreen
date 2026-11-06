"""Typed configuration sections mirroring the legacy input dictionaries.

These replace deeply nested, unvalidated dicts with dataclasses that have named fields,
defaults, IDE autocomplete, and validation. Each still serializes back to the exact
legacy dict via :meth:`to_dict`, so the underlying subsystems are untouched.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from ._base import DictConfig, ConfigError


def _check_fraction(name, value):
    if value is not None and not (0.0 <= value <= 1.0):
        raise ConfigError(f"{name} must be in [0, 1], got {value!r}")


def _check_efficiency(name, value):
    if value is not None and not (0.0 < value <= 1.0):
        raise ConfigError(f"{name} must be in (0, 1], got {value!r}")


def _check_positive(name, value):
    if value is not None and value <= 0:
        raise ConfigError(f"{name} must be > 0, got {value!r}")


# ---------------------------------------------------------------------------
# Mission
# ---------------------------------------------------------------------------

@dataclass
class MissionConfig(DictConfig):
    """High-level mission parameters (``MissionInput``)."""

    range_mission: float = None       # nautical miles
    range_diversion: float = None     # nautical miles
    beta_start: Optional[float] = None  # DEPRECATED, ignored: the mass at the start of the
    #                                     climb follows from the computed ground segments
    payload_weight: float = None      # kg
    crew_weight: float = None         # kg
    range_loiter: Optional[float] = None   # nautical miles (optional)
    time_loiter: Optional[float] = None    # minutes (optional)
    # ground segments (not in the flown profile); None = ICAO LTO defaults
    taxi_out_time: Optional[float] = None        # [min] (default 13)
    taxi_in_time: Optional[float] = None         # [min] (default 13)
    taxi_power_fraction: Optional[float] = None  # of the take-off propulsive power (default 0.07)
    takeoff_time: Optional[float] = None         # [min] at take-off power (default 0.7)
    takeoff_power_fraction: Optional[float] = None  # of the take-off propulsive power, averaged
    #                                                 over takeoff_time (default 1.0)
    # battery fraction of the taxi propulsive power (battery configurations only); default:
    # the take-off phi, i.e. the phi of the profile's 'Takeoff' stage
    taxi_phi: Optional[float] = None

    _KEY_MAP = {
        "range_mission": "Range Mission",
        "range_diversion": "Range Diversion",
        "beta_start": "Beta start",
        "payload_weight": "Payload Weight",
        "crew_weight": "Crew Weight",
        "range_loiter": "Range Loiter",
        "time_loiter": "Time Loiter",
        "taxi_out_time": "Taxi Out Time",
        "taxi_in_time": "Taxi In Time",
        "taxi_power_fraction": "Taxi Power Fraction",
        "takeoff_time": "Takeoff Time",
        "takeoff_power_fraction": "Takeoff Power Fraction",
        "taxi_phi": "Taxi Supplied Power Ratio",
    }

    def __post_init__(self):
        _check_fraction("beta_start", self.beta_start)
        _check_fraction("taxi_power_fraction", self.taxi_power_fraction)
        _check_fraction("takeoff_power_fraction", self.takeoff_power_fraction)
        _check_fraction("taxi_phi", self.taxi_phi)
        for n in ("taxi_out_time", "taxi_in_time", "takeoff_time"):
            v = getattr(self, n)
            if v is not None and v < 0:
                raise ConfigError(f"{n} must be >= 0, got {v!r}")
        for n in ("range_mission", "range_diversion", "payload_weight", "crew_weight"):
            _check_positive(n, getattr(self, n))


# ---------------------------------------------------------------------------
# Energy / powertrain efficiencies
# ---------------------------------------------------------------------------

@dataclass
class EnergyConfig(DictConfig):
    """Powertrain energy and efficiency parameters (``EnergyInput``)."""

    Ef: float = None                          # fuel specific energy [J/kg]
    contingency_fuel: float = None            # final reserve [kg]
    eta_gas_turbine_model: Optional[str] = None
    eta_gas_turbine: Optional[float] = None
    eta_gearbox: Optional[float] = None
    eta_propulsive_model: Optional[str] = None
    eta_propulsive: Optional[float] = None
    eta_electric_motor: Optional[float] = None     # parallel config
    eta_electric_motor_1: Optional[float] = None   # serial config (generator)
    eta_electric_motor_2: Optional[float] = None   # serial config (motor)
    eta_pmad: Optional[float] = None
    specific_power_powertrain: Optional[List[float]] = None  # [thermal, electric motor] W/kg
    specific_power_pmad: Optional[float] = None              # power-management / inverter [W/kg]
    # --- hydrogen fuel-cell parameters (Hydrogen configuration only) ---
    fc_model: Optional[str] = None              # key into FC_Database
    i_rated: Optional[float] = None             # rated current density [A/cm^2]
    v_cell_design: Optional[float] = None       # design cell voltage [V]
    stack_power_density: Optional[float] = None  # [W/kg]
    bop_mass_ratio: Optional[float] = None       # balance-of-plant mass / stack mass
    stack_design_voltage: Optional[float] = None  # nominal stack (bus) design voltage [V]; sets the
    #                                               cell count N_cells = V_stack / V_cell_design.
    #                                               Affects the stack voltage and per-cell area only,
    #                                               not the masses. Defaults to 1000 V if unset.
    h2_gravimetric_index: Optional[float] = None  # usable H2 / (H2 + tank) mass
    # phase of the fuel-cell product water -> heat rejected to the coolant: 'auto' (default,
    # from the cathode-exhaust saturation) or a fraction in [0, 1] (0 = liquid/HHV, 1 = vapour/LHV)
    fc_product_water_vapour_fraction: Optional[Any] = None
    fc_cathode_inlet_rh: Optional[float] = None   # cathode inlet relative humidity at T_op [-]
    h2_fuel_margin: Optional[float] = None        # extra H2 loaded on top of the flown H2, as a
    #                                               fraction of it (unusable/residual, feed);
    #                                               default 0.05
    # --- thermal-management (heat-exchanger) specific powers [W of heat / kg of HEX] ---
    # The cryogenic-H2-cooled fuel-cell HEX is far more mass-effective than the battery HEX
    # (which must reject to ambient via a liquid loop + ram-air), so they are separate inputs.
    hex_specific_power_h2: Optional[float] = None       # fuel-cell (H2-cooled) HEX [W/kg]
    hex_specific_power_battery: Optional[float] = None  # battery HEX [W/kg]
    # --- simple (Class I) battery for fuel-cell + battery hybrids ---
    battery_specific_energy: Optional[float] = None  # [Wh/kg]
    battery_specific_power: Optional[float] = None   # [W/kg]
    battery_usable_soc: Optional[float] = None       # usable state-of-charge fraction
    # --- Class-II propulsion model selection + nominal (design) powers ---
    eta_electric_motor_model: Optional[str] = None   # 'constant' | 'Smart'
    gt_design_power: Optional[float] = None           # nominal gas-turbine power [W]
    em_design_power: Optional[float] = None           # nominal electric-motor power [W]
    em_design_voltage: Optional[float] = None         # [V]
    em_design_rpm: Optional[float] = None             # [rpm]
    # --- serial "range-extender" strategy (Hybrid + HybridType 'Serial') ---
    # When set, the serial gas turbine runs at this constant shaft power for the whole mission
    # (only the altitude/velocity lapse affects its efficiency); the battery absorbs the surplus
    # (recharging) when propulsive demand is lower and covers the deficit when it is higher.
    gt_rated_power: Optional[float] = None            # constant serial GT shaft power [W]
    battery_charge_efficiency: Optional[float] = None  # in-flight recharge efficiency [-] (default 1.0)
    # --- turbofan (Configuration 'Turbofan') ---
    # The turbofan is a single overall-efficiency node in the powertrain graph:
    # eta_o = F*V/(mdot_f*LHV), which is exactly equivalent to a TSFC map since
    # TSFC = V/(eta_o*LHV). The nominal (SLS) thrust must be chosen before the mission,
    # for the same reason the Class-II gas turbine needs a nominal power.
    turbofan_design_thrust: Optional[float] = None    # nominal SLS thrust, all engines [N]
    engine_thrust_to_weight: Optional[float] = None   # installed engine T/W [N/N], ~5.5 for a CFM56 class
    opr: Optional[float] = None                       # overall pressure ratio [-], used by the Filippone NOx model
    turbofan_model_path: Optional[str] = None         # alternative fitted engine map (.pkl); packaged artifact if unset

    _KEY_MAP = {
        "Ef": "Ef",
        "contingency_fuel": "Contingency Fuel",
        "eta_gas_turbine_model": "Eta Gas Turbine Model",
        "eta_gas_turbine": "Eta Gas Turbine",
        "eta_gearbox": "Eta Gearbox",
        "eta_propulsive_model": "Eta Propulsive Model",
        "eta_propulsive": "Eta Propulsive",
        "eta_electric_motor": "Eta Electric Motor",
        "eta_electric_motor_1": "Eta Electric Motor 1",
        "eta_electric_motor_2": "Eta Electric Motor 2",
        "eta_pmad": "Eta PMAD",
        "specific_power_powertrain": "Specific Power Powertrain",
        "specific_power_pmad": "Specific Power PMAD",
        "fc_model": "Model",
        "i_rated": "i Rated",
        "v_cell_design": "V Cell Design",
        "stack_power_density": "Stack Power Density",
        "bop_mass_ratio": "BoP Mass Ratio",
        "stack_design_voltage": "Stack Design Voltage",
        "h2_gravimetric_index": "H2 Gravimetric Index",
        "fc_product_water_vapour_fraction": "FC Product Water Vapour Fraction",
        "fc_cathode_inlet_rh": "FC Cathode Inlet RH",
        "h2_fuel_margin": "H2 Fuel Margin",
        "hex_specific_power_h2": "HEX Specific Power H2",
        "hex_specific_power_battery": "HEX Specific Power Battery",
        "battery_specific_energy": "Battery Specific Energy",
        "battery_specific_power": "Battery Specific Power",
        "battery_usable_soc": "Battery Usable SOC",
        "eta_electric_motor_model": "Eta Electric Motor Model",
        "gt_design_power": "GT Design Power",
        "em_design_power": "EM Design Power",
        "em_design_voltage": "EM Design Voltage",
        "em_design_rpm": "EM Design RPM",
        "gt_rated_power": "GT Rated Power",
        "battery_charge_efficiency": "Battery Charge Efficiency",
        "turbofan_design_thrust": "Turbofan Design Thrust",
        "engine_thrust_to_weight": "Engine Thrust to Weight",
        "opr": "OPR",
        "turbofan_model_path": "Turbofan Model Path",
    }

    def __post_init__(self):
        _check_positive("Ef", self.Ef)
        for n in ("eta_gas_turbine", "eta_gearbox", "eta_propulsive", "eta_electric_motor",
                  "eta_electric_motor_1", "eta_electric_motor_2", "eta_pmad"):
            _check_efficiency(n, getattr(self, n))


# ---------------------------------------------------------------------------
# Battery cell
# ---------------------------------------------------------------------------

@dataclass
class CellConfig(DictConfig):
    """Battery cell / pack parameters (``CellInput``)."""

    cell_class: str = None                 # 'I' or 'II'
    model: Optional[str] = None            # cell chemistry name (Class II)
    specific_power: Optional[float] = None     # W/kg
    specific_energy: Optional[float] = None    # Wh/kg
    minimum_soc: Optional[float] = None
    pack_voltage: Optional[float] = None       # V (Class II)
    initial_temperature: Optional[float] = None    # C (Class II)
    max_operative_temperature: Optional[float] = None  # C (Class II)
    Ebat: Optional[float] = None           # J (Class I)
    pbat: Optional[float] = None           # W/kg (Class I)

    # --- optional Class-II thermal-management & degradation analysis (post-design only) ---
    # These never affect the baseline sizing; they parametrize
    # ``aircraft.battery.thermal_degradation_analysis()`` (ground fast-charge cooling load and
    # cycle-life). All default to off / sensible values when the analysis is invoked.
    charge_c_rate: Optional[float] = None           # ground fast-charge C-rate [1/h]
    discharge_c_rate: Optional[float] = None         # representative discharge C-rate [1/h]
    maximum_soc: Optional[float] = None              # SOC at full charge (default 1.0)
    eol_capacity: Optional[float] = None             # end-of-life capacity fraction (e.g. 0.8)
    coolant_temperature: Optional[float] = None      # ground coolant inlet temperature [C]
    ground_cooling_coefficient: Optional[float] = None  # ground cold-plate h [W/m^2K]

    _KEY_MAP = {
        "cell_class": "Class",
        "model": "Model",
        "specific_power": "SpecificPower",
        "specific_energy": "SpecificEnergy",
        "minimum_soc": "Minimum SOC",
        "pack_voltage": "Pack Voltage",
        "initial_temperature": "Initial temperature",
        "max_operative_temperature": "Max operative temperature",
        "Ebat": "Ebat",
        "pbat": "pbat",
        "charge_c_rate": "Charge C-Rate",
        "discharge_c_rate": "Discharge C-Rate",
        "maximum_soc": "Maximum SOC",
        "eol_capacity": "EoL Capacity",
        "coolant_temperature": "Coolant Temperature",
        "ground_cooling_coefficient": "Ground Cooling Coefficient",
    }

    def __post_init__(self):
        if self.cell_class not in (None, "I", "II"):
            raise ConfigError(f"cell_class must be 'I' or 'II', got {self.cell_class!r}")
        _check_fraction("minimum_soc", self.minimum_soc)


# ---------------------------------------------------------------------------
# Well-to-tank
# ---------------------------------------------------------------------------

@dataclass
class WellToTankConfig(DictConfig):
    """Well-to-tank efficiency chain (``WellToTankInput``)."""

    eta_charge: float = None
    eta_grid: float = None
    eta_extraction: float = None
    eta_production: float = None
    eta_transportation: float = None

    _KEY_MAP = {
        "eta_charge": "Eta Charge",
        "eta_grid": "Eta Grid",
        "eta_extraction": "Eta Extraction",
        "eta_production": "Eta Production",
        "eta_transportation": "Eta Transportation",
    }

    def __post_init__(self):
        for n in ("eta_charge", "eta_grid", "eta_extraction", "eta_production", "eta_transportation"):
            _check_efficiency(n, getattr(self, n))


# ---------------------------------------------------------------------------
# Climate impact (all optional; subsystem reads via .get)
# ---------------------------------------------------------------------------

@dataclass
class ClimateImpactConfig(DictConfig):
    """Climate-impact parameters (``ClimateImpactInput``)."""

    H: Optional[float] = None
    N: Optional[float] = None
    Y: Optional[float] = None
    einox_model: Optional[str] = None
    wtw_co2: Optional[float] = None
    grid_co2: Optional[float] = None

    _KEY_MAP = {
        "H": "H",
        "N": "N",
        "Y": "Y",
        "einox_model": "EINOx_model",
        "wtw_co2": "WTW_CO2",
        "grid_co2": "Grid_CO2",
    }


# ---------------------------------------------------------------------------
# Aerodynamics (structured polar + Cl/Cd values)
# ---------------------------------------------------------------------------

@dataclass
class AerodynamicsConfig(DictConfig):
    """Aerodynamic polar and lift/drag limits (``AerodynamicsInput``).

    ``analytic_polar`` / ``numerical_polar`` hold the ``{'type': ..., 'input': ...}``
    structure expected by the Aerodynamics subsystem; exactly one should be set.
    """

    take_off_cl: float = None
    landing_cl: float = None
    minimum_cl: float = None
    cd0: float = None
    analytic_polar: Optional[Dict[str, Any]] = None
    numerical_polar: Optional[Dict[str, Any]] = None
    # --- transonic ('compressible') polar: Korn/Lock wave-drag geometry ---
    # Only read when analytic_polar selects the 'compressible' polar; ignored otherwise,
    # so existing configurations are unaffected.
    wing_sweep: Optional[float] = None          # quarter-chord sweep [deg]
    thickness_to_chord: Optional[float] = None  # mean t/c [-]
    korn_kappa: Optional[float] = None          # airfoil technology factor: 0.87 conventional, 0.95 supercritical

    _KEY_MAP = {
        "take_off_cl": "Take Off Cl",
        "landing_cl": "Landing Cl",
        "minimum_cl": "Minimum Cl",
        "cd0": "Cd0",
        "analytic_polar": "AnalyticPolar",
        "numerical_polar": "NumericalPolar",
        "wing_sweep": "Wing Sweep",
        "thickness_to_chord": "Thickness to Chord",
        "korn_kappa": "Korn Kappa",
    }

    def __post_init__(self):
        _check_positive("cd0", self.cd0)
        if self.analytic_polar is None and self.numerical_polar is None:
            raise ConfigError("Aerodynamics requires either analytic_polar or numerical_polar")


# ---------------------------------------------------------------------------
# Constraints (DISA + per-phase points stored wholesale)
# ---------------------------------------------------------------------------

# Phase keys consumed by Constraint.SetInput, and whether each is required.
_CONSTRAINT_PHASES = (
    "Cruise", "AEO Climb", "OEI Climb", "Take Off", "Landing", "Turn",
    "Ceiling", "Acceleration",
)


@dataclass
class TankConfig(DictConfig):
    """Liquid-hydrogen tank configuration (``TankInput``, Hydrogen configuration only)."""

    max_diameter: float = None          # max tank outer diameter [m]
    number_of_tanks: int = 1
    tank_model: str = "Svensson_Default"  # key into TANK_Database
    fuselage_diameter: Optional[float] = None

    _KEY_MAP = {
        "max_diameter": "Max Diameter",
        "number_of_tanks": "Number of Tanks",
        "tank_model": "Tank Model",
        "fuselage_diameter": "Fuselage Diameter",
    }

    def __post_init__(self):
        _check_positive("max_diameter", self.max_diameter)
        if self.number_of_tanks is not None and self.number_of_tanks < 1:
            raise ConfigError(f"number_of_tanks must be >= 1, got {self.number_of_tanks!r}")


@dataclass
class TMSConfig(DictConfig):
    """Thermal-management system (``TMSInput``, fuel-cell configurations).

    ``tms_class='I'`` (default): exchanger mass = peak fuel-cell heat / the EnergyConfig
    ``hex_specific_power_h2``. ``tms_class='II'``: geometric FC_SPEC model (coolant -> LH2
    exchanger, then coolant -> ram-air exchangers, pump, ram-air drag); needs CoolProp.
    Every other field only applies to Class II; ``None`` keeps the model default.
    """

    tms_class: str = "I"
    coolant: Optional[str] = None                 # CoolProp name, e.g. 'INCOMP::MEG-30%'
    coolant_delta_t: Optional[float] = None       # coolant temperature drop over the loop [K]
    max_volume_per_unit: Optional[float] = None   # [m^3] per exchanger unit
    max_weight_per_unit: Optional[float] = None   # [kg] per exchanger unit
    max_hex_units: Optional[int] = None           # max parallel units per role
    ram_air_delta_t: Optional[float] = None       # design ram-air temperature rise [K]
    ram_air_max_effectiveness: Optional[float] = None  # cap on the ram-air temperature rise
    h2_approach_delta_t: Optional[float] = None   # H2 leaves its exchanger at T_op - this [K]
    h2_supply_pressure: Optional[float] = None    # LH2 supply pressure [Pa]
    loop_pressure_drop: Optional[float] = None    # coolant-loop pressure rise of the pump [Pa]
    pump_efficiency: Optional[float] = None
    pump_motor_efficiency: Optional[float] = None
    pump_specific_power: Optional[float] = None        # [W/kg]
    pump_motor_specific_power: Optional[float] = None  # [W/kg]
    ram_recovery: Optional[float] = None          # fraction of dynamic pressure the intake recovers
    takeoff_coolant_overtemperature: Optional[float] = None  # [K] coolant/stack allowed above T_op
    #                                                          at the take-off point only (default 0)

    _KEY_MAP = {
        "tms_class": "TMS Class",
        "coolant": "TMS Coolant",
        "coolant_delta_t": "TMS Coolant DeltaT",
        "max_volume_per_unit": "TMS Max Volume Per Unit",
        "max_weight_per_unit": "TMS Max Weight Per Unit",
        "max_hex_units": "TMS Max HEX Units",
        "ram_air_delta_t": "TMS Ram Air DeltaT",
        "ram_air_max_effectiveness": "TMS Ram Air Max Effectiveness",
        "h2_approach_delta_t": "TMS H2 Approach DeltaT",
        "h2_supply_pressure": "TMS H2 Supply Pressure",
        "loop_pressure_drop": "TMS Loop Pressure Drop",
        "pump_efficiency": "TMS Pump Efficiency",
        "pump_motor_efficiency": "TMS Pump Motor Efficiency",
        "pump_specific_power": "TMS Pump Specific Power",
        "pump_motor_specific_power": "TMS Pump Motor Specific Power",
        "ram_recovery": "TMS Ram Recovery",
        "takeoff_coolant_overtemperature": "TMS Takeoff Coolant Overtemperature",
    }

    def __post_init__(self):
        if self.tms_class not in ("I", "II"):
            raise ConfigError(f"tms_class must be 'I' or 'II', got {self.tms_class!r}")
        for name in ("coolant_delta_t", "max_volume_per_unit", "max_weight_per_unit",
                     "max_hex_units", "ram_air_delta_t", "h2_approach_delta_t",
                     "h2_supply_pressure", "loop_pressure_drop", "pump_specific_power",
                     "pump_motor_specific_power"):
            _check_positive(name, getattr(self, name))
        if self.takeoff_coolant_overtemperature is not None and self.takeoff_coolant_overtemperature < 0:
            raise ConfigError("takeoff_coolant_overtemperature must be >= 0")
        for name in ("ram_air_max_effectiveness", "pump_efficiency", "pump_motor_efficiency",
                     "ram_recovery"):
            _check_efficiency(name, getattr(self, name))


@dataclass
class ConstraintsConfig(DictConfig):
    """Constraint-diagram definition (``ConstraintsInput``).

    Each phase is a plain dict (heterogeneous keys per phase, e.g. ``kTO``/``sTO`` for
    Take Off, ``Climb Gradient`` for OEI Climb). The config validates DISA and that the
    phases the subsystem reads are present, while serializing each phase dict verbatim.
    """

    disa: float = 0.0
    phases: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def __post_init__(self):
        missing = [p for p in _CONSTRAINT_PHASES if p not in self.phases]
        if missing:
            raise ConfigError(f"ConstraintsConfig missing required phases: {missing}")

    def to_dict(self):
        out = {"DISA": self.disa}
        out.update({name: dict(point) for name, point in self.phases.items()})
        return out

    @classmethod
    def from_dict(cls, data):
        if data is None:
            return None
        data = dict(data)
        disa = data.pop("DISA", 0.0)
        return cls(disa=disa, phases=data)
