"""Validation and behaviour plots for the packaged emission surrogates.

Produces, in this folder, per engine:
  * `validation_vs_icao*.png`  — surrogate EINOx/EICO at the LTO modes vs the ICAO certification
    data (the calibration targets);
  * `ei_vs_combustor_state*.png` — emission indices vs the combustor inlet state (T3, P3, FAR),
    showing the physical trends the surrogate carries across the flight envelope.

Two engines are supported and must not be confused: the **PW127** turboprop map, whose NOx is
certification-*anchored* and whose third coordinate is a shaft-power fraction, and the
**CFM56-class turbofan** map, whose NOx is unanchored (the CRN is native to that engine class)
and whose third coordinate is a *thrust* fraction.

Run:  python validation_plots.py [pw127|turbofan|all]   (needs the artifact + matplotlib)
"""
import os
import sys

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from PhlyGreen.Systems.Powertrain.emissions_surrogate import EmissionSurrogate

HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(HERE, "..", "data")

# FOCA/EASA PW127G ICAO LTO targets (g/kg fuel); power fractions per turboprop LTO.
ICAO_PW127 = {
    "To":   {"PC": 1.00, "NOx": 19.0, "CO": 2.0,  "soot": 0.30},
    "Cl":   {"PC": 0.90, "NOx": 16.0, "CO": 2.0,  "soot": 0.55},
    "App":  {"PC": 0.30, "NOx": 10.0, "CO": 4.0,  "soot": 0.25},
    "Taxi": {"PC": 0.07, "NOx": 5.0,  "CO": 20.0, "soot": 1.20},
}

# ICAO LTO targets for the CFM56-7B27E, the engine the CRN is calibrated to (transcribed in
# crn/evap_model_ottimizzato.py). Turbofan power codes are % of F00 thrust, not shaft power.
ICAO_TURBOFAN = {
    "To":   {"PC": 1.00, "NOx": 23.94, "CO": 0.31},
    "Cl":   {"PC": 0.85, "NOx": 17.89, "CO": 0.17},
    "App":  {"PC": 0.30, "NOx": 9.09,  "CO": 2.82},
    "Taxi": {"PC": 0.07, "NOx": 4.36,  "CO": 29.39},
}

ENGINES = {
    "pw127": dict(icao=ICAO_PW127, data="PW127_Emission_Map.csv",
                  pkl="Emission_Model_PW127.pkl", mach=(0.10, 0.55), suffix="",
                  label="PW127", nox_note="certification-anchored"),
    "turbofan": dict(icao=ICAO_TURBOFAN, data="Turbofan_Emission_Map.csv",
                     pkl="Emission_Model_Turbofan.pkl", mach=(0.20, 0.85), suffix="_turbofan",
                     label="CFM56-class turbofan", nox_note="unanchored (CRN prediction)"),
}

# Module-level default, kept so the original PW127 behaviour is unchanged when this file is
# imported rather than run.
ICAO = ICAO_PW127
DATA = os.path.join(_DATA_DIR, "PW127_Emission_Map.csv")


def validation_vs_icao(es, eng=None):
    """Surrogate EI at the LTO modes vs ICAO (NOx is anchored to it; CO is from the CRN)."""
    eng = eng or ENGINES["pw127"]
    icao, (m_lo, m_hi) = eng["icao"], eng["mach"]
    modes = list(icao)
    lo, hi = es._ranges["PC"]                          # surrogate load-fraction domain
    nox_m, co_m, nox_i, co_i, in_range = [], [], [], [], []
    for m in modes:
        pc = icao[m]["PC"]
        pc_c = min(max(pc, lo), hi)                    # clip Taxi (0.07) into the model range
        # SLS, averaged over the model Mach range (the anchor matched the SLS Mach-mean)
        eis = [es.predict_op(0.0, mm, pc_c) for mm in np.linspace(m_lo, m_hi, 4)]
        nox_m.append(np.mean([e["EINOX"] for e in eis]))
        co_m.append(np.mean([e["EICO"] for e in eis]))
        nox_i.append(icao[m]["NOx"]); co_i.append(icao[m]["CO"])
        in_range.append(lo - 1e-6 <= pc <= hi + 1e-6)

    fig, (axN, axC) = plt.subplots(1, 2, figsize=(11, 4.4))
    x = np.arange(len(modes)); w = 0.38
    for ax, mod, ic, lab in ((axN, nox_m, nox_i, "EINOx"), (axC, co_m, co_i, "EICO")):
        ax.bar(x - w/2, ic, w, label="ICAO", color="tab:gray")
        ax.bar(x + w/2, mod, w, label="surrogate", color="tab:red")
        ax.set_xticks(x); ax.set_xticklabels(modes)
        ax.set_ylabel(f"{lab} [g/kg fuel]"); ax.grid(axis="y", alpha=0.3); ax.legend()
        for i, ir in enumerate(in_range):
            if not ir:
                ax.text(i, 0.02 * ax.get_ylim()[1], "out of\nmodel range", ha="center",
                        fontsize=7, color="tab:blue")
    axN.set_title(f"NOx: surrogate ({eng['nox_note']}) vs ICAO")
    axC.set_title("CO: surrogate (CRN) vs ICAO")
    fig.suptitle(f"{eng['label']} emission surrogate — validation vs ICAO LTO data")
    fig.tight_layout()
    p = os.path.join(HERE, f"validation_vs_icao{eng['suffix']}.png")
    fig.savefig(p, dpi=120, bbox_inches="tight"); plt.close(fig); print("saved", p)


def ei_vs_combustor_state(df, eng=None):
    """EI vs combustor inlet temperature T3, pressure P3 and fuel-air ratio FAR."""
    eng = eng or ENGINES["pw127"]
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
    frac = "thrust fraction" if eng["suffix"] else "power fraction"
    fig.colorbar(s, ax=axes, label=frac, shrink=0.6, location="right")
    fig.suptitle(f"{eng['label']} emission indices vs combustor inlet state (colour = {frac})")
    p = os.path.join(HERE, f"ei_vs_combustor_state{eng['suffix']}.png")
    fig.savefig(p, dpi=120, bbox_inches="tight"); plt.close(fig); print("saved", p)


def run(which="pw127"):
    eng = ENGINES[which]
    pkl = os.path.join(_DATA_DIR, eng["pkl"])
    csv = os.path.join(_DATA_DIR, eng["data"])
    if not (os.path.isfile(pkl) and os.path.isfile(csv)):
        print(f"skipping {which}: artifact not built ({eng['pkl']})")
        return
    print(f"--- {eng['label']} ---")
    validation_vs_icao(EmissionSurrogate(pkl), eng)
    ei_vs_combustor_state(pd.read_csv(csv), eng)


def main(which=None):
    which = which or (sys.argv[1] if len(sys.argv) > 1 else "all")
    for name in (list(ENGINES) if which == "all" else [which]):
        run(name)
    print("\nNote: the PW127 NOx is certification-anchored (it matches ICAO by construction at "
          "the in-range LTO modes); the turbofan NOx is NOT anchored -- the CRN is native to that "
          "engine class, so its NOx is a prediction and the gap to ICAO is a real error. CO comes "
          "from the CRN in both cases. Idle (Taxi) is below the modelled load-fraction range for "
          "both; soot is not yet modelled (see EMISSIONS_MODEL_NOTES.md).")


if __name__ == "__main__":
    main()
