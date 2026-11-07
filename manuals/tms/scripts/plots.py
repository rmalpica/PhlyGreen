"""Figures of the TMS manual, drawn from ../data/tms_data.json (see compute_data.py).

Each function writes one vector PDF to ../figures/.
"""

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402
import numpy as np                                  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "tms_data.json")
FIG = os.path.join(HERE, "..", "figures")

# Fixed categorical order (blue, orange, aqua, yellow, magenta) and neutral inks.
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


def short(name):
    """'Mission/Climb1' -> 'M/Climb1', 'Diversion/Cruise' -> 'D/Cruise'."""
    return name.replace("Mission/", "M/").replace("Diversion/", "D/").replace("Takeoff", "Take-off")


def save(fig, name):
    path = os.path.join(FIG, name)
    fig.savefig(path)
    plt.close(fig)
    print("  ", path)


# ------------------------------------------------------------------------------------
def fig_heat_profile(d):
    h = d["h2_II"]["history"]
    dp = d["h2_II"]["tms"]["design_point"]
    t = np.array(h["t"]) / 60.0
    q = np.array(h["Q"]) / 1e3
    fig, ax = plt.subplots(figsize=(6.3, 2.7))
    ax.plot(t, q, color=C1, lw=1.0, label="fuel-cell heat $Q_{fc}(t)$")
    for i, s in enumerate(h["segments"]):
        if i % 2:
            ax.axvspan(s["t0"] / 60, s["t1"] / 60, color="#f3f2ef", lw=0, zorder=0)
    pts = h["thermal_profile"]
    tp = [p for p in pts if p["name"] != "Takeoff"]
    # segment peaks: place them at the time of their segment's peak in the history
    seg_t = {s["name"]: (s["t0"], s["t1"]) for s in h["segments"]}
    for p in tp:
        t0, t1 = seg_t[p["name"]]
        mask = (np.array(h["t"]) >= t0) & (np.array(h["t"]) < t1)
        k = np.argmax(np.where(mask, np.array(h["Q"]), -1))
        is_dp = p["name"] == dp
        ax.plot(t[k], q[k], "o", ms=5 if is_dp else 3.5, mfc=C2 if is_dp else "white",
                mec=C2 if is_dp else C1, mew=1.0, zorder=5)
    to = next(p for p in pts if p["name"] == "Takeoff")
    ax.plot(0, to["Q_fc"] / 1e3, "s", ms=4.5, mfc="white", mec=INK2, mew=1.0, zorder=5)
    ax.plot([], [], "o", ms=3.5, mfc="white", mec=C1, label="segment peaks (thermal profile)")
    ax.plot([], [], "o", ms=5, mfc=C2, mec=C2, label=f"selected design point ({short(dp)})")
    ax.plot([], [], "s", ms=4.5, mfc="white", mec=INK2, label="take-off/OEI point (not flown)")
    ax.set_xlabel("mission time [min]")
    ax.set_ylabel("fuel-cell heat [kW]")
    ax.set_xlim(left=-3)
    ax.set_ylim(0, 5600)
    ax.legend(loc="lower left", bbox_to_anchor=(0.16, 0.03), fontsize=6.8)
    # inset: the first 30 minutes (climb)
    ins = ax.inset_axes([0.30, 0.47, 0.36, 0.45])
    ins.plot(t, q, color=C1, lw=1.0)
    for s in h["segments"][:5]:
        ins.axvline(s["t0"] / 60, color=MUTED, lw=0.5)
        ins.text(0.5 * (s["t0"] + s["t1"]) / 60, 1300, s["name"].split("/")[1],
                 rotation=90, fontsize=5.5, ha="center", va="bottom", color=INK2)
    for p in tp[:5]:
        t0, t1 = seg_t[p["name"]]
        mask = (np.array(h["t"]) >= t0) & (np.array(h["t"]) < t1)
        k = np.argmax(np.where(mask, np.array(h["Q"]), -1))
        is_dp = p["name"] == dp
        ins.plot(t[k], q[k], "o", ms=4 if is_dp else 3, mfc=C2 if is_dp else "white",
                 mec=C2 if is_dp else C1, mew=0.8, zorder=5)
    ins.plot(0, to["Q_fc"] / 1e3, "s", ms=3.5, mfc="white", mec=INK2, zorder=5)
    ins.set_xlim(-1, 30)
    ins.set_ylim(1000, 5400)
    ins.tick_params(labelsize=5.5)
    ins.set_title("climb, first 30 min", fontsize=6.5, pad=2)
    save(fig, "heat_profile.pdf")


