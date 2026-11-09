"""Draw every figure of the engine-deck manual.

Reads ../data/engine_decks_data.json (compute_data.py, which folds in the summary of
../data/gt_deck_check.json from check_gt_deck.py) and ../data/crn_check.json (check_crn.py),
and writes vector PDFs to
../figures/. With --recompute it first runs compute_data.py; the two check scripts need pyCycle
and Cantera and are run separately (see the manual, Section "Reproducing the figures").

    cd trunk
    python ../manuals/engine-decks/scripts/make_figures.py              # reuse the JSON files
    python ../manuals/engine-decks/scripts/make_figures.py --recompute  # re-run compute_data.py
"""

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402
import numpy as np                                  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data")
FIG = os.path.join(HERE, "..", "figures")
sys.path.insert(0, HERE)

# Categorical order (blue, orange, aqua, yellow, magenta) and neutral inks, as in the TMS manual.
C1, C2, C3, C4, C5 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"
CATS = [C1, C2, C3, C4, C5]
INK, INK2, GRID, MUTED = "#0b0b0b", "#52514e", "#e4e3df", "#a8a7a2"

plt.rcParams.update({
    "font.family": "serif", "font.size": 8.5, "axes.labelsize": 8.5,
    "axes.titlesize": 8.5, "legend.fontsize": 7.2, "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5, "axes.edgecolor": INK2, "axes.labelcolor": INK,
    "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.axisbelow": True, "axes.spines.top": False,
    "axes.spines.right": False, "lines.linewidth": 1.4, "legend.frameon": False,
    "pdf.fonttype": 42, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
})


def load(name):
    with open(os.path.join(DATA, name)) as f:
        return json.load(f)


def save(fig, name):
    path = os.path.join(FIG, name)
    fig.savefig(path)
    plt.close(fig)
    print("  ", os.path.normpath(path))


# =============================================================================================
# Gas turbine
# =============================================================================================
def fig_gt_map(d):
    g = d["gas_turbine"]
    pc = np.array(g["maps"]["pc"])
    mp = g["map_points"]
    fig, axes = plt.subplots(1, 4, figsize=(6.6, 2.3), sharey=True)
    alts = [0.0, 10000.0, 20000.0, 30000.0]
    for ax, mach in zip(axes, [0.01, 0.2, 0.4, 0.6]):
        for k, alt in enumerate(alts):
            ax.plot(pc, g["maps"]["eta"][f"{alt:.0f}_{mach:.2f}"], color=CATS[k], lw=1.1,
                    label=f"{alt/1000:.0f} kft")
            sel = [(p, e) for a, m, p, e in zip(mp["Altitude_ft"], mp["Mach"], mp["Power"],
                                                mp["Efficiency"])
                   if abs(m - mach) < 1e-9 and a == alt]
            ax.plot([p for p, _ in sel], [e for _, e in sel], "o", ms=2.8, mfc=CATS[k],
                    mec=CATS[k])
        ax.axvspan(0.0, 0.3, color="#f3f2ef", lw=0, zorder=0)
        ax.set_title(f"Mach {mach:.2f}" if mach < 0.1 else f"Mach {mach:.1f}")
        ax.set_xlabel("power fraction [-]")
        ax.set_xlim(0.0, 1.02)
    axes[0].set_ylabel(r"thermal efficiency $\eta_{GT}$ [-]")
    axes[0].set_ylim(0.0, 0.45)
    axes[2].legend(loc="lower right", fontsize=6.3, handlelength=1.2)
    axes[3].plot([], [], "o", ms=2.8, color=INK2, label="map point")
    axes[3].legend(loc="lower right", fontsize=6.0, handlelength=1.0)
    save(fig, "gt_map.pdf")


