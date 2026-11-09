"""Run the Cantera chemical reactor network (CRN) of the emission pipeline at a few states.

Two checks, both read-only with respect to the package:

1. **CFM56 native calibration.** The CRN in
   ``trunk/PhlyGreen/Systems/Powertrain/emissions_pipeline/crn/evap_model_ottimizzato.py`` carries
   the four ICAO LTO combustor states of the CFM56-7B27E in ``MODE_DATA``. We run the CRN at these
   four states with its native air split (no patch) and compare with the ICAO emission indices
   transcribed in the same file.

2. **PW127 raw CRN on the sea-level slice.** ``build_pw127_surrogate.py`` runs the CRN with a
   richer primary zone (ARPZ = 0.24) and the mixer-scale floor 1.20, then rescales NOx to the
   certification values. The shipped CSV keeps only the rescaled NOx. We re-run the patched CRN on
   the 20 sea-level rows of ``pw127_crn_inputs_corrected.csv`` to recover the raw CRN NOx, CO and
   UHC there, and so the anchoring factor k(PF).

Results go to ../data/crn_check.json. Needs Cantera. Runtime: about two minutes.

    python manuals/engine-decks/scripts/check_crn.py
"""

import contextlib
import importlib
import io
import json
import os
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
TRUNK = os.path.abspath(os.path.join(HERE, "..", "..", "..", "trunk"))
PIPE = os.path.join(TRUNK, "PhlyGreen", "Systems", "Powertrain", "emissions_pipeline")
CRN_DIR = os.path.join(PIPE, "crn")
OUT = os.path.abspath(os.path.join(HERE, "..", "data", "crn_check.json"))

# ICAO values written in evap_model_ottimizzato.py (lines 706-707 and MODE_DATA[...]['EIUHC_ICAO']).
ICAO_CFM56 = {"ID": {"NOx": 4.36, "CO": 29.39, "UHC": 1.54},
              "AP": {"NOx": 9.09, "CO": 2.82, "UHC": 0.05},
              "CL": {"NOx": 17.89, "CO": 0.17, "UHC": 0.02},
              "TO": {"NOx": 23.94, "CO": 0.31, "UHC": 0.03}}
ARPZ_PW127 = 0.24          # build_pw127_surrogate.py


def quiet_run(evap, key, params):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        r = evap.run_crn_evap_mode(key, params)
    return {"NOx": float(r["EI_NOx"]), "CO": float(r["EI_CO"]), "UHC": float(r["EI_UHC_total"]),
            "eta_b": float(r["eta_b6"]), "T_out": float(r["T_DZ"])}


def main():
    t0 = time.time()
    os.chdir(CRN_DIR)          # the mechanism file is opened by relative path
    sys.path.insert(0, CRN_DIR)
    import cantera
    import evap_model_ottimizzato as evap

    # --- 1. native CFM56 calibration at its own four LTO states --------------------------
    native = {}
    for key in ["ID", "AP", "CL", "TO"]:
        params = dict(evap.MODE_DATA[key])
        res = quiet_run(evap, key, params)
        res["state"] = {k: params[k] for k in ("power", "T_in", "p_in_bar", "mdot_air", "FAR",
                                                "dPqP", "chi_mixer_scale")}
        res["ICAO"] = ICAO_CFM56[key]
        native[key] = res
        print(f"  CFM56 {key}: NOx {res['NOx']:.2f} (ICAO {ICAO_CFM56[key]['NOx']}), "
              f"CO {res['CO']:.2f} (ICAO {ICAO_CFM56[key]['CO']})")
    air_split = {"ARPZ": evap.ARPZ, "ARSZ": evap.ARSZ, "ARDZ": evap.ARDZ, "N_PZ": evap.N_PZ}

    # --- 2. PW127-patched CRN on the sea-level rows ----------------------------------------
    evap = importlib.reload(evap)
    rest = evap.ARSZ + evap.ARDZ
    scale = (1.0 - ARPZ_PW127) / rest
    evap.ARPZ, evap.ARSZ, evap.ARDZ = ARPZ_PW127, evap.ARSZ * scale, evap.ARDZ * scale
    order = ["ID", "AP", "CL", "TO"]
    t_modes = np.array([evap.MODE_DATA[k]["T_in"] for k in order])
    chi_modes = np.array([evap.MODE_DATA[k]["chi_mixer_scale"] for k in order])

    states = pd.read_csv(os.path.join(PIPE, "pw127_crn_inputs_corrected.csv"))
    shipped = pd.read_csv(os.path.join(TRUNK, "PhlyGreen", "Systems", "Powertrain", "data",
                                       "PW127_Emission_Map.csv"))
    sls = states[states["alt_ft"] < 1.0]
    pw127 = []
    for row in sls.itertuples():
        t3 = row.T3_K
        chi = max(float(np.interp(np.clip(t3, t_modes[0], t_modes[-1]), t_modes, chi_modes)), 1.20)
        params = {"label": "PW127", "power": 0., "T_in": t3, "p_in_bar": row.P3_Pa / 1e5,
                  "mdot_air": row.mdot_air3_kg_s, "FAR": row.FAR, "dPqP": 0.95,
                  "chi_mixer_scale": chi, "EIUHC_ICAO": 0.0}
        res = quiet_run(evap, "GRID", params)
        match = shipped[np.isclose(shipped.Mach, row.Mach) & np.isclose(shipped.alt_ft, 0.0)
                        & np.isclose(shipped.PC, row.PC)]
        res.update({"Mach": float(row.Mach), "PC": float(row.PC), "T3_K": float(t3),
                    "FAR": float(row.FAR), "chi": chi,
                    "shipped_EINOX": float(match.EINOX.iloc[0]),
                    "shipped_EICO": float(match.EICO.iloc[0]),
                    "shipped_EIUHC": float(match.EIUHC.iloc[0])})
        pw127.append(res)
    print(f"  PW127 sea-level slice: {len(pw127)} points")

    out = {"cantera_version": cantera.__version__, "cfm56_native": native,
           "cfm56_air_split": air_split, "pw127_sls": pw127, "runtime_s": time.time() - t0}
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print(f"done in {out['runtime_s']:.0f} s -> {OUT}")


if __name__ == "__main__":
    main()
