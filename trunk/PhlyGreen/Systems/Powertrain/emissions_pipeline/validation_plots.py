"""Validation and behaviour plots for the PW127 emission surrogate.

Produces, in this folder:
  * `validation_vs_icao.png`  — surrogate EINOx/EICO at the LTO modes vs the FOCA/EASA PW127 ICAO
    data (the calibration targets);
  * `ei_vs_combustor_state.png` — emission indices vs the combustor inlet state (T3, P3, FAR),
    showing the physical trends the surrogate carries across the flight envelope.

Run:  python validation_plots.py   (needs the packaged surrogate + dataset; matplotlib)
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from PhlyGreen.Systems.Powertrain.emissions_surrogate import EmissionSurrogate

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "..", "data", "PW127_Emission_Map.csv")

# FOCA/EASA PW127G ICAO LTO targets (g/kg fuel); power fractions per turboprop LTO.
ICAO = {
    "To":   {"PC": 1.00, "NOx": 19.0, "CO": 2.0,  "soot": 0.30},
    "Cl":   {"PC": 0.90, "NOx": 16.0, "CO": 2.0,  "soot": 0.55},
    "App":  {"PC": 0.30, "NOx": 10.0, "CO": 4.0,  "soot": 0.25},
    "Taxi": {"PC": 0.07, "NOx": 5.0,  "CO": 20.0, "soot": 1.20},
}


def validation_vs_icao(es):
    """Surrogate EI at the LTO modes vs ICAO (NOx is anchored to it; CO is from the CRN)."""
    modes = list(ICAO)
    lo, hi = es._ranges["PC"]                          # surrogate power-fraction domain
    nox_m, co_m, nox_i, co_i, in_range = [], [], [], [], []
    for m in modes:
        pc = ICAO[m]["PC"]
        pc_c = min(max(pc, lo), hi)                    # clip Taxi (0.07) into the model range
        # SLS, averaged over the model Mach range (the anchor matched the SLS Mach-mean)
        eis = [es.predict_op(0.0, mm, pc_c) for mm in np.linspace(0.1, 0.55, 4)]
        nox_m.append(np.mean([e["EINOX"] for e in eis]))
        co_m.append(np.mean([e["EICO"] for e in eis]))
        nox_i.append(ICAO[m]["NOx"]); co_i.append(ICAO[m]["CO"])
        in_range.append(lo - 1e-6 <= pc <= hi + 1e-6)

    fig, (axN, axC) = plt.subplots(1, 2, figsize=(11, 4.4))
    x = np.arange(len(modes)); w = 0.38
    for ax, mod, ic, lab in ((axN, nox_m, nox_i, "EINOx"), (axC, co_m, co_i, "EICO")):
        ax.bar(x - w/2, ic, w, label="ICAO (FOCA/EASA)", color="tab:gray")
        ax.bar(x + w/2, mod, w, label="surrogate", color="tab:red")
        ax.set_xticks(x); ax.set_xticklabels(modes)
        ax.set_ylabel(f"{lab} [g/kg fuel]"); ax.grid(axis="y", alpha=0.3); ax.legend()
        for i, ir in enumerate(in_range):
            if not ir:
                ax.text(i, 0.02 * ax.get_ylim()[1], "out of\nmodel range", ha="center",
                        fontsize=7, color="tab:blue")
    axN.set_title("NOx: surrogate (certification-anchored) vs ICAO")
    axC.set_title("CO: surrogate (CRN) vs ICAO")
    fig.suptitle("PW127 emission surrogate — validation vs ICAO LTO data")
    fig.tight_layout()
    p = os.path.join(HERE, "validation_vs_icao.png")
    fig.savefig(p, dpi=120, bbox_inches="tight"); plt.close(fig); print("saved", p)


def ei_vs_combustor_state(df):
    """EI vs combustor inlet temperature T3, pressure P3 and fuel-air ratio FAR."""
    outs = [("EINOX", "EINOx"), ("EICO", "EICO"), ("EIUHC", "EIUHC")]
    cols = [("T3_K", "T3 [K]", 1.0), ("P3_Pa", "P3 [bar]", 1e-5), ("FAR", "FAR [-]", 1.0)]
    fig, axes = plt.subplots(len(outs), len(cols), figsize=(13, 9), sharey="row")
    for r, (oc, ol) in enumerate(outs):
        for c, (xc, xl, sc) in enumerate(cols):
            ax = axes[r, c]
            s = ax.scatter(df[xc] * sc, df[oc], c=df["PC"], cmap="viridis", s=14, alpha=0.7)
            if r == len(outs) - 1:
                ax.set_xlabel(xl)
            if c == 0:
                ax.set_ylabel(f"{ol} [g/kg]")
            ax.grid(alpha=0.3)
    fig.colorbar(s, ax=axes, label="power fraction PC", shrink=0.6, location="right")
    fig.suptitle("PW127 emission indices vs combustor inlet state (colour = power fraction)")
    p = os.path.join(HERE, "ei_vs_combustor_state.png")
    fig.savefig(p, dpi=120, bbox_inches="tight"); plt.close(fig); print("saved", p)


def main():
    es = EmissionSurrogate()
    df = pd.read_csv(DATA)
    validation_vs_icao(es)
    ei_vs_combustor_state(df)
    print("\nNote: NOx is certification-anchored (matches ICAO by construction at the in-range LTO "
          "modes); CO comes from the PW127-recalibrated CRN. Idle (Taxi, PC=0.07) is below the "
          "flight-envelope model range; soot is not yet modelled (see EMISSIONS_MODEL_NOTES.md).")


if __name__ == "__main__":
    main()