def fig_gt_scaling(d):
    g = d["gas_turbine"]
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(6.6, 2.3))
    s = g["scaling_data"]
    a1.plot(s["shp"], s["eta_real"], "o", ms=3.5, color=C1, label="embedded SFC data")
    hp = np.geomspace(300, 8000, 60)
    i_ref = 6
    eta_ref = s["eta_real"][i_ref]
    n = g["scaling_n_calibrated"]
    a1.plot(hp, 1 - (1 - eta_ref) * (2500 / hp) ** n, color=C2, label=f"fit, $n$ = {n:.4f}")
    a1.set_xscale("log")
    a1.set_xlabel("rated power [shp]")
    a1.set_ylabel(r"$\eta$ from SFC [-]")
    a1.legend(loc="upper left")
    a1.set_title("(a) size-scaling calibration")

    sc = g["size_scaling"]
    a2.plot(sc["design_hp"], sc["eta"], color=C1)
    a2.axvline(g["ref_hp"], color=MUTED, lw=0.8, ls="--")
    a2.set_xscale("log")
    a2.set_xlabel("design power per engine [hp]")
    a2.set_ylabel(r"$\eta_{GT}$ [-]")
    a2.set_title("(b) 20 kft, M 0.4, 70 % power")

    la = g["lapse"]
    alt_km = np.array(la["alt_m"]) / 1000
    a3.plot(alt_km, la["delta"], color=C1, label=r"map, Class II: $p/p_0$")
    a3.plot(alt_km, la["rho075"], color=C2, label=r"Class I: $(\rho/\rho_0)^{0.75}$")
    a3.set_xlabel("altitude [km]")
    a3.set_ylabel("available / rated power [-]")
    a3.legend(loc="lower left", fontsize=6.3)
    a3.set_title("(c) power lapse")
    fig.tight_layout(w_pad=1.0)
    save(fig, "gt_scaling.pdf")


def fig_gt_mission(d):
    ds = d["designs"]
    w = ds["tp_c2_walk"]
    wc = ds["tp_walk"]
    t = np.array(w["t"]) / 60
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.6, 2.3))
    nominal = ds["tp_c2_Surrogate"]["gt_design_power"]
    a1.plot(t, np.array(w["P_shaft"]) / nominal, color=C1, lw=1.0, label="shaft / nominal")
    import PhlyGreen.Utilities.Units as Units
    from PhlyGreen.Systems.Powertrain.gas_turbine_surrogate import _isa_pressure_ratio
    delta = np.array([_isa_pressure_ratio(Units.mToft(a)) for a in w["alt"]])
    a1.plot(t, np.array(w["P_shaft"]) / (nominal * delta), color=C2, lw=1.0,
            label=r"shaft / available ($\delta$)")
    a1.axhspan(0, 0.3, color="#f3f2ef", lw=0, zorder=0)
    a1.set_xlabel("mission time [min]")
    a1.set_ylabel("load fraction [-]")
    a1.set_ylim(0, 1.1)
    a1.legend(loc="upper right")
    a1.set_title("(a) gas-turbine load")
    a2.plot(t, w["eta_gt"], color=C1, lw=1.0, label="Class II (response surface)")
    a2.plot(np.array(wc["t"]) / 60, wc["eta_gt"], color=MUTED, lw=1.0, ls="--",
            label="Class I (constant 0.22)")
    a2.set_xlabel("mission time [min]")
    a2.set_ylabel(r"$\eta_{GT}$ [-]")
    a2.set_ylim(0.0, 0.45)
    a2.legend(loc="lower right")
    a2.set_title("(b) gas-turbine efficiency")
    fig.tight_layout(w_pad=1.2)
    save(fig, "gt_mission.pdf")


# =============================================================================================
# Turbofan
# =============================================================================================
def fig_tf_maps(d):
    tf = d["turbofan"]
    fr = tf["maps"]["fraction"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.6, 2.5))
    labels = {"SL_M0.25": "SL, M 0.25", "10kft_M0.45": "10 kft, M 0.45",
              "20kft_M0.60": "20 kft, M 0.60", "30kft_M0.75": "30 kft, M 0.75",
              "35kft_M0.78": "35 kft, M 0.78"}
    for k, (key, lab) in enumerate(labels.items()):
        a1.plot(fr, tf["maps"]["eta"][key], color=CATS[k], label=lab)
        a2.plot(fr, tf["maps"]["tsfc_imperial"][key], color=CATS[k], label=lab)
    a1.set_xlabel("thrust fraction $F/F_{avail}$ [-]")
    a1.set_ylabel(r"overall efficiency $\eta_o$ [-]")
    a1.set_title(r"(a) $\eta_o$")
    a1.legend(loc="lower right", fontsize=6.5)
    a2.set_xlabel("thrust fraction $F/F_{avail}$ [-]")
    a2.set_ylabel("TSFC [lb/(lbf h)]")
    a2.set_title("(b) TSFC")
    fig.tight_layout(w_pad=1.2)
    save(fig, "tf_maps.pdf")


