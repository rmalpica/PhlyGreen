"""Figures of the hydrogen-tank manual, drawn from ../data/tank_data.json (see compute_data.py).

Each function writes one vector PDF to ../figures/.
"""

import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402
import numpy as np                                  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "tank_data.json")
FIG = os.path.join(HERE, "..", "figures")

# Same fixed categorical order and neutral inks as the other PhlyGreen manuals.
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


def mark_mission_end(ax, d):
    ax.axvline(d["h2_t"]["MissionTime"] / 60.0, color=MUTED, lw=0.8, ls="-.")


# ------------------------------------------------------------------------------------
def fig_mission_history(d):
    """H2-T tank state along the mission and diversion (track_tank)."""
    h = d["h2_t"]["history"]
    tank = d["h2_t"]["tank"]
    t = np.array(h["t"]) / 60.0
    fig, axes = plt.subplots(5, 1, sharex=True, figsize=(6.3, 7.4))
    axes[0].plot(t, np.array(h["Alt"]) / 1e3, color=INK2)
    axes[0].set_ylabel("altitude [km]")
    axes[1].plot(t, h["P"], color=C1)
    axes[1].axhline(tank["P_min"] / 1e5, color=MUTED, lw=0.8, ls=":")
    axes[1].axhline(tank["P_max"] / 1e5, color=MUTED, lw=0.8, ls=":")
    axes[1].set_ylabel("pressure [bar]")
    axes[2].plot(t, h["m_tot"], color=C3)
    axes[2].set_ylabel("stored H$_2$ [kg]")
    axes[3].plot(t, np.array(h["Consumption"]) * 1e3, color=C1, label="feed to the fuel cell")
    axes[3].plot(t, np.array(h["Vent"]) * 1e3, color=C2, label="vent")
    axes[3].set_ylabel("H$_2$ flow [g/s]")
    axes[3].legend(loc="center right")
    axes[4].plot(t, h["Q_in"], color=C4, label="heat leak $Q_{MLI}$ (all tanks)")
    axes[4].set_ylabel("heat leak [W]")
    axes[4].set_xlabel("time from the start of the climb [min]")
    for ax in axes:
        mark_mission_end(ax, d)
    fig.align_ylabels(axes)
    fig.tight_layout(h_pad=0.4)
    save(fig, "mission_history.pdf")


def fig_capacity_sweep(d):
    s = d["capacity_sweep"]
    cap = np.array(s["capacity"])
    gi_split = [g["gravimetric_index"] for g in s["auto_split"]]
    gi_nosplit = [g["gravimetric_index"] for g in s["no_split"]]
    m_split = [g["mass_system_empty"] for g in s["auto_split"]]
    m_nosplit = [g["mass_system_empty"] for g in s["no_split"]]
    n_split = [g["n_tanks"] for g in s["auto_split"]]
    shape_split = [g["shape"][0] for g in s["auto_split"]]
    gi_nocap = [g["gravimetric_index"] for g in s["auto_split_nocap"]]
    m_nocap = [g["mass_system_empty"] for g in s["auto_split_nocap"]]
    fig, axes = plt.subplots(1, 2, figsize=(6.3, 2.6))
    axes[0].plot(cap, m_nosplit, "o-", ms=3, color=C2, label="one tank (no split)")
    axes[0].plot(cap, m_nocap, "s--", ms=3, color=C3, label="split, no cap on tanks")
    axes[0].plot(cap, m_split, "o-", ms=3, color=C1, label="automatic split (cap 4)")
    axes[0].set_xlabel("stored hydrogen [kg]")
    axes[0].set_ylabel("empty tank system mass [kg]")
    axes[0].legend(loc="upper left")
    axes[1].plot(cap, gi_nosplit, "o-", ms=3, color=C2)
    axes[1].plot(cap, gi_nocap, "s--", ms=3, color=C3)
    axes[1].plot(cap, gi_split, "o-", ms=3, color=C1)
    labels = [f"{n}{sh}" for n, sh in zip(n_split, shape_split)]
    for c, g, lab, prev in zip(cap, gi_split, labels, [None] + labels[:-1]):
        if lab != prev:
            axes[1].annotate(lab, (c, g), textcoords="offset points", xytext=(0, 5),
                             ha="center", fontsize=6.5, color=INK2)
    axes[1].set_xlabel("stored hydrogen [kg]")
    axes[1].set_ylabel("gravimetric index [-]")
    fig.tight_layout()
    save(fig, "capacity_sweep.pdf")


