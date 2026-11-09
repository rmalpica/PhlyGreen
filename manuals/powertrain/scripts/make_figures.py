"""Draw every figure of the powertrain manual.

    python manuals/powertrain/scripts/make_figures.py              # reuse data/powertrain_data.json
    python manuals/powertrain/scripts/make_figures.py --recompute  # run compute_data.py first

Two kinds of figures are written to ../figures/:

* graph_*.tex: TikZ drawings of the powertrain graphs. They are generated from the graph
  objects themselves (Section "Graph drawings" below), so every node, edge and efficiency
  label is the one the builder in PhlyGreen/Systems/Powertrain/graph.py adds. Only the
  positions of the nodes are chosen here.
* *.pdf: matplotlib plots of the numbers in ../data/powertrain_data.json.
"""

import inspect
import json
import os
import subprocess
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402
import numpy as np                                  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
MANUAL = os.path.dirname(HERE)
DATA = os.path.join(MANUAL, "data", "powertrain_data.json")
FIG = os.path.join(MANUAL, "figures")
sys.path.insert(0, HERE)

from PhlyGreen.Systems.Powertrain.graph import (traditional_graph, parallel_hybrid_graph,  # noqa: E402
                                                serial_hybrid_graph, fuelcell_battery_graph)
import example_new_architecture as newarch          # noqa: E402

# Fixed categorical order (blue, orange, aqua, yellow, magenta) and neutral inks, as in the
# other PhlyGreen manuals.
C1, C2, C3, C4, C5 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
INK, INK2, GRID, MUTED = "#0b0b0b", "#52514e", "#e4e3df", "#a8a7a2"
plt.rcParams.update({
    "font.family": "serif", "font.size": 8.5, "axes.labelsize": 8.5,
    "axes.titlesize": 8.5, "legend.fontsize": 7.5, "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5, "axes.edgecolor": INK2, "axes.labelcolor": INK,
    "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.axisbelow": True, "axes.spines.top": False,
    "axes.spines.right": False, "lines.linewidth": 1.4, "legend.frameon": False,
    "pdf.fonttype": 42, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
})


def save(fig, name):
    path = os.path.join(FIG, name)
    fig.savefig(path)
    plt.close(fig)
    print("  ", path)


# ==========================================================================================
# Graph drawings
# ==========================================================================================
# Component name and efficiency symbol of each builder argument (from the comments in
# graph.py).
COMPONENT = {
    "eta_gt": ("gas turbine", r"\eta_{gt}"), "eta_gb": ("gearbox", r"\eta_{gb}"),
    "eta_pp": ("propeller", r"\eta_{pp}"), "eta_pm": ("PMAD", r"\eta_{pm}"),
    "eta_em": ("motor", r"\eta_{em}"), "eta_em1": ("generator", r"\eta_{em1}"),
    "eta_em2": ("motor", r"\eta_{em2}"), "eta_fc": ("fuel cell", r"\eta_{fc}"),
    "eta_gen": ("generator", r"\eta_{gen}"), "eta_fan": ("fan", r"\eta_{fan}"),
}
SYMBOL = {"PfH2": r"P_{f,\mathrm{H_2}}"}            # all other names: P_{rest}
PHI_SENTINEL = 0.25


def build_with_sentinels(builder, phi_name):
    """Call ``builder`` with a distinct sentinel number for every efficiency argument and
    PHI_SENTINEL for the split ratio. Returns the graph and {sentinel: argument name}."""
    kwargs, sentinel_to_arg = {}, {}
    for k, name in enumerate(inspect.signature(builder).parameters):
        if name == phi_name:
            kwargs[name] = PHI_SENTINEL
        else:
            value = round(0.61 + 0.01 * k, 2)
            kwargs[name] = value
            sentinel_to_arg[value] = name
    return builder(**kwargs), sentinel_to_arg


