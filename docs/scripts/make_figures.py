"""Regenerate the documentation figures (written to ``docs/images/``).

Run from the repository root (CoolProp and the turbofan map are needed):

    python docs/scripts/make_figures.py            # everything (~5 min)
    python docs/scripts/make_figures.py tms        # only one group: reference | a320 | tms | hydrogen

Every figure comes from the package or from the examples, so the docs show what the code does.
"""

import importlib.util
import os
import sys
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TRUNK = os.path.join(ROOT, "trunk")
IMAGES = os.path.join(ROOT, "docs", "images")
sys.path.insert(0, os.path.join(TRUNK, "examples"))
sys.path.insert(0, os.path.join(TRUNK, "validation"))
warnings.simplefilter("ignore")

import PhlyGreen as pg                                     # noqa: E402
from PhlyGreen.config import TMSConfig                     # noqa: E402
from common import hydrogen_config                         # noqa: E402


def _out(group, name):
    d = os.path.join(IMAGES, group)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, name + ".png")


def _save(fig, group, name):
    path = _out(group, name)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    print("  wrote", os.path.relpath(path, ROOT))


def _example(filename):
    spec = importlib.util.spec_from_file_location(filename[:-3], os.path.join(TRUNK, "examples", filename))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------------------------------------
def reference():
    """ATR 42-600 reference (example 28) + its hydrogen variant against the literature."""
    ex = _example("28_reference_atr42.py")
    results = ex.run()
    os.makedirs(os.path.join(IMAGES, "reference"), exist_ok=True)
    ex.make_figures(results, outdir=os.path.join(IMAGES, "reference"))

    # hydrogen variant vs published fuel-cell regional designs (MTOW/payload vs range)
    designs = {}
    for cls in ("I", "II"):
        c = hydrogen_config()
        c.tms = TMSConfig(tms_class=cls)
        a = pg.build_aircraft(); a.configure(c)
        designs[cls] = a.weight.WTO
    lit = [  # (label, design range [nm], payload [kg], MTOW [kg])
        ("Svensson et al. 2024 (50 pax)", 648, 5500, 21050),
        ("Eissele et al. 2023 (50 pax, FC+bat.)", 432, 5300, 19600),
        ("Schlittenhardt et al. 2025 (70 pax)", 432, 6650, 23640),
        ("FlyZero FZR-1E 2022 (75 pax)", 800, 7875, 28800),
    ]
    fig, ax = plt.subplots(figsize=(8, 4.8))
    for (lab, rng, pl, mtow), mk in zip(lit, "o^vD"):
        ax.plot(rng, mtow / pl, mk, ms=9, label=lab)
    for cls, mk in (("I", "*"), ("II", "P")):
        ax.plot(750, designs[cls] / 4560, mk, ms=13, color="k",
                label=f"PhlyGreen H2 ATR 42, TMS Class {cls} ({designs[cls]/1e3:.1f} t)")
    ax.set_xlabel("design range [nm] (reserves excluded)")
    ax.set_ylabel("MTOW / payload [-]")
    ax.set_title("Hydrogen fuel-cell regional aircraft: PhlyGreen vs published designs")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    _save(fig, "reference", "h2_vs_literature")


def a320():
    """A320-200 validation figures (trunk/validation/a320_reference.py)."""
    import a320_reference as val
    val.FIGDIR = os.path.join(IMAGES, "reference")
    wall = val.landing_limited_wing_loading()
    a_def, a_land = val._design(), val._design(wall)
    val.make_figures(a_def, a_land, wall, val.wing_loading_sweep()[1])


def tms():
    """Thermal-management figures: architecture, a sized design, HEX drawings, behaviour."""
    from PhlyGreen.Systems.Thermal.plotting import draw_hex, plot_tms_rating
    _schematic()
    c = hydrogen_config()
    c.tms = TMSConfig(tms_class="II")
    a = pg.build_aircraft(); a.configure(c)
    tms_, res = a.tms, a.weight.tms_result
    fig, ax = plt.subplots(figsize=(10, 4))
    plot_tms_rating(tms_, res, a.mission.thermal_profile, ax=ax)
    fig.tight_layout()
    _save(fig, "tms", "tms_rating")
    for u in res.units:
        fig = draw_hex(u.design, n_parallel=u.n_parallel,
                       title=f"{u.role.replace('_', ' ')}: one of {u.n_parallel} unit(s)")
        _save(fig, "tms", f"hex_{u.role}")

    # design-point selection: mass and worst shortfall of each candidate
    cand = res.candidates
    fig, ax = plt.subplots(figsize=(8, 4))
    names = [x["point"] for x in cand]
    cols = ["tab:green" if x["feasible"] else "tab:red" for x in cand]
    ax.bar(names, [x["mass"] for x in cand], color=cols)
    for i, x in enumerate(cand):
        ax.text(i, x["mass"], f"{100 * x['worst_shortfall']:.0f}%", ha="center", va="bottom", fontsize=8)
    ax.set_ylabel("TMS mass if sized here [kg]")
    ax.set_title("Design-point candidates (green: rejects the heat everywhere;\n"
                 "label: worst shortfall over the mission)")
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    fig.tight_layout()
    _save(fig, "tms", "tms_candidates")

    # mass vs heat load and ram drag vs ram recovery, at one point
    point = dict(res.design_point)
    Qs = np.linspace(0.5, 1.5, 9) * point["Q_fc"]
    masses = []
    for Q in Qs:
        p = {**point, "Q_fc": Q, "mdot_h2": point["mdot_h2"] * Q / point["Q_fc"]}
        masses.append(tms_.SizeAtPoint(p).total_mass)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4))
    a1.plot(Qs / 1e6, masses, "o-")
    a1.set_xlabel("fuel-cell heat at the design point [MW]")
    a1.set_ylabel("TMS mass [kg]")
    a1.set_title("TMS mass vs heat load")
    a1.grid(alpha=0.3)
    etas, drags = [1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7], []
    for e in etas:
        tms_.ram_recovery = e
        r = tms_.SizeAtPoint(point)
        drags.append(r.ram_drag_raw)
    tms_.ram_recovery = 1.0
    a2.plot(etas, drags, "s-")
    a2.axhline(0, color="k", lw=0.8)
    a2.invert_xaxis()
    a2.set_xlabel("intake ram recovery η_ram [-]")
    a2.set_ylabel("net duct drag [N] (negative = thrust)")
    a2.set_title("Ram-air duct drag at the design point")
    a2.grid(alpha=0.3)
    fig.tight_layout()
    _save(fig, "tms", "tms_trends")


