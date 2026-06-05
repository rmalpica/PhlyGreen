"""Phase 3 — build the PW127 emission-index dataset and surrogate (certification-anchored NOx).

1. Run the PW127-calibrated CRN (richer primary zone, ARPZ=0.24) over the part-power-corrected
   combustor-state envelope -> EINOx_crn, EICO, EIUHC at each (alt, Mach, power-fraction).
2. CO and UHC: use the CRN directly (CO is recalibrated to PW127).
3. NOx: keep the CRN's altitude/Mach/power *shape* but RESCALE to the PW127 ICAO NOx at the SLS
   LTO modes (certification anchor): EINOx = EINOx_crn * k(PF), k(PF) = NOx_cert(PF)/NOx_crn_SLS(PF).
4. Write the PW127 EI dataset and refit the response surface.
"""
import os, sys, io, contextlib
import multiprocessing as mp
import numpy as np
import pandas as pd
from scipy.interpolate import PchipInterpolator

HERE = os.path.dirname(os.path.abspath(__file__))
CRN_DIR = os.path.join(HERE, "crn")
ARPZ_PW127 = 0.24
# certification NOx vs useful power fraction (To/Cl/App; idle is below the flight envelope)
PF_CERT = np.array([0.30, 0.90, 1.00]); NOX_CERT = np.array([10.0, 16.0, 19.0])


def _init():
    os.chdir(CRN_DIR); sys.path.insert(0, CRN_DIR)
    global evap
    import evap_model_ottimizzato as evap
    rest = evap.ARSZ + evap.ARDZ
    sc = (1.0 - ARPZ_PW127) / rest
    evap.ARPZ, evap.ARSZ, evap.ARDZ = ARPZ_PW127, evap.ARSZ * sc, evap.ARDZ * sc


def _run_point(row):
    T3, P3, FAR, mdot = row
    order = ["ID", "AP", "CL", "TO"]
    Tm = np.array([evap.MODE_DATA[k]["T_in"] for k in order])
    chm = np.array([evap.MODE_DATA[k]["chi_mixer_scale"] for k in order])
    chi = max(float(np.interp(np.clip(T3, Tm[0], Tm[-1]), Tm, chm)), 1.20)
    params = {"label": "PW127", "power": 0., "T_in": T3, "p_in_bar": P3 / 1e5, "mdot_air": mdot,
              "FAR": FAR, "dPqP": 0.95, "chi_mixer_scale": chi, "EIUHC_ICAO": 0.0}
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            r = evap.run_crn_evap_mode("GRID", params)
        return (float(r.get("EI_NOx", np.nan)), float(r.get("EI_CO", np.nan)),
                float(r.get("EI_UHC_total", np.nan)))
    except Exception:
        return (np.nan, np.nan, np.nan)


def main():
    df = pd.read_csv(os.path.join(HERE, "pw127_crn_inputs_corrected.csv"))
    rows = df[["T3_K", "P3_Pa", "FAR", "mdot_air3_kg_s"]].to_numpy(float)
    print(f"Running PW127 CRN (ARPZ={ARPZ_PW127}) over {len(rows)} envelope points ...")
    with mp.Pool(processes=min(6, mp.cpu_count()), initializer=_init) as pool:
        out = pool.map(_run_point, rows)
    out = np.array(out)
    df["EINOX_crn"], df["EICO"], df["EIUHC"] = out[:, 0], out[:, 1], out[:, 2]
    good = df.dropna(subset=["EINOX_crn", "EICO", "EIUHC"])
    print(f"  {len(good)}/{len(df)} CRN points converged")

    # --- certification anchor for NOx ---
    # Anchor on the SLS slice (Mach=0 static is excluded upstream as a convergence artifact, so
    # the remaining low-Mach SLS points represent the ICAO ground condition); the CRN supplies the
    # altitude (and mild Mach) variation on top.
    sls = good[good["alt_ft"] < 1.0]
    pf_sls = np.sort(sls["PC"].unique())
    nox_crn_sls = np.array([sls[np.isclose(sls["PC"], p)]["EINOX_crn"].mean() for p in pf_sls])
    crn_sls_i = PchipInterpolator(pf_sls, nox_crn_sls)
    cert_i = PchipInterpolator(PF_CERT, NOX_CERT)
    def k(pf):
        pf = np.clip(pf, PF_CERT[0], PF_CERT[-1])
        return float(cert_i(pf)) / max(float(crn_sls_i(np.clip(pf, pf_sls[0], pf_sls[-1]))), 1e-6)
    good = good.copy()
    good["EINOX"] = [r.EINOX_crn * k(r.PC) for r in good.itertuples()]

    print("\nNOx anchor check at SLS (PF -> CRN, anchored, certification):")
    for pf in pf_sls:
        s = good[(good["alt_ft"] < 1.0) & np.isclose(good["PC"], pf)]
        print(f"  PF={pf:.2f}: CRN {s['EINOX_crn'].mean():5.1f} -> anchored {s['EINOX'].mean():5.1f}"
              f"  (cert {float(cert_i(np.clip(pf,0.3,1.0))):.1f})")

    out_csv = os.path.abspath(os.path.join(HERE, "..", "data", "PW127_Emission_Map.csv"))
    good[["op_id", "Mach", "alt_ft", "PC", "time_s", "dist_nm", "T3_K", "P3_Pa", "FAR",
          "mdot_air3_kg_s", "EINOX", "EICO", "EIUHC"]].to_csv(out_csv, index=False)
    print(f"\nsaved PW127 EI dataset -> {out_csv}")

    # --- refit the surrogate (reuse the Phase-1 fitter) ---
    sys.path.insert(0, os.path.join(HERE, ".."))
    import train_emission_surrogate as T
    print("\n--- fitting packaged PW127 surrogate ---")
    T.main(csv=out_csv)


if __name__ == "__main__":
    main()
