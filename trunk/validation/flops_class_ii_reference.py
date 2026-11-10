"""Validation of the Class-II (FLOPS) structural-mass model on the ATR 42-600 and the A320-200.

Each reference aircraft is sized with the Class-I regression and with the Class-II FLOPS
component build-up, at two wing loadings:

* A, the default design point (minimum installed power or thrust);
* B, the wing loading of the real aircraft (ATR 42: 18,600 kg / 54.5 m^2) or the
  landing-limited one (A320, ``a320_reference.landing_limited_wing_loading``).

The predicted take-off weight, operating empty weight and wing area are compared with the
published values. The FLOPS inputs (``examples/common.py``: ``atr_flops_input``,
``a320_flops_input``) carry their provenance; all mass scalers are 1.0, so nothing is
calibrated to the reference masses. The input dossier is ``flops_class_ii_reference.md``.

A sweep of the aspect ratio at the wing loading B shows the structural feedback of the
Class-II wing: the span is sqrt(AR * S), so a larger aspect ratio makes a heavier wing. The
aerodynamic model keeps a fixed Oswald factor and Cd0, so the sweep shows the structural
side of the aspect-ratio trade only.

Run from ``trunk/``:

    python validation/flops_class_ii_reference.py
"""

import os
import sys
import warnings

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "examples"))
sys.path.insert(0, _HERE)

import PhlyGreen as pg                                              # noqa: E402
import PhlyGreen.Utilities.Units as Units                           # noqa: E402
from common import (traditional_config, turbofan_config,           # noqa: E402
                    atr_flops_input, a320_flops_input)
import a320_reference                                               # noqa: E402

FIGDIR = os.path.join(_HERE, "figures")

# ATR 42-600 factsheet (2020): MTOW (basic), OEW (Tech. Spec.), wing area.
ATR42_REFERENCE = {"MTOW": 18600.0, "OEW": 11550.0, "wing_area": 54.5}
ATR42_REAL_WING_LOADING = 18600.0 / 54.5                            # [kg/m^2]

# CFM56-5B4 ("SAC" models): dry weight 2,454.8 kg, take-off thrust 12,010 daN (EASA TCDS E.003
# Issue 06, Sections II.5 and II.6.1). The dry weight includes the basic engine and its
# accessories; nacelle and thrust reverser are not stated as included.
CFM56_5B4_THRUST_TO_WEIGHT = 120100.0 / (9.81 * 2454.8)          # [N/N] = 4.99

# A320-214 WV017 (a320_reference.py, sources in a320_reference.md).
A320_REFERENCE = {"MTOW": a320_reference.REFERENCE["MTOW"][0],
                  "OEW": a320_reference.REFERENCE["OEW"][0],
                  "wing_area": a320_reference.REFERENCE["wing_area"][0]}

COMPONENTS = [  # (label, attribute path on weight.AircraftComponents)
    ("wing", ("Wing", "wingmass")),
    ("fuselage", ("Fuselage", "fuselagemass")),
    ("horizontal tail", ("Tail", "HTailmass")),
    ("vertical tail", ("Tail", "VTailmass")),
    ("landing gear", ("LandingGear", "Landing_gearmass")),
    ("nacelles", ("Nacelle", "nacellemass")),
    ("paint", ("Paint", "paintmass")),
    ("systems and equipment", ("SystemEquipment", "system_equipment_mass")),
    ("propellers", ("Propeller", "propellermass")),
    ("fuel system, oil, starter, controls, pax service, unusable fuel",
     ("OperatingItems", "operating_items_mass")),
]


def atr_config(weight_class, wing_loading_kgm2=None, aspect_ratio=None):
    cfg = traditional_config()
    cfg.weight_class = weight_class
    if wing_loading_kgm2 is not None:
        cfg.design_wing_loading = wing_loading_kgm2 * 9.81
    if aspect_ratio is not None:
        cfg.aerodynamics.analytic_polar["input"]["AR"] = aspect_ratio
    return cfg, atr_flops_input()


def a320_config(weight_class, wing_loading_kgm2=None, aspect_ratio=None):
    cfg = turbofan_config()
    cfg.weight_class = weight_class
    cfg.avoid_powertrain_double_count = True        # Class I: the regression has the engines
    cfg.energy.engine_thrust_to_weight = CFM56_5B4_THRUST_TO_WEIGHT   # Class II: engine mass
    if wing_loading_kgm2 is not None:
        cfg.design_wing_loading = wing_loading_kgm2 * 9.81
    if aspect_ratio is not None:
        cfg.aerodynamics.analytic_polar["input"]["AR"] = aspect_ratio
    return cfg, a320_flops_input()


def design(cfg, flops_input):
    aircraft = pg.build_aircraft()
    aircraft.FLOPSInput = flops_input
    aircraft.configure(cfg)
    return aircraft


def summary(aircraft):
    r = aircraft.results()
    return {"MTOW": r.WTO, "OEW": r.empty_weight, "wing_area": aircraft.WingSurface,
            "W/S": aircraft.DesignWTOoS / 9.81}


