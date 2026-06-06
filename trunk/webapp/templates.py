"""Baseline design templates for the Virtual Aircraft Design Lab.

Thin wrappers around the canonical baseline configs in ``examples/common.py`` (the same
ATR-like regional turboprop used throughout the examples), exposed as a labelled registry the
GUI can offer as "starting designs". Also provides a small config <-> dict serializer used for
caching and for the JSON download — this is the *only* glue the GUI needs on top of the public
``PhlyGreen`` API; the package itself is untouched.
"""

import copy
import os
import sys

# Make ``examples/common.py`` importable (it is a plain module, not a package), exactly as the
# tutorial notebooks do.
_HERE = os.path.dirname(os.path.abspath(__file__))      # .../trunk/webapp
_EXAMPLES = os.path.join(os.path.dirname(_HERE), "examples")
if _EXAMPLES not in sys.path:
    sys.path.insert(0, _EXAMPLES)

import common  # noqa: E402  (examples/common.py)


# --- the labelled registry of starting designs ------------------------------------------------
# Each factory returns a fully-validated PhlyGreen.config.AircraftConfig. The hydrogen template
# uses the physics LH2 tank (CoolProp is a required dependency).
TEMPLATES = {
    "Traditional turboprop": {
        "factory": lambda: common.traditional_config(),
        "blurb": "Conventional fuel-only ATR-like turboprop. The baseline reference design.",
    },
    "Hybrid GT + battery": {
        "factory": lambda: common.hybrid_config(battery_class="II"),
        "blurb": "Gas turbine + battery hybrid (parallel by default — switch to serial under Advanced). "
                 "The battery supplies a share (phi) of the propulsive power.",
    },
    "Hydrogen fuel cell": {
        "factory": lambda: common.hydrogen_config(tank=True),
        "blurb": "Fuel-cell electric on liquid hydrogen with a physics-sized cryogenic LH2 tank.",
    },
    "Hybrid fuel cell + battery": {
        "factory": lambda: common.fuelcell_battery_config(cruise_phi=0.15),
        "blurb": "Hydrogen fuel cell hybridised with a battery that supplies a share (phi) of the "
                 "propulsive power.",
    },
}

TEMPLATE_LABELS = list(TEMPLATES)


def make_config(label):
    """Return a fresh baseline :class:`AircraftConfig` for the given template label."""
    return TEMPLATES[label]["factory"]()


def fcb_class_ii_cell():
    """A Class-II (cell-level electro-thermal) battery for the fuel-cell + battery design.

    Attaching this to a ``FuelCellBattery`` config switches the battery from the simple Class-I
    specific-energy/power model to the physics cell model (P-number sizing + thermal cooling).
    """
    from PhlyGreen.config import CellConfig
    return CellConfig(cell_class="II", model="Finger-Cell-Thermal", specific_power=8000,
                      specific_energy=250, minimum_soc=0.2, pack_voltage=800,
                      initial_temperature=25, max_operative_temperature=50)


FCB_LABEL = "Hybrid fuel cell + battery"


def template_blurb(label):
    return TEMPLATES[label]["blurb"]


# --- config (de)serialization -----------------------------------------------------------------
_SECTIONS = ("aerodynamics", "constraints", "mission", "energy", "mission_stages",
             "diversion_stages", "loiter_stages", "well_to_tank", "cell",
             "climate_impact", "tank")


def config_to_dict(config):
    """Plain, JSON-able dict of a full ``AircraftConfig`` (flags + every section ``to_dict``).

    ``AircraftConfig`` has no ``to_dict`` of its own (only its sections do), so we assemble one.
    Used as a stable cache key and as the design's downloadable JSON.
    """
    d = {
        "configuration": config.configuration,
        "hybrid_type": config.hybrid_type,
        "aircraft_type": config.aircraft_type,
        "weight_class": config.weight_class,
        "design_wing_loading": config.design_wing_loading,
    }
    for name in _SECTIONS:
        section = getattr(config, name, None)
        d[name] = section.to_dict() if section is not None else None
    return d


def clone(config):
    """Deep-copy a config (the GUI mutates copies, never a template in place)."""
    return copy.deepcopy(config)
