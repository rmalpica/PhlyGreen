"""Example 29 — The Airbus A320-200 reference aircraft: inputs, sources and comparison.

The turbofan configuration (``common.turbofan_config``) is an A320-200 (A320-214, CFM56-5B4,
weight variant WV017) on its design mission: 150 passengers two-class (14,250 kg) over
3,000 nm, with a 200 nm alternate and a 30-min hold. The reference data and the provenance of
every number are in ``trunk/validation/a320_reference.md``. The primary sources are:

- Airbus, *A320 Aircraft Characteristics — Airport and Maintenance Planning* (ACAP), Rev. Jun 2024;
- EASA TCDS EASA.A.064 (Issue 12) and TCDS-N EASA.A.064.3 (Issue 28).

Wing area and OEW come from secondary sources and are labelled as such.

This example prints the inputs and compares two design points with the reference:

A. the default design point, the wing loading that minimises the installed thrust;
B. the landing-limited design point, the wing-loading wall from the model's own landing
   constraint (approach speed and landing CL_max), which is where a narrow-body is sized.

The full validation (OEW calibration, payload-range, wing-loading sweep) is
``trunk/validation/a320_reference.py``; this example reuses its functions.

Needs the fitted turbofan map ``Systems/Powertrain/data/Turbofan_Engine_Model.pkl``.

Run it:
    cd trunk && python examples/29_reference_a320.py
"""

import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from common import turbofan_config, savefig

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "validation"))
import a320_reference as val                      # noqa: E402  (trunk/validation)
from PhlyGreen import postprocess as pp           # noqa: E402


def print_inputs(cfg):
    print("=== Inputs of the A320-200 reference (examples/common.py: turbofan_config) ===")
    print(f"configuration {cfg.configuration}, Class-I structure '{cfg.aircraft_type}' "
          f"(narrow-body empty-weight regression), powertrain double count avoided: "
          f"{cfg.avoid_powertrain_double_count}")
    m = cfg.mission
    print(f"mission: {m.range_mission} nm + {m.range_diversion} nm alternate + {m.time_loiter} min hold, "
          f"payload {m.payload_weight} kg (150 pax x 95 kg), crew {m.crew_weight} kg")
    a = cfg.aerodynamics
    pol = a.analytic_polar["input"]
    print(f"aerodynamics (compressible polar): Cd0 {a.cd0}, AR {pol['AR']}, e {pol['e_osw']}, "
          f"sweep {a.wing_sweep} deg, t/c {a.thickness_to_chord}, Korn kappa {a.korn_kappa}, "
          f"CL_TO {a.take_off_cl}, CL_land {a.landing_cl}")
    e = cfg.energy
    print(f"engine: turbofan map, nominal SLS thrust {e.turbofan_design_thrust / 1e3:.1f} kN "
          f"(2 x CFM56-5B4 at 12,010 daN, EASA TCDS), installed T/W {e.engine_thrust_to_weight}, "
          f"Ef {e.Ef / 1e6:.1f} MJ/kg, reserve {e.contingency_fuel} kg")
    print("constraints:")
    for phase, p in cfg.constraints.phases.items():
        print(f"  {phase:13s} " + ", ".join(f"{k} {v}" for k, v in p.items()))
    print("reference (value, units, source class):")
    for k, v in val.REFERENCE.items():
        if k != "citation":
            print(f"  {k:18s} {v[0]:>9} {v[1]:4s} {v[2]}")


def main():
    print(__doc__.split("Run it:")[0].strip())
    print_inputs(turbofan_config())
    wall = val.landing_limited_wing_loading()
    a_default = val._design()
    a_landing = val._design(wall)
    val.compare(a_default, "A) minimum-installed-thrust design point")
    val.compare(a_landing, f"B) landing-limited design point (W/S = {wall:.1f} kg/m2)")

    print("\nFigures:")
    fig, ax = plt.subplots(figsize=(8, 5.5))
    pp.plot_constraint_diagram(a_landing, ax=ax)
    ax.plot(a_default.DesignWTOoS / 9.81, a_default.DesignTW, "s", color="k", ms=8,
            label="A: minimum installed thrust")
    ax.legend(fontsize=8)
    ax.set_title("A320-200 reference: constraint diagram (B = landing-limited)")
    savefig(fig, "a320_constraint_diagram.png")
    plt.close(fig)
    fig, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    pp.plot_mission_profile(a_landing, axes=axes, include_loiter=True)
    axes[0].set_title("A320-200 reference: mission, alternate and hold")
    savefig(fig, "a320_mission_profile.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
