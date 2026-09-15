"""Build the turbofan (CFM56-class) emission-index dataset and surrogate.

The counterpart of :mod:`build_pw127_surrogate`, and a much shorter story, because the Cantera
CRN in ``crn/evap_model_ottimizzato.py`` is **natively a CFM56-7B27E model** -- its docstring,
its air splits (ARPZ = 0.3082) and its ICAO reference EIs are all CFM56. The PW127 build
monkey-patches that calibration at import; a turbofan build simply does not.

Three PW127-specific things are therefore *removed* rather than replaced:

1. the ARPZ renormalisation to 0.24 (a richer primary zone, fitted to the turboprop);
2. the ``max(chi, 1.20)`` floor on the mixer scale. ``chi`` falls 1.50 -> 1.00 as T3 rises
   477 -> 795 K, so a floor of 1.20 clamps everything above T3 ~ 640 K. The PW127 box topped out
   at 662 K so the floor barely bit; our box runs to 796 K, where it would silently discard the
   CRN's own climb (1.07) and take-off (1.00) values -- i.e. we would not be running the CFM56
   calibration we think we are;
3. the flat ``dPqP = 0.95``; we use the HBTF deck's own burner pressure loss instead.

NOx is **not** certification-anchored here. The PW127 anchor existed because an equal-split CRN
cannot reproduce a staged turboprop combustor; this CRN is native to the engine class it is being
asked about, so its raw NOx is reported and compared against ICAO. If that comparison is poor,
anchor it deliberately and say so -- do not anchor by default.

Reads  ../data/Turbofan_Universal_Map.csv   (written by ../data/HBTF_turbofan.py)
Writes ../data/Turbofan_Emission_Map.csv and ../data/Emission_Model_Turbofan.pkl

Run (needs cantera):
    cd PhlyGreen/Systems/Powertrain/emissions_pipeline && python build_turbofan_surrogate.py
"""
import os, sys, io, contextlib
import multiprocessing as mp

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CRN_DIR = os.path.join(HERE, "crn")

# Burner pressure loss of the vendored HBTF deck (`burner.dPqP = 0.0540`), i.e. p_out/p_in.
DPQP_HBTF = 1.0 - 0.0540

# ICAO LTO reference for the CFM56-7B27E, transcribed in the CRN itself
# (crn/evap_model_ottimizzato.py:706-707 and MODE_DATA). Power codes are % of F00.
ICAO_CFM56 = {
    "Idle":     {"PC": 0.07, "NOx": 4.36,  "CO": 29.39, "UHC": 1.54},
    "Approach": {"PC": 0.30, "NOx": 9.09,  "CO": 2.82,  "UHC": 0.05},
    "Climb":    {"PC": 0.85, "NOx": 17.89, "CO": 0.17,  "UHC": 0.02},
    "TakeOff":  {"PC": 1.00, "NOx": 23.94, "CO": 0.31,  "UHC": 0.03},
}


def _init():
    """Import the CRN with its native CFM56 calibration untouched."""
    os.chdir(CRN_DIR)
    sys.path.insert(0, CRN_DIR)
    global evap
    import evap_model_ottimizzato as evap
    # deliberately no ARPZ/ARSZ/ARDZ patching -- see the module docstring


def _chi_from_T3(T3):
    """Mixer scale interpolated against the CRN's own four LTO inlet temperatures.

    No floor: the floor in the PW127 build is a turboprop artefact (see docstring).
    """
    order = ["ID", "AP", "CL", "TO"]
    Tm = np.array([evap.MODE_DATA[k]["T_in"] for k in order])
    chm = np.array([evap.MODE_DATA[k]["chi_mixer_scale"] for k in order])
    return float(np.interp(np.clip(T3, Tm[0], Tm[-1]), Tm, chm))


def _run_point(row):
    T3, P3, FAR, mdot = row
    params = {"label": "TURBOFAN", "power": 0.0, "T_in": T3, "p_in_bar": P3 / 1e5,
              "mdot_air": mdot, "FAR": FAR, "dPqP": DPQP_HBTF,
              "chi_mixer_scale": _chi_from_T3(T3), "EIUHC_ICAO": 0.0}
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            r = evap.run_crn_evap_mode("GRID", params)
        return (float(r.get("EI_NOx", np.nan)), float(r.get("EI_CO", np.nan)),
                float(r.get("EI_UHC_total", np.nan)))
    except Exception:
        return (np.nan, np.nan, np.nan)


def _load_map():
    """Read the engine map and rename its columns to what the fitter expects.

    ``train_emission_surrogate`` keys on exactly ``alt_ft, Mach, PC``; with those names it needs
    no modification at all. ``PC`` here is a **thrust** fraction, not a shaft-power fraction --
    the semantic change that matters for a turbofan.
    """
    src = os.path.abspath(os.path.join(HERE, "..", "data", "Turbofan_Universal_Map.csv"))
    df = pd.read_csv(src)
    df = df.rename(columns={"Altitude_ft": "alt_ft", "ThrustFraction": "PC",
                            "mdot_air3": "mdot_air3_kg_s"})
    return df, src


