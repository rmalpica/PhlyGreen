"""Structured, machine-readable results of an aircraft design.

Historically the design outcome was only available as text printed by
:meth:`Aircraft.Print_Aircraft_Design_Summary`. :class:`AircraftResults` collects the
same scalar quantities into a dataclass so callers (tests, optimization/UQ outer loops,
serialization) can consume them programmatically instead of parsing stdout.
"""

from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any

import numpy as np


def _mean_tsfc(aircraft):
    """Thrust-weighted mean TSFC [kg/(N s)] over the mission, or None if unavailable.

    TSFC = mdot_f / F. Both come from quantities the mission already integrated, so this
    reports rather than recomputes: fuel mass is the converged Wf, and the thrust impulse
    is integrated from the propulsive-power history.
    """
    try:
        import numpy as np
        import scipy.integrate as integrate
        m = aircraft.mission
        times = np.concatenate([a.t for a in m.integral_solution])
        beta = np.concatenate([a.y[1] for a in m.integral_solution])
        thrust = np.array([
            aircraft.weight.WTO * aircraft.performance.PoWTO(
                aircraft.DesignWTOoS, b, m.profile.PowerExcess(t), 1,
                m.profile.Altitude(t), m.DISA, m.profile.Velocity(t), 'TAS')
            / m.profile.Velocity(t)
            for t, b in zip(times, beta)])
        impulse = integrate.trapezoid(thrust, times)      # [N s]
        if impulse <= 0:
            return None
        return float(aircraft.weight.Wf / impulse)
    except Exception:
        return None


