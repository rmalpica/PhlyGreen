"""Curated input "knobs" for the design lab.

A small, hand-picked set of the most pedagogically useful inputs (the full typed config has
dozens of fields — too many for a teaching UI). Each :class:`Knob` knows how to read its current
value from a config and write a new one back; the *same* setters power both the Design tab
widgets and the Sweep tab, so there is one source of truth for "what can a student change".

Setters mutate the config in place (the caller always passes a deep copy).
"""

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class Knob:
    key: str                       # stable id (used as widget key / sweep selector)
    label: str                     # human label with units
    getter: Callable               # getter(config) -> float
    setter: Callable               # setter(config, value) -> None  (mutates in place)
    lo: float
    hi: float
    step: float
    applies: Callable = lambda cfg: True   # applies(config) -> bool
    help: str = ""

    def value(self, cfg):
        return float(self.getter(cfg))


# --- helpers to reach into the nested config --------------------------------------------------
def _cruise_segment(cfg):
    for seg in cfg.mission_stages.segments:
        if seg.segment_type == "ConstantMachCruise":
            return seg
    return None


def _get_cruise_mach(cfg):
    seg = _cruise_segment(cfg)
    return seg.inputs.get("Mach", 0.4) if seg else 0.4


def _set_cruise_mach(cfg, v):
    seg = _cruise_segment(cfg)
    if seg:
        seg.inputs["Mach"] = float(v)


def _get_cruise_alt(cfg):
    seg = _cruise_segment(cfg)
    return seg.inputs.get("Altitude", 8000.0) if seg else 8000.0


def _set_cruise_alt(cfg, v):
    """Move cruise altitude and keep the profile monotonic (end of last climb / top of descent)."""
    v = float(v)
    for seg in cfg.mission_stages.segments:
        if seg.segment_type == "ConstantMachCruise":
            seg.inputs["Altitude"] = v
        elif seg.name == "Climb3":
            seg.inputs["EndAltitude"] = v
        elif seg.segment_type == "ConstantRateDescent":
            seg.inputs["StartAltitude"] = v


def _get_cruise_phi(cfg):
    seg = _cruise_segment(cfg)
    if not seg:
        return 0.0
    return seg.phi_end if seg.phi_end is not None else (seg.phi or 0.0)


def _set_cruise_phi(cfg, v):
    seg = _cruise_segment(cfg)
    if seg:
        seg.phi = None
        seg.phi_start = float(v)
        seg.phi_end = float(v)


# Battery / power-split share (phi) is set *per phase*: take-off, climb and cruise can each take a
# different fraction of propulsive power from the battery (important for a fuel-cell + battery
# design, where you may want the battery to cover the take-off / climb peaks).
def _segments(cfg, pred):
    return [s for s in cfg.mission_stages.segments if pred(s)]


def _get_takeoff_phi(cfg):
    segs = _segments(cfg, lambda s: s.name == "Takeoff")
    if not segs:
        return 0.0
    s = segs[0]
    return s.phi if s.phi is not None else (s.phi_end if s.phi_end is not None else 0.0)


def _set_takeoff_phi(cfg, v):
    for s in _segments(cfg, lambda s: s.name == "Takeoff"):
        s.phi = float(v)            # take-off uses a single (constant) phi
        s.phi_start = s.phi_end = None


def _get_climb_phi(cfg):
    segs = _segments(cfg, lambda s: s.segment_type == "ConstantRateClimb")
    if not segs:
        return 0.0
    s = segs[0]
    return s.phi_end if s.phi_end is not None else (s.phi if s.phi is not None else 0.0)


def _set_climb_phi(cfg, v):
    for s in _segments(cfg, lambda s: s.segment_type == "ConstantRateClimb"):
        s.phi = None
        s.phi_start = s.phi_end = float(v)


def _has_battery(cfg):
    return cfg.configuration in ("Hybrid", "FuelCellBattery")


def _get_ar(cfg):
    return cfg.aerodynamics.analytic_polar["input"]["AR"]


def _set_ar(cfg, v):
    cfg.aerodynamics.analytic_polar["input"]["AR"] = float(v)


def _is_battery_hybrid(cfg):
    return cfg.configuration == "Hybrid"


def _is_fuel(cfg):
    return cfg.configuration in ("Traditional", "Hybrid")


def _is_h2(cfg):
    return cfg.configuration in ("Hydrogen", "FuelCellBattery")