def fig_tf_lapse(d):
    tf = d["turbofan"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.6, 2.5), gridspec_kw={"width_ratios": [1, 1.5]})
    for m, alts in tf["envelope"].items():
        a1.plot([float(m)] * len(alts), np.array(alts) / 1000, "o", ms=3.2, color=C1)
    a1.set_xlabel("Mach [-]")
    a1.set_ylabel("altitude [kft]")
    a1.set_xlim(0.1, 0.9)
    a1.set_ylim(-2, 38)
    a1.set_title("(a) converged flight conditions")
    lc = tf["lapse_curves"]
    for k, a in enumerate(["0", "10000", "20000", "30000", "35000"]):
        # solid where the deck has points at this altitude, faint outside (clipped/extrapolated)
        sampled = [m for alt, m in zip(tf["lapse_training"]["alt_ft"], tf["lapse_training"]["Mach"])
                   if alt == float(a)]
        mach = np.array(lc["mach"])
        val = np.array(lc["map"][a])
        inside = (mach >= min(sampled) - 1e-9) & (mach <= max(sampled) + 1e-9)
        a2.plot(mach, val, color=CATS[k], lw=0.8, alpha=0.35)
        a2.plot(mach[inside], val[inside], color=CATS[k], label=f"{float(a)/1000:.0f} kft")
        a2.plot(lc["mach"], lc["mattingly"][a], color=CATS[k], ls=":", lw=1.0)
    lt = tf["lapse_training"]
    for alt, m, lp in zip(lt["alt_ft"], lt["Mach"], lt["lapse"]):
        k = [0, 10000, 20000, 30000, 35000].index(alt) if alt in (0, 10000, 20000, 30000, 35000) else None
        if k is not None:
            a2.plot(m, lp, "o", ms=2.8, color=CATS[k])
    a2.plot([], [], color=INK2, label="map (RBF)")
    a2.plot([], [], color=INK2, ls=":", lw=1.0, label="Mattingly fallback")
    a2.plot([], [], "o", ms=2.8, color=INK2, label="deck points")
    a2.set_xlabel("Mach [-]")
    a2.set_ylabel(r"thrust lapse $F_{max}/F_{00}$ [-]")
    a2.set_title("(b) thrust lapse")
    a2.legend(loc="upper right", fontsize=6.3, ncol=2)
    fig.tight_layout(w_pad=1.2)
    save(fig, "tf_lapse.pdf")


# =============================================================================================
# Propeller
# =============================================================================================
def fig_propeller(d):
    p = d["propeller"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.6, 2.5))
    h = p["hamilton"]
    k = 0
    for alt, ls in (("0", "-"), ("6000", "--")):
        for j, pw in enumerate(("1", "2", "4")):
            eta = np.array(h["eta"][f"{alt}_{pw}"], float)
            a1.plot(h["J"], eta, color=CATS[j], ls=ls, lw=1.1,
                    label=f"{pw} MW" if alt == "0" else None)
    a1.plot([], [], color=INK2, ls="-", label="sea level")
    a1.plot([], [], color=INK2, ls="--", label="6000 m")
    a1.set_xlabel("advance ratio $J$ [-]")
    a1.set_ylabel(r"$\eta_P$ [-]")
    a1.set_ylim(0, 1)
    a1.set_title("(a) Hamilton Standard")
    a1.legend(loc="lower right", fontsize=6.5, ncol=2)
    c = p["surrogate_chain"]
    s = p["csv_slice"]
    for j, rpm in enumerate(("1000", "1200")):
        a2.plot(c["V"], c["eta"][rpm], color=CATS[j], lw=1.1, label=f"governor + map, {rpm} rpm")
    a2.plot(s["V"], s["eta"], "o", ms=3.2, color=INK2, label="CSV rows")
    a2.plot(s["V"], s["eta_fit"], "x", ms=3.6, color=C3, mew=1.0, label="map at the rows' pitch, rpm")
    a2.set_xlabel("true airspeed [m/s]")
    a2.set_ylabel(r"$\eta_P$ [-]")
    a2.set_ylim(0, 1)
    a2.set_title(f"(b) RBF surrogate, {s['alt_m']:.0f} m, {s['power_kw']:.0f} kW")
    a2.legend(loc="lower right", fontsize=6.0)
    fig.tight_layout(w_pad=1.2)
    save(fig, "propeller.pdf")