def extract_primitives(graph, sentinel_to_arg):
    """Recover the primitives from the rows of a PowertrainGraph.

    Each row is (coefficients, right-hand side). A converter or combiner row has +1 on its
    output and -eta on each input; a split row has phi and phi - 1; a sink row has a
    non-zero right-hand side. Returns a list of dictionaries.
    """
    primitives = []
    for coeffs, rhs in graph._rows:          # the stored equations of the graph
        if rhs != 0.0:
            (var,) = coeffs
            primitives.append({"kind": "sink", "var": var, "value": rhs})
            continue
        outputs = [v for v, c in coeffs.items() if c == 1.0]
        if len(outputs) == 1 and all(c < 0 for v, c in coeffs.items() if v != outputs[0]):
            inputs = [v for v in coeffs if v != outputs[0]]
            eta = round(-coeffs[inputs[0]], 2)
            primitives.append({"kind": "converter" if len(inputs) == 1 else "combiner",
                               "out": outputs[0], "inputs": inputs,
                               "arg": sentinel_to_arg.get(eta), "eta": eta})
            continue
        a = [v for v, c in coeffs.items() if abs(c - PHI_SENTINEL) < 1e-12]
        b = [v for v, c in coeffs.items() if abs(c - (PHI_SENTINEL - 1.0)) < 1e-12]
        if len(a) == 1 and len(b) == 1:
            primitives.append({"kind": "split", "a": a[0], "b": b[0]})
            continue
        raise ValueError(f"unrecognized row {coeffs} = {rhs}")
    return primitives


def symbol(var):
    return SYMBOL.get(var, "P_{%s}" % var[1:])


def edge_label(prim, overrides):
    if prim["arg"] is None:                          # a literal efficiency, e.g. 1.0
        return None
    name, sym = overrides.get(prim["arg"], COMPONENT[prim["arg"]])
    return r"%s\\$%s$" % (name, sym)


def label_side(p0, p1, route):
    """Place an edge label above a horizontal stretch and right of a vertical one."""
    if route == "-|":
        return "above, pos=0.25"
    if route == "|-":
        return "above, pos=0.75"
    return "right" if abs(p0[0] - p1[0]) < 1e-9 else "above"


def write_graph_tikz(filename, graph, sentinel_to_arg, layout, overrides=None):
    """Write figures/<filename> with a TikZ picture of ``graph``.

    ``layout`` holds: ``pos`` {variable: (x, y)} in cm, ``desc`` {variable: short meaning},
    ``sum`` {combiner output: (x, y)} for the summing junctions, ``sink`` (x, y) for the
    normalization marker, ``routes`` {(from, to): '-|' or '|-'} for bent edges and
    ``fill`` {variable: colour}.
    """
    overrides = overrides or {}
    prims = extract_primitives(graph, sentinel_to_arg)
    pos, desc = layout["pos"], layout["desc"]
    missing = [v for v in graph.variables if v not in pos]
    if missing:
        raise KeyError(f"{filename}: no position for {missing}")
    routes = layout.get("routes", {})
    lines = [r"\begin{tikzpicture}[>={Stealth[length=2mm]},",
             r"  var/.style={draw, rounded corners=2pt, minimum width=16mm, minimum height=9mm,",
             r"              align=center, font=\small, fill=#1}, var/.default=white,",
             r"  junction/.style={draw, circle, inner sep=0.5pt, font=\small, fill=white},",
             r"  lbl/.style={font=\scriptsize, align=center, inner sep=1.5pt},",
             r"  flow/.style={->, thick}, plain/.style={thick},",
             r"  splitline/.style={densely dashed, thick, draw=orange!80!black}]"]
    for k, var in enumerate(graph.variables):
        x, y = pos[var]
        fill = layout.get("fill", {}).get(var, "white")
        lines.append(r"\node[var=%s] (%s) at (%.2f,%.2f) {$%s$\,[%d]\\[-2pt]{\scriptsize %s}};"
                     % (fill, var, x, y, symbol(var), k, desc[var]))
    for prim in prims:
        if prim["kind"] == "converter":
            src, dst = prim["inputs"][0], prim["out"]
            route = routes.get((src, dst), "--")
            text = edge_label(prim, overrides)
            node = r" node[lbl, %s] {%s}" % (label_side(pos[src], pos[dst], route), text) if text else ""
            lines.append(r"\draw[flow] (%s) %s%s (%s);" % (src, route, node, dst))
        elif prim["kind"] == "combiner":
            out = prim["out"]
            jx, jy = layout["sum"][out]
            jname = "sum" + out
            lossless = prim["arg"] is None and prim["eta"] == 1.0
            lines.append(r"\node[junction] (%s) at (%.2f,%.2f) {$\Sigma$};" % (jname, jx, jy))
            style = "plain" if lossless else "flow"
            for src in prim["inputs"]:
                route = routes.get((src, out), "--")
                lines.append(r"\draw[%s] (%s) %s (%s);" % (style, src, route, jname))
            route = routes.get((jname, out), "--")
            text = edge_label(prim, overrides)
            node = r" node[lbl, %s] {%s}" % (label_side((jx, jy), pos[out], route), text) if text else ""
            lines.append(r"\draw[%s] (%s) %s%s (%s);" % (style, jname, route, node, out))
        elif prim["kind"] == "split":
            a, b = prim["a"], prim["b"]
            side = "left" if abs(pos[a][0] - pos[b][0]) < 1e-9 else "above"
            sym = layout.get("split_symbol", r"\varphi")
            lines.append(r"\draw[splitline] (%s) -- node[lbl, %s, text=orange!60!black] {split\\$%s$} (%s);"
                         % (a, side, sym, b))
        elif prim["kind"] == "sink":
            sx, sy = layout["sink"]
            lines.append(r"\node[lbl, draw, rounded corners=2pt, fill=gray!10, minimum height=6mm] (sink) at (%.2f,%.2f) {$=%g$};"
                         % (sx, sy, prim["value"]))
            lines.append(r"\draw[flow] (%s) -- (sink);" % prim["var"])
    lines.append(r"\end{tikzpicture}")
    # Extent of the drawing: nodes are about 1.7 cm wide, the sink marker about 0.8 cm, and
    # a split label on the left adds about 0.7 cm.
    xs = [p[0] for p in pos.values()]
    left = min(xs) - 0.85 - 0.7
    right = max(max(xs) + 0.85, layout["sink"][0] + 0.4)
    width_cm = right - left
    body = "\n".join(lines)
    if width_cm > 15.9:
        body = "\\resizebox{\\linewidth}{!}{%\n" + body + "%\n}"
    with open(os.path.join(FIG, filename), "w") as f:
        f.write("%% Generated by manuals/powertrain/scripts/make_figures.py from the graph builder.\n")
        f.write("%% Do not edit by hand.\n" + body + "\n")
    print("  ", os.path.join(FIG, filename), f"({len(prims)} primitives)")
    return prims