def _schematic():
    from matplotlib.patches import FancyBboxPatch
    fig, ax = plt.subplots(figsize=(10, 3.4))
    ax.axis("off")
    boxes = {"stack": (0.02, 0.45, "fuel-cell stack\n(T_op)"),
             "hex1": (0.30, 0.45, "HEX 1\ncoolant → LH₂"),
             "hex2": (0.58, 0.45, "HEX 2 (n units)\ncoolant → ram air"),
             "pump": (0.30, 0.02, "pump\n(electric load on the FC)")}
    for x, y, txt in boxes.values():
        ax.add_patch(FancyBboxPatch((x, y), 0.2, 0.3, boxstyle="round,pad=0.02", fc="#eef4fa", ec="k"))
        ax.text(x + 0.1, y + 0.15, txt, ha="center", va="center", fontsize=9)
    arrow = dict(arrowstyle="->", lw=1.5, color="tab:red")
    ax.annotate("", xy=(0.30, 0.6), xytext=(0.22, 0.6), arrowprops=arrow)
    ax.annotate("", xy=(0.58, 0.6), xytext=(0.50, 0.6), arrowprops=arrow)
    ax.annotate("", xy=(0.50, 0.17), xytext=(0.68, 0.45), arrowprops=arrow)
    ax.annotate("", xy=(0.12, 0.45), xytext=(0.30, 0.17), arrowprops=arrow)
    ax.text(0.26, 0.64, "coolant", color="tab:red", fontsize=8, ha="center")
    blue = dict(arrowstyle="->", color="tab:blue")
    ax.annotate("", xy=(0.45, 0.77), xytext=(0.45, 0.97), arrowprops=blue)
    ax.text(0.46, 0.93, "LH₂ from tank\n(saturated liquid)", color="tab:blue", fontsize=8, va="top")
    ax.annotate("", xy=(0.15, 0.77), xytext=(0.35, 0.77),
                arrowprops=dict(arrowstyle="->", color="tab:blue", connectionstyle="arc3,rad=0.5"))
    ax.text(0.25, 1.12, "H₂ at T_op − ΔT\nto the stack", color="tab:blue", fontsize=8, ha="center", va="top")
    cyan = dict(arrowstyle="->", color="tab:cyan", lw=2)
    ax.annotate("", xy=(0.66, 0.77), xytext=(0.66, 0.97), arrowprops=cyan)
    ax.text(0.67, 0.93, "ram air in\n(intake, diffuser)", color="tab:cyan", fontsize=8, va="top")
    ax.annotate("", xy=(0.97, 0.6), xytext=(0.80, 0.6), arrowprops=cyan)
    ax.text(0.885, 0.64, "nozzle\n(net drag)", color="tab:cyan", fontsize=8, ha="center")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    ax.set_title("Class-II TMS: the FC_SPEC architecture")
    _save(fig, "tms", "tms_architecture")


def hydrogen():
    """Heat rejected to the coolant vs the phase of the product water."""
    from PhlyGreen.Systems.FuelCell.FuelCell import FuelCell as F
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4))
    rh = np.linspace(0, 1, 101)
    for P, ls in ((1.5e5, "-"), (2.5e5, "--")):
        xs = []
        for r in rh:
            fc = F(None); fc.T_op, fc.Target_Press, fc.stoich, fc.inlet_rh = 353.15, P, 2.0, r
            xs.append(fc.product_water_vapour_fraction())
        a1.plot(rh, xs, ls, label=f"80 °C, {P/1e5:.1f} bar, λ = 2")
    a1.set_xlabel("cathode inlet relative humidity (at T_op) [-]")
    a1.set_ylabel("vapour fraction of product water $x_v$ [-]")
    a1.set_title("Product water leaving as vapour (stack exit)")
    a1.grid(alpha=0.3); a1.legend(fontsize=8)
    V = np.linspace(0.45, 0.85, 50)
    F_ = F.FARADAY_CONST
    for xv, ls in ((0.0, "-"), (0.5, ":"), (1.0, "--")):
        E = (F.DELTA_H_REACT - xv * (F.DELTA_H_REACT - F.DELTA_H_REACT_LHV)) / (2 * F_)
        a2.plot(V, (E - V) / V, ls, label=f"$x_v$ = {xv:.1f} (E_tn = {E:.3f} V)")
    a2.set_xlabel("cell voltage [V]")
    a2.set_ylabel("coolant heat / gross electric power [-]")
    a2.set_title("Heat per unit of electric power")
    a2.grid(alpha=0.3); a2.legend(fontsize=8)
    fig.tight_layout()
    _save(fig, "hydrogen", "fc_heat_basis")


GROUPS = {"reference": reference, "a320": a320, "tms": tms, "hydrogen": hydrogen}

if __name__ == "__main__":
    for name in (sys.argv[1:] or GROUPS):
        print(f"[{name}]")
        GROUPS[name]()