@dataclass
class AircraftResults:
    """Key sizing outputs of a converged aircraft design.

    Masses are in kg, powers in W, energies in J, areas in m^2. Fields that do not
    apply to a given configuration (e.g. battery fields for a Traditional aircraft)
    are left as ``None``.
    """

    # --- masses -------------------------------------------------------------
    WTO: Optional[float] = None              # take-off weight [kg]
    Wf: Optional[float] = None               # mission fuel (trip + altn + loiter) [kg]
    final_reserve: Optional[float] = None    # contingency / final reserve fuel [kg]
    block_fuel: Optional[float] = None       # Wf + final_reserve [kg]
    WStructure: Optional[float] = None       # structural mass [kg]
    WPT: Optional[float] = None              # powertrain mass [kg]
    WBat: Optional[float] = None             # battery mass (Hybrid only) [kg]
    WCrew: Optional[float] = None            # crew mass [kg]
    WPayload: Optional[float] = None         # payload mass [kg]
    empty_weight: Optional[float] = None     # operating empty weight [kg]
    zero_fuel_weight: Optional[float] = None # zero-fuel weight [kg]

    # --- geometry / powers --------------------------------------------------
    WingSurface: Optional[float] = None      # wing reference area [m^2]
    TO_PP: Optional[float] = None            # take-off propulsive peak power [W]
    Max_PEng: Optional[float] = None         # climb/cruise engine peak power [W]
    Max_PEng_alt: Optional[float] = None     # altitude of Max_PEng [m]
    engineRating: Optional[float] = None     # thermal powertrain SLS rating — TOTAL (all
    #                                          engines); divide by the engine count for per-engine.
    #                                          UNITS DEPEND ON THE CONFIGURATION: shaft power [W]
    #                                          for the power-rated ones, thrust [N] for Turbofan.
    #                                          engineRating_units says which.
    engineRating_units: Optional[str] = None  # 'W' (shaft power) | 'N' (thrust)

    # --- turbofan only ------------------------------------------------------
    DesignTW: Optional[float] = None         # design thrust-to-weight from the T/W diagram [-]
    # For a Turbofan these describe the *sizing-critical* mission point: the one with the
    # largest thrust referred back to sea level (thrust/lapse), which is usually top of
    # climb rather than the largest raw thrust low down.
    Max_Thrust: Optional[float] = None       # thrust there [N]
    Max_Thrust_alt: Optional[float] = None   # altitude of that point [m]
    Max_Thrust_mach: Optional[float] = None  # Mach at that point [-]
    TO_Thrust: Optional[float] = None        # take-off / OEI thrust requirement [N]
    mean_TSFC: Optional[float] = None        # mission-mean thrust-specific fuel consumption [kg/(N s)]

    # --- energy / climate ---------------------------------------------------
    SourceEnergy: Optional[float] = None     # well-to-wake source energy [J]
    Psi: Optional[float] = None              # well-to-wake efficiency index [-]

    # --- battery (Hybrid only) ----------------------------------------------
    battery_class: Optional[str] = None
    pack_energy: Optional[float] = None      # [J] (Class II)
    pack_power_max: Optional[float] = None   # [W] (Class II)
    S_number: Optional[float] = None
    P_number: Optional[float] = None

    # --- provenance ---------------------------------------------------------
    configuration: Optional[str] = None
    hybrid_type: Optional[str] = None
    aircraft_type: Optional[str] = None

    extras: Dict[str, Any] = field(default_factory=dict)

    # A snapshot of every input that produced this design (config flags + the legacy input
    # dicts), so you can keep track of *what was actually solved*. See :meth:`input_summary`.
    inputs: Dict[str, Any] = field(default_factory=dict)

    # Reference to the source aircraft, set by :meth:`from_aircraft`. Not a dataclass field
    # (no annotation), so it stays out of ``to_dict``/``asdict`` and equality.
    _aircraft = None

    @classmethod
    def from_aircraft(cls, aircraft):
        """Build :class:`AircraftResults` from a designed :class:`Aircraft`.

        Reads defensively: any attribute not present for the current configuration is
        left as ``None`` rather than raising.
        """
        w = aircraft.weight
        r = cls()

        r.configuration = getattr(aircraft, 'Configuration', None)
        r.hybrid_type = getattr(aircraft, 'HybridType', None)
        r.aircraft_type = getattr(aircraft, 'AircraftType', None)

        r.WTO = _get(w, 'WTO')
        r.Wf = _get(w, 'Wf')
        r.final_reserve = _get(w, 'final_reserve')
        if r.Wf is not None and r.final_reserve is not None:
            r.block_fuel = r.Wf + r.final_reserve
        r.WStructure = _get(w, 'WStructure')
        r.WPT = _get(w, 'WPT')
        r.WBat = _get(w, 'WBat')
        r.WCrew = _get(w, 'WCrew')
        r.WPayload = _get(w, 'WPayload')

        if None not in (r.WPT, r.WStructure, r.WCrew):
            # Add the powertrain only when the structural model does not already contain it --
            # the same rule the take-off-weight closure uses, so the reported empty weight and
            # the weight the design actually converged on stay consistent.
            wpt = w.powertrain_in_closure(r.WPT) if hasattr(w, 'powertrain_in_closure') else r.WPT
            r.empty_weight = wpt + r.WStructure + r.WCrew + (r.WBat or 0.0)
            if r.WPayload is not None:
                r.zero_fuel_weight = r.empty_weight + r.WPayload

        r.WingSurface = getattr(aircraft, 'WingSurface', None)
        r.TO_PP = _get(aircraft.mission, 'TO_PP')
        r.Max_PEng = _get(aircraft.mission, 'Max_PEng')
        r.Max_PEng_alt = _get(aircraft.mission, 'Max_PEng_alt')
        r.engineRating = _get(aircraft.powertrain, 'engineRating')
        r.engineRating_units = 'N' if r.configuration == 'Turbofan' else 'W'

        if r.configuration == 'Turbofan':
            m = aircraft.mission
            r.DesignTW = _get(aircraft, 'DesignPW')       # the diagram is built in T/W [-]
            r.Max_Thrust = _get(m, 'Max_Thrust')
            r.Max_Thrust_alt = _get(m, 'Max_Thrust_alt')
            r.Max_Thrust_mach = _get(m, 'Max_Thrust_mach')
            r.TO_Thrust = _get(m, 'TO_Thrust')
            # Mission-mean TSFC, reported so the design is comparable with published engine
            # data. The mission integrates on eta_o; this is the same number re-expressed.
            r.mean_TSFC = _mean_tsfc(aircraft)

        if getattr(aircraft, 'WellToTankInput', None) is not None:
            r.SourceEnergy = _get(aircraft.welltowake, 'SourceEnergy')
            r.Psi = _get(aircraft.welltowake, 'Psi')

        # Battery pack specs: the configuration (S/P cells), energy and power exist for the
        # Class-II battery, used by the Hybrid and the fuel-cell + battery architectures.
        if r.configuration in ('Hybrid', 'FuelCellBattery'):
            b = getattr(aircraft, 'battery', None)
            if b is not None:
                r.battery_class = getattr(b, 'BatteryClass', None)
                r.pack_energy = _get(b, 'pack_energy')
                r.pack_power_max = _get(b, 'pack_power_max')
                r.S_number = _get(b, 'S_number')
                r.P_number = _get(b, 'P_number')

        # Opt-in battery thermal-management / degradation results, if the post-design
        # analysis (battery.thermal_degradation_analysis) was run before results().
        ageing = getattr(getattr(aircraft, 'battery', None), 'ageing', None)
        if ageing:
            r.extras['battery_ageing'] = dict(ageing)

        # Snapshot the inputs that produced this design.
        r.inputs = _collect_inputs(aircraft)

        r._aircraft = aircraft
        return r

    def to_dict(self):
        """Return a plain dict of all fields (suitable for JSON serialization)."""
        return asdict(self)

    def input_summary(self):
        """Return a human-readable summary of *all* inputs that produced this design.

        Includes the configuration flags (Configuration / HybridType / AircraftType /
        weight & battery class) and every legacy input block that was set on the aircraft
        (mission, aerodynamics, constraints, energy, cell, well-to-tank, climate, propeller,
        FLOPS, tank) plus the mission / diversion / loiter flight segments. Use it to keep
        track of exactly what was solved; pair it with :meth:`to_dict` for the outputs.
        """
        return _format_inputs(self.inputs)

    def print_input_summary(self):
        """Print :meth:`input_summary` to stdout."""
        print(self.input_summary())

    def write_timeseries(self, path, include_components="auto"):
        """Dump every time-evolving mission variable to a CSV file (debug helper).

        Writes one row per solver time point with the raw ODE states, the derived mission
        quantities (altitude, velocity, SOC, phi, …), the power flow (propulsive / gas-turbine
        / electric-motor power) and the Class-II component quantities. ``include_components``
        defaults to ``"auto"`` — only components that actually used a Class-II model in this
        design are added (a constant-efficiency design loads no surrogates); pass ``True`` to
        force all or ``False`` to omit. Requires the results to have been built via
        :meth:`from_aircraft` / :meth:`Aircraft.results`. Returns the path.
        """
        if self._aircraft is None:
            raise ValueError(
                "No source aircraft attached — build results via Aircraft.results() / "
                "AircraftResults.from_aircraft() before dumping the time series.")
        from .postprocess import write_timeseries as _write
        return _write(self._aircraft, path, include_components=include_components)