def fig_diameter_sweep(d):
    s = d["diameter_sweep"]
    dm = np.array(s["max_diameter"])
    fig, axes = plt.subplots(1, 2, figsize=(6.3, 2.6))
    axes[0].plot(dm, [g["gravimetric_index"] for g in s["no_split"]], "o-", ms=3, color=C2,
                 label="one tank (no split)")
    axes[0].plot(dm, [g["gravimetric_index"] for g in s["auto_split_nocap"]], "s--", ms=3,
                 color=C3, label="split, no cap")
    axes[0].plot(dm, [g["gravimetric_index"] for g in s["auto_split"]], "o-", ms=3, color=C1,
                 label="automatic split (cap 4)")
    for x, g in zip(dm, s["auto_split"]):
        axes[0].annotate(f"{g['n_tanks']}{g['shape'][0]}", (x, g["gravimetric_index"]),
                         textcoords="offset points", xytext=(0, 5), ha="center",
                         fontsize=6, color=INK2)
    axes[0].set_xlabel("maximum diameter $D_{max}$ [m]")
    axes[0].set_ylabel("gravimetric index [-]")
    axes[0].set_title(f"stand-alone tank, {d['h2_t']['tank']['capacity_total']:.0f} kg", loc="left")
    axes[0].legend(loc="lower right")
    ds = d["design_sweep_dmax"]
    axes[1].plot([r["max_diameter"] for r in ds], [r["weights"]["WTO"] / 1e3 for r in ds],
                 "o-", ms=3, color=C1)
    axes[1].axhline(d["h2_gi"]["weights"]["WTO"] / 1e3, color=MUTED, lw=0.8, ls="--")
    axes[1].annotate("H2-GI (index 0.35)", (ds[0]["max_diameter"], d["h2_gi"]["weights"]["WTO"] / 1e3),
                     textcoords="offset points", xytext=(0, 3), fontsize=6.5, color=INK2)
    axes[1].set_xlabel("maximum diameter $D_{max}$ [m]")
    axes[1].set_ylabel("take-off mass [t]")
    axes[1].set_title("full aircraft design (H2-T)", loc="left")
    fig.tight_layout()
    save(fig, "diameter_sweep.pdf")


def fig_heat_leak(d):
    la = d["heat_leak_altitude"]
    T = [r["T_amb"] for r in la]
    fig, axes = plt.subplots(1, 2, figsize=(6.3, 2.6))
    axes[0].plot(T, [r["q_cond"] for r in la], color=C1, label="solid conduction")
    axes[0].plot(T, [r["q_rad"] for r in la], color=C2, label="radiation")
    axes[0].plot(T, [r["q_gas"] for r in la], color=C3, label="gas conduction")
    axes[0].plot(T, [r["q_cond"] + r["q_rad"] + r["q_gas"] for r in la], color=INK, lw=1.0,
                 label="total")
    axes[0].set_xlabel("ambient temperature $T_h$ [K]")
    axes[0].set_ylabel("heat flux [W/m$^2$]")
    axes[0].set_ylim(0, 33)
    axes[0].legend(loc="upper left", ncol=2)
    ll = d["heat_leak_layers"]
    axes[1].plot([r["n_layers"] for r in ll], [r["flux"] for r in ll], "o-", ms=3, color=C1)
    axes[1].set_xscale("log")
    axes[1].set_yscale("log")
    axes[1].set_xticks([5, 10, 20, 40, 60])
    axes[1].set_xticklabels(["5", "10", "20", "40", "60"])
    axes[1].set_xlabel("number of MLI layers $N$")
    axes[1].set_ylabel("heat flux at sea level [W/m$^2$]")
    fig.tight_layout()
    save(fig, "heat_leak.pdf")


def fig_parked(d):
    p = d["parked"]
    fig, axes = plt.subplots(1, 2, figsize=(6.3, 2.5))
    for key, color, label in (("sea_level", C1, "sea level (288 K)"),
                              ("altitude_8000", C2, "8000 m (236 K)")):
        t = np.array(p[key]["t"]) / 3600.0
        axes[0].plot(t, p[key]["P"], color=color, label=label)
        axes[1].plot(t, p[key]["m_vent_cum"], color=color, label=label)
    axes[0].set_xlabel("time [h]")
    axes[0].set_ylabel("pressure [bar]")
    axes[0].legend(loc="lower right")
    axes[1].set_xlabel("time [h]")
    axes[1].set_ylabel("cumulative vented H$_2$ [kg]")
    fig.tight_layout()
    save(fig, "parked.pdf")


def fig_replay(d):
    r = d["replay"]
    h = d["h2_t"]["history"]
    fig, axes = plt.subplots(1, 2, figsize=(6.3, 2.6))
    t_ref = np.array(h["t"]) / 60.0
    axes[0].plot(t_ref, h["P"], color=C1, label="reference ($P_{max}$ 1.6 bar, $N$ = 9)")
    axes[1].plot(t_ref, h["m_vent_cum"], color=C1)
    for key, color, label in (("pmax_2.0", C2, "$P_{max}$ = 2.0 bar"),
                              ("pmax_3.0", C3, "$P_{max}$ = 3.0 bar"),
                              ("mli_40", C4, "$N$ = 40 layers")):
        t = np.array(r[key]["t"]) / 60.0
        axes[0].plot(t, r[key]["P"], color=color, label=label)
        axes[1].plot(t, r[key]["m_vent_cum"], color=color)
    for ax in axes:
        mark_mission_end(ax, d)
        ax.set_xlabel("time from the start of the climb [min]")
    axes[0].set_ylabel("pressure [bar]")
    axes[1].set_ylabel("cumulative vented H$_2$ [kg]")
    axes[0].legend(loc="upper left", fontsize=6.8)
    fig.tight_layout()
    save(fig, "replay.pdf")


def main():
    with open(DATA) as f:
        d = json.load(f)
    os.makedirs(FIG, exist_ok=True)
    fig_mission_history(d)
    fig_capacity_sweep(d)
    fig_diameter_sweep(d)
    fig_heat_leak(d)
    fig_parked(d)
    fig_replay(d)


if __name__ == "__main__":
    main()