def fig_candidates(d):
    c = d["h2_II"]["tms"]["candidates"]
    names = [short(x["point"]) for x in c]
    mass = [x["mass"] for x in c]
    feas = [x["feasible"] for x in c]
    fig, ax = plt.subplots(figsize=(6.3, 2.6))
    x = np.arange(len(c))
    ax.bar(x, mass, 0.6, color=[C1 if f else MUTED for f in feas], edgecolor="white", lw=0.8)
    for i, cc in enumerate(c):
        txt = "feasible" if cc["feasible"] else f"{100*cc['worst_shortfall']:.1f} %"
        ax.text(i, mass[i] + 20, txt, ha="center", va="bottom", fontsize=6.8, color=INK2)
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=30, ha="right")
    ax.set_ylabel("TMS mass [kg]")
    ax.set_xlabel("candidate design point")
    ax.set_ylim(0, max(mass) * 1.32)
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=C1, label="feasible at every point (lightest is chosen)"),
                       Patch(color=MUTED, label="infeasible (label: worst shortfall)")],
              loc="upper center", ncol=2)
    save(fig, "candidates.pdf")


def fig_rating(d):
    rows = d["h2_II"]["tms"]["rating"]
    fig, ax = plt.subplots(figsize=(6.3, 2.6))
    x = np.arange(len(rows))
    ax.bar(x - 0.2, [r["q_req"] / 1e3 for r in rows], 0.38, color=C1, label="heat to reject $Q_{ext}$")
    ax.bar(x + 0.2, [r["q_cap"] / 1e3 for r in rows], 0.38, color=C2,
           label="capacity of the chosen hardware")
    ax.set_xticks(x)
    ax.set_xticklabels([short(r["name"]) for r in rows], rotation=30, ha="right")
    ax.set_ylabel("heat [kW]")
    ax.legend(loc="upper right", ncol=2)
    ax.set_ylim(0, max(r["q_cap"] for r in rows) / 1e3 * 1.18)
    save(fig, "rating.pdf")


def fig_heat_split(d):
    rows = d["h2_II"]["heat_split"]
    fig, ax = plt.subplots(figsize=(6.3, 2.6))
    x = np.arange(len(rows))
    a = np.array([r["q_ram"] for r in rows]) / 1e3
    b = np.array([r["q_h2"] for r in rows]) / 1e3
    c = np.array([max(r["q_reactant"], 0.0) for r in rows]) / 1e3
    qfc = np.array([r["Q_fc"] for r in rows]) / 1e3
    ax.bar(x, a, 0.62, color=C1, edgecolor="white", lw=0.6, label="HEX 2: coolant $\\to$ ram air")
    ax.bar(x, b, 0.62, bottom=a, color=C3, edgecolor="white", lw=0.6,
           label="HEX 1: coolant $\\to$ LH$_2$")
    ax.bar(x, c, 0.62, bottom=a + b, color=C4, edgecolor="white", lw=0.6,
           label="reactants inside the stack (when positive)")
    ax.plot(x, qfc, "_", color=INK, ms=13, mew=1.3, label="stack heat $Q_{fc}$")
    ax.set_xticks(x)
    ax.set_xticklabels([short(r["name"]) for r in rows], rotation=30, ha="right")
    ax.set_ylabel("heat [kW]")
    ax.set_ylim(0, qfc.max() * 1.35)
    ax.legend(loc="upper center", ncol=2, fontsize=6.8)
    save(fig, "heat_split.pdf")


def fig_mass_breakdown(d):
    labels, h2, ram, pump, c1 = [], [], [], [], []
    for key, lab in (("h2_I", "Hydrogen\nClass I"), ("h2_II", "Hydrogen\nClass II"),
                     ("fcb_I", "FC+battery\nClass I"), ("fcb_II", "FC+battery\nClass II")):
        s = d[key]
        labels.append(lab)
        if s["tms_class"] == "I":
            c1.append(s["W_TMS"]); h2.append(0); ram.append(0); pump.append(0)
        else:
            u = {x["role"]: x["mass"] for x in s["tms"]["units"]}
            c1.append(0); h2.append(u.get("coolant_to_h2", 0)); ram.append(u.get("coolant_to_ram_air", 0))
            pump.append(s["tms"]["pump_mass"])
    x = np.arange(len(labels))
    c1, h2, ram, pump = map(np.array, (c1, h2, ram, pump))
    fig, ax = plt.subplots(figsize=(4.6, 2.7))
    ax.bar(x, c1, 0.55, color=MUTED, edgecolor="white", lw=0.6, label="Class I: $Q_{peak}/s_{HEX}$")
    ax.bar(x, ram, 0.55, color=C1, edgecolor="white", lw=0.6, label="ram-air exchangers")
    ax.bar(x, h2, 0.55, bottom=ram, color=C3, edgecolor="white", lw=0.6, label="LH$_2$ exchanger")
    ax.bar(x, pump, 0.55, bottom=ram + h2, color=C4, edgecolor="white", lw=0.6,
           label="pump + pump motor")
    tot = c1 + h2 + ram + pump
    for i, v in enumerate(tot):
        ax.text(i, v + 15, f"{v:,.0f} kg", ha="center", va="bottom", fontsize=7, color=INK2)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("TMS mass [kg]")
    ax.set_ylim(0, tot.max() * 1.35)
    ax.legend(loc="upper left", ncol=2)
    save(fig, "mass_breakdown.pdf")