def _get(obj, name):
    """Return ``obj.name`` as a plain Python float if present, else ``None``.

    Coerces numpy scalars / 0-d (or size-1) arrays to ``float`` so the dataclass stays
    JSON-serializable. Some attributes are exposed via validating properties that raise
    when unset; treat those as absent too.
    """
    try:
        value = getattr(obj, name, None)
    except Exception:
        return None
    if value is None:
        return None
    if isinstance(value, np.ndarray):
        if value.size == 1:
            return float(value.reshape(()).item())
        return value.tolist()
    if isinstance(value, np.generic):
        return float(value)
    return value


# Input blocks captured for the design snapshot, in display order.
_INPUT_BLOCKS = [
    'MissionInput', 'AerodynamicsInput', 'ConstraintsInput', 'EnergyInput', 'CellInput',
    'PropellerInput', 'WellToTankInput', 'ClimateImpactInput', 'FLOPSInput', 'TankInput',
    'MissionStages', 'DiversionStages', 'LoiterStages',
]


def _collect_inputs(aircraft):
    """Snapshot the configuration flags and every input block set on the aircraft."""
    import copy
    snapshot = {}
    snapshot['flags'] = {
        'Configuration': getattr(aircraft, 'Configuration', None),
        'HybridType': getattr(aircraft, 'HybridType', None),
        'AircraftType': getattr(aircraft, 'AircraftType', None),
        'WeightClass': getattr(getattr(aircraft, 'weight', None), 'Class', None),
        'BatteryClass': getattr(getattr(aircraft, 'battery', None), 'BatteryClass', None),
    }
    for name in _INPUT_BLOCKS:
        value = getattr(aircraft, name, None)
        if value is not None:
            try:
                snapshot[name] = copy.deepcopy(value)
            except Exception:
                snapshot[name] = value
    return snapshot


def _format_value(value):
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def _format_inputs(inputs):
    """Render the input snapshot from :func:`_collect_inputs` as a readable text block."""
    if not inputs:
        return "(no input snapshot — build results via Aircraft.results())"

    lines = ["=== Design inputs (what was solved) ==="]
    flags = inputs.get('flags', {})
    lines.append("Configuration:")
    for key, val in flags.items():
        if val is not None:
            lines.append(f"  {key:14s}: {val}")

    for name in _INPUT_BLOCKS:
        block = inputs.get(name)
        if not block:
            continue
        lines.append(f"\n[{name}]")
        if name in ('MissionStages', 'DiversionStages', 'LoiterStages'):
            lines.extend(_format_stages(block))
        elif isinstance(block, dict):
            lines.extend(_format_dict(block, indent="  "))
        else:
            lines.append(f"  {block}")
    return "\n".join(lines)


def _format_dict(block, indent="  ", depth=0):
    """Recursively format a (possibly nested) input dict, one key per line."""
    out = []
    for key, val in block.items():
        if isinstance(val, dict) and depth < 2:
            out.append(f"{indent}{key}:")
            out.extend(_format_dict(val, indent + "  ", depth + 1))
        else:
            out.append(f"{indent}{key}: {_format_value(val)}")
    return out


def _format_stages(stages):
    """Compact one-line-per-segment view of a flight-stage ordered dict."""
    out = []
    for seg_name, seg in stages.items():
        seg_type = seg.get('type', '?') if isinstance(seg, dict) else '?'
        phi = seg.get('Supplied Power Ratio', {}) if isinstance(seg, dict) else {}
        phi_txt = ""
        if phi:
            if 'phi' in phi:
                phi_txt = f"  phi={phi['phi']:g}"
            else:
                phi_txt = f"  phi={phi.get('phi_start', 0):g}->{phi.get('phi_end', 0):g}"
        out.append(f"  {seg_name:12s} {seg_type}{phi_txt}")
    return out