def component_masses(aircraft):
    c = aircraft.weight.AircraftComponents
    return {label: Units.lbTokg(getattr(getattr(c, obj), attr))
            for label, (obj, attr) in COMPONENTS}


def compare(name, reference, cases):
    print(f"\n=== {name}: model vs reference ===")
    header = f"{'quantity':12s} {'reference':>10s}"
    for label in cases:
        header += f" {label:>22s}"
    print(header)
    for key, unit in (("MTOW", "kg"), ("OEW", "kg"), ("wing_area", "m2")):
        row = f"{key + ' [' + unit + ']':12s} {reference[key]:10.1f}"
        for label, s in cases.items():
            row += f" {s[key]:12.1f} ({100 * (s[key] / reference[key] - 1):+6.1f}%)"
        print(row)
    row = f"{'W/S [kg/m2]':12s} {'':>10s}"
    for s in cases.values():
        row += f" {s['W/S']:22.1f}"
    print(row)


def print_components(name, aircraft):
    print(f"\n{name}: Class-II component masses [kg]")
    for label, mass in component_masses(aircraft).items():
        print(f"  {label:66s} {mass:8.0f}")
    r = aircraft.results()
    print(f"  {'sum (WStructure)':66s} {r.WStructure:8.0f}")
    print(f"  {'powertrain (engines, WPT)':66s} {r.WPT:8.0f}")
    print(f"  {'crew (mission input)':66s} {r.WCrew:8.0f}")


def aspect_ratio_sweep(make_config, wing_loading_kgm2, ratios):
    """Wing mass and take-off weight vs aspect ratio at a fixed wing loading (Class II)."""
    rows = []
    for ar in ratios:
        a = design(*make_config("II", wing_loading_kgm2, aspect_ratio=ar))
        rows.append((ar, component_masses(a)["wing"], a.weight.WTO,
                     Units.ftTom(np.sqrt(ar * Units.m2toft2(a.WingSurface)))))
    return rows


def print_sweep(name, rows):
    print(f"\n{name}: aspect-ratio sweep at fixed wing loading (Class II)")
    print(f"  {'AR':>5s} {'span [m]':>9s} {'wing [kg]':>10s} {'MTOW [kg]':>10s}")
    for ar, wing, wto, span in rows:
        print(f"  {ar:5.1f} {span:9.2f} {wing:10.0f} {wto:10.0f}")


def make_figure(atr_rows, a320_rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    os.makedirs(FIGDIR, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, rows, title in ((axes[0], atr_rows, "ATR 42-600 (341 kg/m$^2$)"),
                            (axes[1], a320_rows, "A320-200 (landing-limited W/S)")):
        ar = [r[0] for r in rows]
        ax.plot(ar, [r[1] for r in rows], "o-", color="tab:blue")
        ax.set_xlabel("aspect ratio [-]")
        ax.set_ylabel("wing mass [kg]", color="tab:blue")
        ax2 = ax.twinx()
        ax2.plot(ar, [r[2] for r in rows], "s--", color="tab:red")
        ax2.set_ylabel("MTOW [kg]", color="tab:red")
        ax.set_title(title)
        ax.grid(alpha=0.3)
    fig.suptitle("Class-II (FLOPS) wing: aspect-ratio sweep at fixed wing loading")
    fig.tight_layout()
    path = os.path.join(FIGDIR, "flops_class_ii_aspect_ratio.png")
    fig.savefig(path, dpi=130)
    plt.close(fig)
    print(f"\nFigure: {path}")


def main():
    warnings.simplefilter("ignore")

    atr = {}
    for wc in ("I", "II"):
        atr[f"Class {wc}, A"] = design(*atr_config(wc))
        atr[f"Class {wc}, B (341)"] = design(*atr_config(wc, ATR42_REAL_WING_LOADING))
    compare("ATR 42-600", ATR42_REFERENCE, {k: summary(a) for k, a in atr.items()})
    print_components("ATR 42-600, B", atr["Class II, B (341)"])

    wall = a320_reference.landing_limited_wing_loading()
    a320 = {}
    for wc in ("I", "II"):
        a320[f"Class {wc}, A"] = design(*a320_config(wc))
        a320[f"Class {wc}, B ({wall:.0f})"] = design(*a320_config(wc, wall))
    compare("A320-200", A320_REFERENCE, {k: summary(a) for k, a in a320.items()})
    print_components("A320-200, B", a320[f"Class II, B ({wall:.0f})"])

    atr_rows = aspect_ratio_sweep(atr_config, ATR42_REAL_WING_LOADING, [8, 10, 11, 12, 14, 16])
    print_sweep("ATR 42-600", atr_rows)
    a320_rows = aspect_ratio_sweep(a320_config, wall, [7, 8.5, 9.5, 11, 12.5])
    print_sweep("A320-200", a320_rows)
    make_figure(atr_rows, a320_rows)


if __name__ == "__main__":
    main()