FUEL, BAT, OUT = "gray!12", "teal!12", "blue!8"


def draw_graphs(d):
    # --- traditional ---------------------------------------------------------------------
    g, s = build_with_sentinels(traditional_graph, None)
    write_graph_tikz("graph_traditional.tex", g, s, {
        "pos": {"Pf": (0, 0), "Pgt": (3.2, 0), "Pgb": (6.4, 0), "Pp": (9.6, 0)},
        "desc": {"Pf": "fuel", "Pgt": "GT shaft", "Pgb": "gearbox out", "Pp": "propulsive"},
        "sink": (11.4, 0), "fill": {"Pf": FUEL, "Pp": OUT}})

    # --- turbofan: the same builder, read with the turbofan efficiencies ------------------
    tf = d["designs"]["Turbofan"]
    assert tf["gearbox_eta"] == 1.0 and tf["propeller_eta"] == 1.0
    g, s = build_with_sentinels(traditional_graph, None)
    write_graph_tikz("graph_turbofan.tex", g, s, {
        "pos": {"Pf": (0, 0), "Pgt": (3.2, 0), "Pgb": (6.4, 0), "Pp": (9.6, 0)},
        "desc": {"Pf": "fuel", "Pgt": "thrust power", "Pgb": "thrust power",
                 "Pp": "thrust power"},
        "sink": (11.4, 0), "fill": {"Pf": FUEL, "Pp": OUT}},
        overrides={"eta_gt": ("engine", r"\eta_o"), "eta_gb": ("gearbox", "1"),
                   "eta_pp": ("fan", "1")})

    # --- parallel hybrid -----------------------------------------------------------------
    g, s = build_with_sentinels(parallel_hybrid_graph, "phi")
    write_graph_tikz("graph_parallel.tex", g, s, {
        "pos": {"Pf": (0, 1.5), "Pgt": (3.3, 1.5), "Pbat": (0, -1.5), "Pe1": (3.3, -1.5),
                "Pgb": (6.6, -1.5), "Ps1": (9.3, 0), "Pp1": (12.2, 0)},
        "desc": {"Pf": "fuel", "Pgt": "GT shaft", "Pbat": "battery", "Pe1": "motor input",
                 "Pgb": "motor shaft", "Ps1": "gearbox out", "Pp1": "propulsive"},
        "sum": {"Ps1": (6.6, 0)}, "sink": (13.8, 0),
        "routes": {("Pgt", "Ps1"): "-|"},
        "fill": {"Pf": FUEL, "Pbat": BAT, "Pp1": OUT}})

    # --- serial hybrid -------------------------------------------------------------------
    g, s = build_with_sentinels(serial_hybrid_graph, "phi")
    write_graph_tikz("graph_serial.tex", g, s, {
        "pos": {"Pf": (0, 1.5), "Pgt": (3.0, 1.5), "Ps1": (6.0, 1.5), "Pbat": (0, -1.5),
                "Pe1": (11.2, 0), "Pgb": (11.2, -3.2), "Pgen": (8.0, -3.2), "Pp1": (4.8, -3.2)},
        "desc": {"Pf": "fuel", "Pgt": "GT shaft", "Ps1": "generator out", "Pbat": "battery",
                 "Pe1": "bus out", "Pgb": "motor shaft", "Pgen": "gearbox out",
                 "Pp1": "propulsive"},
        "sum": {"Pe1": (8.6, 0)}, "sink": (2.6, -3.2),
        "routes": {("Ps1", "Pe1"): "-|", ("Pbat", "Pe1"): "-|"},
        "fill": {"Pf": FUEL, "Pbat": BAT, "Pp1": OUT}})

    # --- fuel cell + battery -------------------------------------------------------------
    g, s = build_with_sentinels(fuelcell_battery_graph, "phi")
    write_graph_tikz("graph_fuelcell_battery.tex", g, s, {
        "pos": {"PfH2": (0, 1.5), "Pfc": (3.3, 1.5), "Pbat": (3.3, -1.5), "Pe1": (9.0, 0),
                "Pem": (9.0, -3.2), "Pgb": (5.9, -3.2), "Pp1": (2.8, -3.2)},
        "desc": {"PfH2": "hydrogen", "Pfc": "fuel-cell out", "Pbat": "battery",
                 "Pe1": "bus out", "Pem": "motor shaft", "Pgb": "gearbox out",
                 "Pp1": "propulsive"},
        "sum": {"Pe1": (6.2, 0)}, "sink": (0.6, -3.2),
        "routes": {("Pfc", "Pe1"): "-|", ("Pbat", "Pe1"): "-|"},
        "fill": {"PfH2": FUEL, "Pbat": BAT, "Pp1": OUT}})

    # --- worked example: partial turbo-electric (scripts/example_new_architecture.py) ------
    g, s = build_with_sentinels(newarch.partial_turboelectric_graph, "xi")
    write_graph_tikz("graph_new_architecture.tex", g, s, {
        "pos": {"Pf": (0, 0), "Pgt": (2.6, 0), "Pa": (5.2, 1.5), "Ps1": (7.8, 1.5),
                "Pp1": (10.4, 1.5), "Pb": (5.2, -1.5), "Pgen": (7.8, -1.5),
                "Pe1": (10.4, -1.5), "Pem": (13.0, -1.5), "Pp2": (13.0, 0.0),
                "Pp": (15.4, 1.5)},
        "desc": {"Pf": "fuel", "Pgt": "GT shaft", "Pa": "to gearbox", "Ps1": "gearbox out",
                 "Pp1": "propeller", "Pb": "to generator", "Pgen": "generator out",
                 "Pe1": "motor input", "Pem": "motor shaft", "Pp2": "fan",
                 "Pp": "propulsive"},
        "sum": {"Pgt": (4.0, 0), "Pp": (13.0, 1.5)}, "sink": (15.4, 0.0),
        "split_symbol": r"\xi",
        "routes": {("Pa", "Pgt"): "-|", ("Pb", "Pgt"): "-|"},
        "fill": {"Pf": FUEL, "Pp": OUT}})