def main(anchor_nox=False):
    df, src = _load_map()
    rows = df[["T3_K", "P3_Pa", "FAR", "mdot_air3_kg_s"]].to_numpy(float)
    print(f"Read {len(rows)} operating points from {os.path.basename(src)}")
    print(f"  T3  {df.T3_K.min():.0f} - {df.T3_K.max():.0f} K      "
          f"(CRN calibration box 477 - 795 K)")
    print(f"  FAR {df.FAR.min():.4f} - {df.FAR.max():.4f}   (CRN calibration box 0.014 - 0.026)")
    print(f"\nRunning the CFM56-native CRN (ARPZ 0.3082, no anchor) over {len(rows)} points ...")

    with mp.Pool(processes=min(6, mp.cpu_count()), initializer=_init) as pool:
        out = pool.map(_run_point, rows)
    out = np.array(out)
    df["EINOX_crn"], df["EICO"], df["EIUHC"] = out[:, 0], out[:, 1], out[:, 2]
    good = df.dropna(subset=["EINOX_crn", "EICO", "EIUHC"]).copy()
    print(f"  {len(good)}/{len(df)} CRN points converged")

    good["EINOX"] = good["EINOX_crn"]
    if anchor_nox:
        from scipy.interpolate import PchipInterpolator
        pf = np.array([ICAO_CFM56[m]["PC"] for m in ("Approach", "Climb", "TakeOff")])
        nx = np.array([ICAO_CFM56[m]["NOx"] for m in ("Approach", "Climb", "TakeOff")])
        sls = good[good["alt_ft"] < 1.0]
        pf_sls = np.sort(sls["PC"].unique())
        crn_sls = np.array([sls[np.isclose(sls["PC"], p)]["EINOX_crn"].mean() for p in pf_sls])
        crn_i, cert_i = PchipInterpolator(pf_sls, crn_sls), PchipInterpolator(pf, nx)
        def k(p):
            p = float(np.clip(p, pf[0], pf[-1]))
            return float(cert_i(p)) / max(float(crn_i(np.clip(p, pf_sls[0], pf_sls[-1]))), 1e-6)
        good["EINOX"] = [r.EINOX_crn * k(r.PC) for r in good.itertuples()]
        print("\n*** NOx CERTIFICATION-ANCHORED: the level is asserted from ICAO, not predicted.")

    # --- how the raw CRN compares with ICAO, at the sea-level slice ---
    report_vs_icao(good)

    out_csv = os.path.abspath(os.path.join(HERE, "..", "data", "Turbofan_Emission_Map.csv"))
    good[["Mach", "alt_ft", "PC", "T3_K", "P3_Pa", "FAR", "mdot_air3_kg_s",
          "EINOX", "EICO", "EIUHC"]].to_csv(out_csv, index=False)
    print(f"\nsaved turbofan EI dataset -> {out_csv}")

    sys.path.insert(0, os.path.join(HERE, ".."))
    import train_emission_surrogate as T
    pkl = os.path.abspath(os.path.join(HERE, "..", "data", "Emission_Model_Turbofan.pkl"))
    print("\n--- fitting the packaged turbofan surrogate ---")
    T.main(csv=out_csv, pkl=pkl, tag="CFM56-class HBTF")
    return out_csv, pkl


def report_vs_icao(good):
    """Compare the sea-level CRN output with the CFM56 ICAO LTO certification values.

    The map has no true static row (the deck does not converge there), so the sea-level slice
    spans the grid's Mach values; it is Mach-averaged here and the same window must be used by
    any plot that repeats this comparison.
    """
    sls = good[good["alt_ft"] < 1.0]
    if sls.empty:
        print("\n(no sea-level slice to compare against ICAO)")
        return
    print(f"\nCRN vs ICAO CFM56-7B27E at sea level "
          f"(Mach {sls.Mach.min():.2f}-{sls.Mach.max():.2f}, averaged):")
    print(f"  {'mode':<10}{'PC':>6}{'NOx CRN':>9}{'ICAO':>7}{'err':>7}"
          f"{'CO CRN':>9}{'ICAO':>7}{'d(abs)':>9}")
    nox_err = []
    for mode, ref in ICAO_CFM56.items():
        pc = ref["PC"]
        near = sls.iloc[(sls["PC"] - pc).abs().argsort()[:4]]   # nearest thrust fraction
        if abs(float(near["PC"].iloc[0]) - pc) > 0.12:
            print(f"  {mode:<10}{pc:>6.2f}   (outside the mapped thrust-fraction range)")
            continue
        nox, co = float(near["EINOX"].mean()), float(near["EICO"].mean())
        e_n = 100 * (nox - ref["NOx"]) / ref["NOx"]
        nox_err.append(e_n)
        print(f"  {mode:<10}{pc:>6.2f}{nox:>9.2f}{ref['NOx']:>7.2f}{e_n:>6.0f}%"
              f"{co:>9.2f}{ref['CO']:>7.2f}{co - ref['CO']:>+9.2f}")
    if nox_err:
        print(f"\n  rms relative error, NOx: {np.sqrt(np.mean(np.square(nox_err))):.0f}%"
              f"   (unanchored -- this is a prediction, not a fitted level)")
    print("  CO is reported as an ABSOLUTE difference [g/kg] on purpose: at climb and take-off\n"
          "  the certified CO is 0.17-0.31 g/kg, so a relative error there is a large number\n"
          "  attached to a negligible mass. The CO that matters is the low-power end, where the\n"
          "  index is one to two orders of magnitude larger.")


def report_only():
    """Re-print the ICAO comparison from the saved dataset, without re-running the CRN."""
    import pandas as pd
    csv = os.path.abspath(os.path.join(HERE, "..", "data", "Turbofan_Emission_Map.csv"))
    report_vs_icao(pd.read_csv(csv))


if __name__ == "__main__":
    if "--report-only" in sys.argv:
        report_only()
    else:
        main(anchor_nox="--anchor-nox" in sys.argv)