# =============================================================================================
# Emissions
# =============================================================================================
def fig_em_maps(d, name, fname, cert):
    e = d["emissions"][name]
    pc = e["maps"]["pc"]
    fig, axes = plt.subplots(1, 3, figsize=(6.6, 2.4))
    for k, (alt, vals) in enumerate(e["maps"]["by_alt"].items()):
        lab = f"{float(alt)/1000:.0f} kft"
        axes[0].plot(pc, vals["EINOX"], color=CATS[k], label=lab)
        axes[1].plot(pc, vals["EICO"], color=CATS[k])
        axes[2].plot(pc, vals["EIUHC"], color=CATS[k])
    # sea-level training rows (all Mach values)
    sl = e["sl_rows"]
    for ax, sp in zip(axes, ("EINOX", "EICO", "EIUHC")):
        ax.plot(sl["PC"], sl[sp], ".", ms=3, color=MUTED, zorder=1)
    # certification points
    for ax, sp in zip(axes, ("NOx", "CO", "UHC")):
        x = [p for p, v in zip(cert["pc"], cert[sp]) if v and v > 0]
        y = [v for v in cert[sp] if v and v > 0]
        if x:
            ax.plot(x, y, "D", ms=4, mfc="white", mec=INK, mew=1.0, zorder=5)
    axes[0].set_ylabel(r"EI$_{NO_x}$ [g/kg]")
    axes[1].set_ylabel(r"EI$_{CO}$ [g/kg]")
    axes[2].set_ylabel(r"EI$_{UHC}$ [g/kg]")
    axes[1].set_yscale("log")
    axes[2].set_yscale("log")
    for ax in axes:
        ax.set_xlabel(cert["xlabel"])
        ax.set_xlim(0.0, 1.03)
    axes[0].plot([], [], ".", ms=3, color=MUTED, label="sea-level data (all Mach)")
    axes[0].plot([], [], "D", ms=4, mfc="white", mec=INK, label=cert["label"])
    handles, labels = axes[0].get_legend_handles_labels()
    fig.suptitle(f"{cert['title']} (lines: Mach {e['maps']['Mach']:.1f})", fontsize=8.5, y=1.02)
    fig.tight_layout(w_pad=1.0, rect=(0, 0.08, 1, 1))
    fig.legend(handles, labels, loc="lower center", ncol=len(labels), fontsize=6.5,
               handlelength=1.4, columnspacing=1.0)
    save(fig, fname)


def fig_em_crn(crn):
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(6.6, 2.4))
    modes = ["ID", "AP", "CL", "TO"]
    pcs = [crn["cfm56_native"][m]["state"]["power"] / 100 for m in modes]
    for ax, sp, log in ((a1, "NOx", False), (a2, "CO", True)):
        ax.plot(pcs, [crn["cfm56_native"][m][sp] for m in modes], "o-", color=C1, ms=3.5,
                label="CRN (native)")
        ax.plot(pcs, [crn["cfm56_native"][m]["ICAO"][sp] for m in modes], "D--", color=INK,
                ms=3.5, mfc="white", lw=0.9, label="ICAO (in CRN file)")
        ax.set_xlabel("thrust fraction [-]")
        if log:
            ax.set_yscale("log")
    a1.set_ylabel(r"EI$_{NO_x}$ [g/kg]")
    a2.set_ylabel(r"EI$_{CO}$ [g/kg]")
    a1.set_title("(a) CFM56 LTO states: NOx")
    a2.set_title("(b) CFM56 LTO states: CO")
    a1.legend(loc="upper left", fontsize=6.3)
    pw = crn["pw127_sls"]
    machs = sorted(set(p["Mach"] for p in pw))
    for k, m in enumerate(machs):
        sel = sorted([p for p in pw if p["Mach"] == m], key=lambda p: p["PC"])
        a3.plot([p["PC"] for p in sel], [p["NOx"] for p in sel], "-", color=CATS[k], lw=1.0,
                label=f"M {m:.2f}")
        a3.plot([p["PC"] for p in sel], [p["shipped_EINOX"] for p in sel], "--", color=CATS[k],
                lw=1.0)
    a3.plot([0.30, 0.90, 1.00], [10.0, 16.0, 19.0], "D", ms=4, mfc="white", mec=INK, mew=1.0)
    a3.plot([], [], color=INK2, label="raw CRN")
    a3.plot([], [], color=INK2, ls="--", label="anchored (shipped)")
    a3.plot([], [], "D", ms=4, mfc="white", mec=INK, label="PW127G cert.")
    a3.set_xlabel("power fraction [-]")
    a3.set_ylabel(r"EI$_{NO_x}$ [g/kg]")
    a3.set_title("(c) PW127 sea level: anchoring")
    handles, labels = a3.get_legend_handles_labels()
    fig.tight_layout(w_pad=0.8, rect=(0, 0.08, 1, 1))
    fig.legend(handles, labels, loc="lower right", ncol=len(labels), fontsize=6.3,
               handlelength=1.4, columnspacing=0.9, bbox_to_anchor=(1.0, 0.0))
    save(fig, "em_crn.pdf")