# ==========================================================================================
# Plots
# ==========================================================================================
def fig_phi_sweep(d):
    sw, eta = d["phi_sweep"], d["eta"]
    phi = np.array(sw["phi"])
    par, ser, fcb = sw["parallel"], sw["serial"], sw["fuelcell_battery"]
    fig, axes = plt.subplots(1, 3, figsize=(6.6, 2.3))
    ax = axes[0]
    ax.plot(phi, par["Pf"], color=C1, label="parallel $P_f$")
    ax.plot(phi, ser["Pf"], color=C2, label="serial $P_f$")
    ax.plot(phi, fcb["PfH2"], color=C3, label=r"FC graph $P_{f,\mathrm{H_2}}$")
    ax.set_xlabel(r"$\varphi$"); ax.set_ylabel("fuel or hydrogen power / $P_p$")
    ax.legend(loc="upper right")
    ax = axes[1]
    ax.plot(phi, par["Pbat"], color=C1, label="parallel")
    ax.plot(phi, ser["Pbat"], color=C2, label="serial")
    ax.plot(phi, fcb["Pbat"], color=C3, label="FC graph")
    ax.set_xlabel(r"$\varphi$"); ax.set_ylabel("battery power / $P_p$")
    ax.legend(loc="upper left")
    ax = axes[2]
    share = np.array(par["Pgb"]) * eta["gb"] * eta["pp"]   # motor contribution to Pp1
    ax.plot(phi, share, color=C1, label="motor share")
    ax.plot(phi, phi, color=MUTED, ls="--", lw=1.0, label=r"$\varphi$")
    ax.set_xlabel(r"$\varphi$"); ax.set_ylabel("share of propulsive power")
    ax.set_ylim(0, 1.02)
    ax.legend(loc="lower right")
    for a, t in zip(axes, "abc"):
        a.set_title(f"({t})", loc="left")
    fig.tight_layout(w_pad=0.8)
    save(fig, "phi_sweep.pdf")