def fig_ram_sweep(d):
    r = d["ram_sweep"]
    V = np.array(r["speeds"])
    alts = r["alts"]
    cols = [C1, C2, C3, C4, C5]
    fig, axs = plt.subplots(1, 2, figsize=(6.5, 2.6))
    ax = axs[0]
    for i, h in enumerate(alts):
        ax.plot(V, np.array(r["mdot"][i]), color=cols[i], label=f"{h/1e3:.0f} km")
    ax.set_xlabel("true airspeed [m/s]")
    ax.set_ylabel("ram-air mass flow [kg/s]")
    ax.legend(title="altitude", loc="upper left", title_fontsize=7.5)
    ax = axs[1]
    i2 = alts.index(2000.0)
    for e, ls in zip(r["eta"], ("-", "--", ":")):
        y = np.array([np.nan if v is None else v for v in r["D"][str(e)][i2]], dtype=float)
        ax.plot(V, y, color=C1, ls=ls, label=f"momentum balance, $\\eta_{{ram}}$ = {e}")
    ax.plot(V, np.array(r["D_cd"][i2]), color=C2, label="$\\Delta C_D$ model used by the aircraft")
    ax.axhline(0, color=INK2, lw=0.6)
    ax.set_xlabel("true airspeed [m/s]")
    ax.set_ylabel("net duct drag at 2 km [N]")
    ax.legend(loc="upper left", fontsize=6.8)
    fig.tight_layout(w_pad=2.0)
    save(fig, "ram_sweep.pdf")


def fig_sensitivity(d):
    s = d["sweeps_h2"]
    fig, axs = plt.subplots(1, 3, figsize=(6.6, 2.4), sharey=True)
    specs = [("coolant_delta_T", "coolant $\\Delta T_{loop}$ [K]"),
             ("ram_air_delta_T", "ram-air $\\Delta T_{air}$ [K]")]
    for ax, (key, lab) in zip(axs[:2], specs):
        rows = s[key]["rows"]
        x = [r["value"] for r in rows]
        ax.plot(x, [r["total_mass"] for r in rows], "o-", color=C1, ms=3, label="total")
        ax.plot(x, [r["mass_ram"] for r in rows], "s--", color=C3, ms=3, label="ram-air HEX")
        ax.plot(x, [r["pump_mass"] for r in rows], "^:", color=C4, ms=3, label="pump + motor")
        ax.axvline(s[key]["default"], color=MUTED, lw=0.8)
        ax.set_xlabel(lab)
        ax.set_ylim(0, None)
    axs[0].set_ylabel("TMS mass [kg]")
    axs[0].legend(loc="center right", fontsize=6.5)
    ax = axs[2]
    for key, lab, col in (("sweeps_h2", "hydrogen", C1), ("sweeps_fcb30", "FC+bat., 800 m", C2)):
        rows = d[key]["takeoff_overtemperature"]["rows"]
        ax.plot([r["value"] for r in rows], [r["total_mass"] for r in rows], "o-", color=col,
                ms=3, label=lab)
    ax.set_xlabel("take-off $\\Delta T_{TO}$ [K]")
    ax.set_ylim(0, None)
    ax.legend(loc="lower left", fontsize=6.5)
    axs[0].set_ylim(0, 1700)
    fig.tight_layout(w_pad=1.0)
    save(fig, "sensitivity.pdf")


def fig_degradation(d):
    bol = {r["name"]: r for r in d["h2_II"]["tms"]["rating"]}
    deg = d["degradation_h2_II"]["rows"]
    names = [r["name"] for r in deg]
    x = np.arange(len(names))
    fig, ax = plt.subplots(figsize=(6.3, 2.6))
    ax.bar(x - 0.27, [bol[n]["q_req"] / 1e3 for n in names], 0.26, color=MUTED,
           label="heat to reject, BOL stack")
    ax.bar(x, [r["q_req"] / 1e3 for r in deg], 0.26, color=C2,
           label="heat to reject, 50 mV loss")
    ax.bar(x + 0.27, [r["q_rej"] / 1e3 for r in deg], 0.26, color=C1,
           label="rejected by the BOL hardware")
    ax.set_xticks(x)
    ax.set_xticklabels([short(n) for n in names], rotation=30, ha="right")
    ax.set_ylabel("heat [kW]")
    ax.set_ylim(0, max(r["q_req"] for r in deg) / 1e3 * 1.25)
    ax.legend(loc="upper right", ncol=3, fontsize=6.8)
    save(fig, "degradation.pdf")


def main():
    with open(DATA) as fh:
        d = json.load(fh)
    os.makedirs(FIG, exist_ok=True)
    fig_heat_profile(d)
    fig_candidates(d)
    fig_rating(d)
    fig_heat_split(d)
    fig_mass_breakdown(d)
    fig_ram_sweep(d)
    fig_sensitivity(d)
    fig_degradation(d)


if __name__ == "__main__":
    main()
