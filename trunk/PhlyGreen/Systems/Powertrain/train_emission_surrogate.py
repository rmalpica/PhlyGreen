"""Offline trainer for the gas-turbine EMISSION-INDEX response surface (not used at run time).

Fits EI(alt_ft, Mach, power_fraction) -> (EINOx, EICO, EIUHC) [g/kg fuel] from the packaged
PW127 emission map ``data/PW127_Emission_Map.csv`` and serializes it to
``data/Emission_Model_PW127.pkl``, which the runtime loader
:mod:`.emissions_surrogate` (:class:`EmissionSurrogate`) reads.

Provenance of the CSV (offline, heavy/optional deps — see ``WIP/phase3_pw127/``): a pyCycle
PW127 cycle maps each operating point to the combustor inlet state, a Cantera Chemical Reactor
Network (CRN) calibrated to ICAO LTO data turns that state into emission indices, the CO/UHC are
taken directly from the (PW127-recalibrated) CRN and the NOx keeps the CRN's altitude/Mach/power
*shape* but is rescaled (anchored) to the PW127 ICAO NOx at the sea-level LTO modes. This trainer
itself needs only pandas + scipy + scikit-learn.

Run it:
    cd trunk/PhlyGreen/Systems/Powertrain && python train_emission_surrogate.py
"""

import os
import pickle

import numpy as np
import pandas as pd
from scipy.interpolate import Rbf
from sklearn.preprocessing import StandardScaler

_HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(_HERE, "data", "PW127_Emission_Map.csv")
PKL_PATH = os.path.join(_HERE, "data", "Emission_Model_PW127.pkl")

INPUTS = ["alt_ft", "Mach", "PC"]          # operating point: altitude, Mach, power fraction
OUTPUTS = ["EINOX", "EICO", "EIUHC"]       # emission indices [g/kg fuel]
LOG_OUTPUTS = {"EICO", "EIUHC"}            # fit these in log10 space (positive, multi-scale)


def _fit_entry(X, y, log, smooth=0.1):
    """One output: StandardScaler + smooth multiquadric Rbf (optional log10), as a plain dict."""
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)
    yt = np.log10(np.clip(y, 1e-9, None)) if log else y
    rbf = Rbf(*Xs.T, yt, function="multiquadric", smooth=smooth)
    return {"kind": "rbf", "scaler": scaler, "model": rbf, "log": log}


def main(csv=CSV_PATH, pkl=PKL_PATH, tag="PW127"):
    df = pd.read_csv(csv).dropna(subset=INPUTS + OUTPUTS)
    X = df[INPUTS].to_numpy(float)
    package = {
        "inputs": INPUTS, "outputs": OUTPUTS, "tag": tag,
        "input_ranges": {c: (float(df[c].min()), float(df[c].max())) for c in INPUTS},
        "models": {o: _fit_entry(X, df[o].to_numpy(float), o in LOG_OUTPUTS) for o in OUTPUTS},
    }
    with open(pkl, "wb") as f:
        pickle.dump(package, f)
    print(f"fitted EI surrogate from {len(df)} points -> {pkl}")
    for o in OUTPUTS:
        print(f"  {o}: range [{df[o].min():.3g}, {df[o].max():.3g}] g/kg")
    return package


if __name__ == "__main__":
    main()