def fig_em_filippone(d):
    f = d["emissions"]["filippone"]
    fig, ax = plt.subplots(figsize=(3.6, 2.4))
    for k, phase in enumerate(("climb", "cruise", "descent")):
        ax.plot(f["mfuel"], f["curves"][f"{phase}_15.77"], color=CATS[k], label=f"{phase}, OPR 15.77")
        ax.plot(f["mfuel"], f["curves"][f"{phase}_30.0"], color=CATS[k], ls="--",
                label=f"{phase}, OPR 30")
    ax.set_xlabel("fuel flow per engine [kg/s]")
    ax.set_ylabel(r"EI$_{NO_x}$ [g/kg]")
    ax.legend(loc="upper left", fontsize=5.8, ncol=2)
    save(fig, "em_filippone.pdf")


def fig_em_mission(d):
    ds = d["designs"]
    cases = (("tp_walk", "tp_ei", "tp_filippone", "TP, constant $\\eta_{GT}$"),
             ("tp_c2_walk", "tp_c2_ei", "tp_c2_filippone", "TP, Class-II GT"),
             ("tf_walk", "tf_ei", "tf_filippone", "TF"))
    fig, axes = plt.subplots(2, 3, figsize=(6.6, 4.2), sharex="col")
    for col, (walk_key, ei_key, fil_key, title) in enumerate(cases):
        w, ei, fil = ds[walk_key], ds[ei_key], ds[fil_key]
        t = np.array(w["t"]) / 60
        a = axes[0, col]
        a.plot(t, fil["EINOX"], color=MUTED, lw=1.0, label="Filippone")
        a.plot(t, ei["EI"]["EINOX"], color=C1, lw=1.0, label="surrogate")
        a.set_title(f"({'abc'[col]}) {title}")
        a.set_ylim(0, 40)
        a = axes[1, col]
        a.plot(t, ei["fraction"], color=C1, lw=1.0)
        a.axhspan(0, 0.3, color="#f3f2ef", lw=0, zorder=0)
        a.axhline(1.0, color=INK2, lw=0.7, ls=":")
        a.set_ylim(0, 1.85)
        a.set_xlabel("mission time [min]")
        a.set_title(f"({'def'[col]}) load fraction")
    axes[0, 0].set_ylabel(r"EI$_{NO_x}$ [g/kg]")
    axes[1, 0].set_ylabel("map coordinate PC [-]")
    axes[0, 2].legend(loc="upper right", fontsize=6.0)
    fig.tight_layout(h_pad=1.0, w_pad=0.8)
    save(fig, "em_mission.pdf")


def main():
    if "--recompute" in sys.argv:
        import compute_data
        compute_data.main()
    d = load("engine_decks_data.json")
    crn = load("crn_check.json")
    fig_gt_map(d)
    fig_gt_scaling(d)
    fig_gt_mission(d)
    fig_tf_maps(d)
    fig_tf_lapse(d)
    fig_propeller(d)
    cert_pw = {"pc": [0.30, 0.90, 1.00], "NOx": [10.0, 16.0, 19.0], "CO": [4.0, 2.0, 2.0],
               "UHC": [0, 0, 0], "xlabel": "power fraction [-]", "label": "PW127G cert.",
               "title": "PW127 artifact"}
    fig_em_maps(d, "PW127", "em_maps_pw127.pdf", cert_pw)
    cert_tf = {"pc": [0.30, 0.85, 1.00], "NOx": [9.09, 17.89, 23.94], "CO": [2.82, 0.17, 0.31],
               "UHC": [0.05, 0.02, 0.03], "xlabel": "thrust fraction [-]",
               "label": "ICAO CFM56-7B27E", "title": "Turbofan artifact"}
    fig_em_maps(d, "Turbofan", "em_maps_tf.pdf", cert_tf)
    fig_em_crn(crn)
    fig_em_filippone(d)
    fig_em_mission(d)


if __name__ == "__main__":
    main()
