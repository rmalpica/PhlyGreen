"""Example 28 — The ATR 42-600 reference aircraft: inputs, sources and comparison.

The regional turboprop used throughout the examples (``common.traditional_config``) is an
ATR 42-600. Its sizing requirements come from the manufacturer's factsheet:

    ATR, "ATR 42-600" factsheet (2020),
    https://www.atr-aircraft.com/wp-content/uploads/2020/07/Factsheets_-_ATR_42-600.pdf

The four inputs taken from the factsheet are:

- take-off distance (basic, MTOW, ISA, SL): 1,107 m;
- optimum climb speed: 160 KCAS;
- rate of climb (ISA, SL, MTOW): 1,851 ft/min;
- time to climb to FL170: 12.7 min.

Everything else (powertrain efficiencies, polar, structural regression) is generic: the model
is NOT tuned to the published masses or power. The script prints every input, then sizes the
aircraft twice and compares both with the factsheet:

A. at the design point PhlyGreen chooses by default (the wing loading that minimises the
   installed power);
B. at the real aircraft's wing loading (18,600 kg / 54.5 m^2 = 341 kg/m^2).

The difference between A and B is the main lesson. Minimising installed power gives a large
wing at a low wing loading. A real aircraft sits at a higher wing loading (smaller wing, less
drag, lighter), bounded by its field and approach performance.

Run it:
    cd trunk && python examples/28_reference_atr42.py
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import PhlyGreen as pg
from PhlyGreen import postprocess as pp
from common import traditional_config, savefig

SHP = 745.7   # W per shaft horsepower

# ATR 42-600 factsheet (ATR, 2020) — values as printed, converted to SI where needed.
FACTSHEET = {
    "MTOW [kg]": 18600.0,                    # "Max take-off weight (basic) 18,600 kg"
    "OEW [kg]": 11550.0,                     # "Operational empty weight (Tech. Spec.) 11,550 kg"
    "wing area [m2]": 54.5,                  # "WING AREA: 54.5 m2"
    "take-off power, 2 engines [MW]": 2 * 2160 * SHP / 1e6,         # "Take-off power 2,160 SHP"
    "max power (OEI take-off / MCT), 2 engines [MW]": 2 * 2400 * SHP / 1e6,   # "2,400 SHP"
}
INPUTS_FROM_FACTSHEET = {
    "take-off distance (MTOW, ISA, SL)": "1,107 m",
    "optimum climb speed": "160 KCAS",
    "rate of climb (ISA, SL, MTOW)": "1,851 ft/min",
    "time to climb to FL170": "12.7 min",
    "max payload (typical OEW)": "5,300 kg (example payload: 48 pax x 95 kg = 4,560 kg)",
    "range with max pax": "703 nm (example design mission: 750 nm + 220 nm diversion)",
}


def print_inputs(cfg):
    print("=== Inputs of the reference aircraft (examples/common.py) ===")
    print(f"configuration {cfg.configuration}, Class-I structure '{cfg.aircraft_type}'")
    m = cfg.mission
    print(f"mission: {m.range_mission} nm + {m.range_diversion} nm diversion, payload "
          f"{m.payload_weight} kg, crew {m.crew_weight} kg")
    a = cfg.aerodynamics
    pol = a.analytic_polar["input"]
    print(f"aerodynamics: Cd0 {a.cd0}, AR {pol['AR']}, e {pol['e_osw']}, CL_TO {a.take_off_cl}, "
          f"CL_land {a.landing_cl}")
    e = cfg.energy
    print(f"powertrain: eta_GT {e.eta_gas_turbine}, eta_gearbox {e.eta_gearbox}, "
          f"eta_prop {e.eta_propulsive}, turboshaft {e.specific_power_powertrain[0]} W/kg, "
          f"Ef {e.Ef / 1e6:.1f} MJ/kg, reserve {e.contingency_fuel} kg")
    print("constraints:")
    for phase, p in cfg.constraints.phases.items():
        print(f"  {phase:13s} " + ", ".join(f"{k} {v}" for k, v in p.items()))
    print("flight profile (mission):")
    for s in cfg.mission_stages.segments:
        if s.segment_type:
            print(f"  {s.name:9s} {s.segment_type:20s} {s.inputs}")
    print("taken from the ATR factsheet:")
    for k, v in INPUTS_FROM_FACTSHEET.items():
        print(f"  {k:35s} {v}")


def design(wing_loading_kgm2=None):
    cfg = traditional_config()
    if wing_loading_kgm2 is not None:
        cfg.design_wing_loading = wing_loading_kgm2 * 9.81
    a = pg.build_aircraft()
    a.configure(cfg)
    return a


def outputs(a):
    r = a.results()
    return {"MTOW [kg]": r.WTO, "OEW [kg]": r.empty_weight, "wing area [m2]": a.WingSurface,
            "take-off power, 2 engines [MW]": r.engineRating / 1e6,
            "max power (OEI take-off / MCT), 2 engines [MW]": r.engineRating / 1e6}


def time_to_climb(a, altitude_m):
    p = a.mission.profile
    t = np.linspace(0.0, p.MissionTime, 20001)
    alt = np.array([float(p.Altitude(x)) for x in t])
    return t[np.argmax(alt >= altitude_m)] / 60.0


def compare(results):
    print("\n=== Model vs ATR 42-600 factsheet ===")
    print(f"{'quantity':48s} {'factsheet':>10s} " + " ".join(f"{k:>16s}" for k in results))
    for q, ref in FACTSHEET.items():
        cells = []
        for a in results.values():
            v = outputs(a)[q]
            cells.append(f"{v:9.2f} ({100 * (v - ref) / ref:+5.1f}%)")
        print(f"{q:48s} {ref:10.2f} " + " ".join(f"{c:>16s}" for c in cells))
    print("(the model's engine rating is one number; it is compared with both published ratings)")
    for name, a in results.items():
        print(f"{name}: W/S {a.DesignWTOoS / 9.81:.0f} kg/m2, block fuel {a.results().block_fuel:.0f} kg, "
              f"time to FL170 {time_to_climb(a, 5182):.1f} min (factsheet 12.7)")


def make_figures(results, outdir=None):
    """Constraint diagram, mission profile, mass breakdown and the comparison chart."""
    figs = {}
    a_def = results["A: default W/S"]
    a_real = results["B: real W/S"]

    fig, ax = plt.subplots(figsize=(8, 5.5))
    pp.plot_constraint_diagram(a_def, ax=ax)
    ax.plot(a_real.DesignWTOoS / 9.81, a_real.DesignPW, "s", color="k", ms=8,
            label="B: real ATR 42-600 wing loading")
    ax.set_title("ATR 42-600 reference: constraint diagram")
    ax.legend(fontsize=8, loc="best")
    figs["atr42_constraint_diagram"] = fig

    fig, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    pp.plot_mission_profile(a_real, axes=axes)
    axes[0].set_title("ATR 42-600 reference: mission and diversion profile")
    figs["atr42_mission_profile"] = fig

    fig, ax = plt.subplots(figsize=(7, 5))
    pp.plot_mass_breakdown(a_real, ax=ax)
    ax.set_title("ATR 42-600 reference (real W/S): take-off mass breakdown")
    figs["atr42_mass_breakdown"] = fig

    fig, ax = plt.subplots(figsize=(10, 4.5))
    qs = list(FACTSHEET)
    x = np.arange(len(qs))
    for i, (name, a) in enumerate(results.items()):
        err = [100 * (outputs(a)[q] - FACTSHEET[q]) / FACTSHEET[q] for q in qs]
        ax.bar(x + (i - 0.5) * 0.38, err, 0.38, label=name)
    ax.axhline(0, color="k", lw=0.8)
    ax.axhspan(-5, 5, color="0.9", zorder=0)
    ax.set_xticks(x)
    short = ["MTOW", "OEW", "wing area", "take-off power\n(2 x 2,160 SHP)", "max power\n(2 x 2,400 SHP)"]
    ax.set_xticklabels(short, fontsize=9)
    ax.set_ylabel("model − factsheet [%]")
    ax.set_title("ATR 42-600 reference: model vs manufacturer data (grey band ±5 %)")
    ax.legend()
    fig.tight_layout()
    figs["atr42_vs_factsheet"] = fig

    for name, fig in figs.items():
        if outdir is None:
            savefig(fig, name + ".png")
        else:
            fig.savefig(f"{outdir}/{name}.png", dpi=130, bbox_inches="tight")
        plt.close(fig)
    return list(figs)


def run():
    results = {"A: default W/S": design(), "B: real W/S": design(18600.0 / 54.5)}
    return results


def main():
    print(__doc__.split("Run it:")[0].strip())
    print_inputs(traditional_config())
    results = run()
    compare(results)
    print("\nFigures:")
    make_figures(results)


if __name__ == "__main__":
    main()