def _set_batt_specific_energy(cfg, v):
    # Hybrid stores it on the cell; FuelCellBattery on the energy block.
    if cfg.cell is not None:
        cfg.cell.specific_energy = float(v)
    if getattr(cfg.energy, "battery_specific_energy", None) is not None:
        cfg.energy.battery_specific_energy = float(v)


def _get_batt_specific_energy(cfg):
    if cfg.cell is not None and cfg.cell.specific_energy is not None:
        return cfg.cell.specific_energy
    return getattr(cfg.energy, "battery_specific_energy", 250.0) or 250.0


# --- the curated knob set ---------------------------------------------------------------------
KNOBS = [
    Knob("range", "Design range [nm]", lambda c: c.mission.range_mission,
         lambda c, v: setattr(c.mission, "range_mission", float(v)),
         200, 1500, 10, help="Trip distance the aircraft must fly."),
    Knob("payload", "Payload [kg]", lambda c: c.mission.payload_weight,
         lambda c, v: setattr(c.mission, "payload_weight", float(v)),
         1000, 7000, 50),
    Knob("cruise_mach", "Cruise Mach [-]", _get_cruise_mach, _set_cruise_mach,
         0.30, 0.55, 0.01),
    Knob("cruise_alt", "Cruise altitude [m]", _get_cruise_alt, _set_cruise_alt,
         4000, 10000, 100, help="Also shifts the top of climb / start of descent."),
    Knob("cd0", "Zero-lift drag Cd0 [-]", lambda c: c.aerodynamics.cd0,
         lambda c, v: setattr(c.aerodynamics, "cd0", float(v)),
         0.012, 0.030, 0.001),
    Knob("ar", "Wing aspect ratio [-]", _get_ar, _set_ar, 8.0, 14.0, 0.5),
    Knob("eta_prop", "Propulsive efficiency [-]", lambda c: c.energy.eta_propulsive,
         lambda c, v: setattr(c.energy, "eta_propulsive", float(v)),
         0.75, 0.95, 0.01),
    # fuel-burning (gas-turbine) designs only
    Knob("eta_gt", "Gas-turbine efficiency [-]", lambda c: c.energy.eta_gas_turbine,
         lambda c, v: setattr(c.energy, "eta_gas_turbine", float(v)),
         0.18, 0.40, 0.01, applies=_is_fuel),
    # battery hybrids only — the battery power share (phi) per flight phase
    Knob("takeoff_phi", "Take-off battery share φ [-]", _get_takeoff_phi, _set_takeoff_phi,
         0.0, 0.6, 0.05, applies=_has_battery,
         help="Fraction of take-off propulsive power from the battery."),
    Knob("climb_phi", "Climb battery share φ [-]", _get_climb_phi, _set_climb_phi,
         0.0, 0.6, 0.05, applies=_has_battery,
         help="Fraction of climb propulsive power from the battery (all climb segments)."),
    Knob("cruise_phi", "Cruise battery share φ [-]", _get_cruise_phi, _set_cruise_phi,
         0.0, 0.6, 0.05, applies=_has_battery,
         help="Fraction of cruise propulsive power from the battery."),
    Knob("batt_e", "Battery specific energy [Wh/kg]", _get_batt_specific_energy,
         _set_batt_specific_energy, 600, 2000, 50, applies=_has_battery),
    # hydrogen / fuel-cell only
    Knob("v_cell", "Fuel-cell design voltage [V]", lambda c: c.energy.v_cell_design,
         lambda c, v: setattr(c.energy, "v_cell_design", float(v)),
         0.40, 0.80, 0.01, applies=_is_h2,
         help="Higher voltage = more efficient but a heavier, lower-power-density stack."),
    Knob("stack_pd", "Stack power density [W/kg]", lambda c: c.energy.stack_power_density,
         lambda c, v: setattr(c.energy, "stack_power_density", float(v)),
         1500, 5000, 100, applies=_is_h2),
]


def knobs_for(config):
    """Return the knobs applicable to the given configuration."""
    return [k for k in KNOBS if k.applies(config)]


def apply_overrides(config, overrides):
    """Apply a ``{knob_key: value}`` dict to ``config`` in place, using the knob setters."""
    by_key = {k.key: k for k in KNOBS}
    for key, val in overrides.items():
        if key in by_key:
            by_key[key].setter(config, val)
    return config