def fig_mission(d):
    fig, axes = plt.subplots(2, 2, figsize=(6.6, 4.2), sharex="col")
    for col, name in enumerate(("Parallel", "Serial")):
        m = d["mission"][name]
        t = np.array(m["t"]) / 60.0
        pp = np.array(m["PP"]) / 1e6
        r = [np.array(x) for x in m["ratios"]]
        ax = axes[0, col]
        ax.plot(t, pp, color=INK2, lw=1.0, label="propulsive $P_p$")
        ax.plot(t, r[1] * pp, color=C2, lw=1.0, label=r"GT shaft $P_p\,\Pi_1$")
        ax.plot(t, r[5] * pp, color=C3, lw=1.0, label=r"battery $P_p\,\Pi_5$")
        ax.plot(t, r[2] * pp, color=C1, lw=1.0, ls="--", label=r"motor shaft $P_p\,\Pi_2$")
        ax.axvline(m["mission_end_time"] / 60.0, color=MUTED, lw=0.8)
        ax.set_ylabel("power [MW]")
        ax.set_title(f"({'ab'[col]}) {name.lower()} hybrid", loc="left")
        ax = axes[1, col]
        ax.plot(t, r[0], color=C2, lw=1.0, label=r"$\Pi_0 = P_f/P_p$")
        ax.plot(t, r[5], color=C3, lw=1.0, label=r"$\Pi_5 = P_{bat}/P_p$")
        ax.plot(t, m["phi"], color=INK2, lw=1.0, ls=":", label=r"$\varphi(t)$")
        ax.axvline(m["mission_end_time"] / 60.0, color=MUTED, lw=0.8)
        ax.set_xlabel("time [min]"); ax.set_ylabel("ratio [-]")
        ax.set_title(f"({'cd'[col]})", loc="left")
        if col == 0:
            ax.legend(loc="center left")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper center", ncol=4)
    save(fig, "mission_ratios.pdf")


def fig_mass_breakdown(d):
    ds = d["designs"]
    names = ["Traditional", "Parallel", "Serial", "Hydrogen", "FuelCellBattery", "Turbofan"]
    labels = ["Traditional", "Parallel", "Serial", "Hydrogen", "FC+battery", "Turbofan"]
    parts = {  # (label, colour, function of the design record)
        "gas turbine / engines": (C2, lambda r: r["WThermal"] or 0.0),
        "generator": (C4, lambda r: r["WGenerator"] or 0.0),
        "motor": (C1, lambda r: ((r["WMotor"] or 0.0) - (r["WGenerator"] or 0.0))
                  if r.get("fc_motor") is None else r["fc_motor"]),
        "PMAD": (C5, lambda r: r["WPMAD"] or 0.0 if r.get("fc_pmad") is None else r["fc_pmad"]),
        "stack + BoP": (C3, lambda r: (r["fc_stack_bop_pmad"] - r["fc_pmad"])
                        if r.get("fc_pmad") is not None else 0.0),
    }
    fig, ax = plt.subplots(figsize=(6.3, 2.6))
    x = np.arange(len(names))
    bottom = np.zeros(len(names))
    for label, (colour, fn) in parts.items():
        vals = np.array([fn(ds[n]) for n in names])
        ax.bar(x, vals, bottom=bottom, color=colour, width=0.6, label=label)
        bottom += vals
    for i, n in enumerate(names):
        ax.text(x[i], bottom[i] + 60, f"{ds[n]['WPT']:.0f}", ha="center", va="bottom", fontsize=7)
    ax.set_xticks(x, labels)
    ax.set_ylabel("powertrain mass [kg]")
    ax.set_ylim(0, bottom.max() * 1.4)
    ax.legend(loc="upper left", ncol=3)
    ax.grid(axis="x", visible=False)
    save(fig, "mass_breakdown.pdf")


