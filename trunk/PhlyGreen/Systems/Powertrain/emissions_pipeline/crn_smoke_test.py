"""Phase 3 step 3.3 (smoke test) — run the Pietrosanto CRN on ONE PW127 combustor state under
Cantera 3.2, to confirm the kernel runs and to see EI at a PW127 operating point.
"""
import os, sys, io, contextlib, time
import numpy as np
import pandas as pd

CRN_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "crn"))
sys.path.insert(0, CRN_DIR)
os.chdir(CRN_DIR)                      # so Cantera finds kerosene_surrogate_luche.yaml
import evap_model_ottimizzato as evap  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))


def chi_from_T(T_in):
    order = ["ID", "AP", "CL", "TO"]
    Tm = np.array([evap.MODE_DATA[k]["T_in"] for k in order])
    chi = np.array([evap.MODE_DATA[k]["chi_mixer_scale"] for k in order])
    return max(float(np.interp(np.clip(T_in, Tm[0], Tm[-1]), Tm, chi)), 1.20)


def run_crn(T_in, p_in_pa, FAR, mdot_air, dPqP=0.95):
    params = {"label": "PW127", "power": 0.0, "T_in": T_in, "p_in_bar": p_in_pa / 1e5,
              "mdot_air": mdot_air, "FAR": FAR, "dPqP": dPqP,
              "chi_mixer_scale": chi_from_T(T_in), "EIUHC_ICAO": 0.0}
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        res = evap.run_crn_evap_mode("GRID", params)
    return {"EINOx": res.get("EI_NOx"), "EICO": res.get("EI_CO"),
            "EIUHC": res.get("EI_UHC_total"), "eta_b": res.get("eta_b6"), "T_DZ": res.get("T_DZ")}


if __name__ == "__main__":
    df = pd.read_csv(os.path.join(HERE, "pw127_crn_inputs.csv"))
    # a near-takeoff PW127 point (least extrapolation vs the CFM56 CRN box)
    row = df.sort_values("FAR").iloc[-1]
    print(f"PW127 state: T3={row.T3_K:.1f} K, P3={row.P3_Pa/1e6:.3f} MPa, FAR={row.FAR:.4f}, "
          f"mdot={row.mdot_air3_kg_s:.2f} kg/s  (PC={row.PC:.2f}, alt={row.alt_ft:.0f} ft)")
    t0 = time.time()
    out = run_crn(row.T3_K, row.P3_Pa, row.FAR, row.mdot_air3_kg_s)
    print(f"CRN ran in {time.time()-t0:.1f} s under Cantera {__import__('cantera').__version__}")
    for k, v in out.items():
        print(f"  {k:7s} = {v}")
    print("\nPW127 ICAO take-off targets (Excel): EINOx=19, EICO=2, EIUHC~0 g/kg")