def fig_design_sweep(d):
    sw = d["design_sweep"]
    phi = np.array(sw["phi_end"])
    fig, axes = plt.subplots(1, 2, figsize=(6.6, 2.5))
    ax = axes[0]
    for name, colour in (("Parallel", C1), ("Serial", C2)):
        recs = sw[name]
        ax.plot(phi, [r["WTO"] / 1e3 for r in recs], "o-", color=colour, ms=3, label=name.lower())
    ax.axhline(d["designs"]["Traditional"]["WTO"] / 1e3, color=MUTED, ls="--", lw=1.0,
               label="traditional")
    ax.set_xlabel(r"cruise $\varphi$ at end of cruise"); ax.set_ylabel("take-off mass [t]")
    ax.legend(loc="center right")
    ax.set_title("(a)", loc="left")
    ax = axes[1]
    for name, colour, mk in (("Parallel", C1, "o"), ("Serial", C2, "s")):
        recs = sw[name]
        ax.plot(phi, [r["WThermal"] for r in recs], mk + "-", color=colour, ms=3,
                label=f"{name.lower()}: gas turbine")
        ax.plot(phi, [(r["WElectric"] or 0.0) for r in recs], mk + "--", color=colour, ms=3,
                label=f"{name.lower()}: electric drive")
        ax.plot(phi, [r["WBat"] or 0.0 for r in recs], mk + ":", color=colour, ms=3,
                label=f"{name.lower()}: battery")
    ax.set_xlabel(r"cruise $\varphi$ at end of cruise"); ax.set_ylabel("mass [kg]")
    ax.set_title("(b)", loc="left")
    fig.tight_layout(rect=(0, 0.16, 1, 1))
    handles, labels = ax.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=3, fontsize=7)
    save(fig, "design_sweep.pdf")


def fig_motor(d):
    m = d["motor"]
    p = np.array(m["power"]) / 1e6
    fig, axes = plt.subplots(1, 2, figsize=(6.3, 2.3))
    ax = axes[0]
    ax.plot(p, m["eta"], color=C1)
    ax.set_xlabel("motor shaft power [MW]"); ax.set_ylabel(r"motor efficiency $\eta_{em}$")
    ax.set_title("(a) d-q motor, 2000 kW, 800 V, 1200 rpm", loc="left")
    ax = axes[1]
    ax.plot(p, m["pbat_ratio_smart"], color=C1, label="d-q motor model")
    ax.axhline(m["pbat_ratio_const"], color=MUTED, ls="--", lw=1.0,
               label=r"constant $\eta_{em}$ = %.2f" % d["eta"]["em"])
    ax.set_xlabel("propulsive power $P_p$ [MW]"); ax.set_ylabel(r"$\Pi_5 = P_{bat}/P_p$")
    ax.set_title(r"(b) parallel graph, $\varphi$ = 0.3", loc="left")
    ax.legend(loc="upper right")
    fig.tight_layout()
    save(fig, "motor_model.pdf")


def main():
    if "--recompute" in sys.argv or not os.path.exists(DATA):
        subprocess.run([sys.executable, os.path.join(HERE, "compute_data.py")], check=True)
    with open(DATA) as f:
        d = json.load(f)
    draw_graphs(d)
    fig_phi_sweep(d)
    fig_mission(d)
    fig_mass_breakdown(d)
    fig_design_sweep(d)
    fig_motor(d)


if __name__ == "__main__":
    main()
