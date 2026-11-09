"""Offline trainer for the gas-turbine response surface (not used at run time).

Fits the RBF surrogates from the **universal** turboshaft map
``data/GT_Universal_Map.csv`` (a single reference engine: thermal efficiency vs altitude,
Mach and *power fraction*) and serializes them to ``data/GT_Engine_Model_Complete.pkl``,
which the runtime model :mod:`.gas_turbine_surrogate` loads.

The map is *size-independent*: the dependence of efficiency on engine size is applied at run
time (keyed on the nominal power chosen before sizing) by
:func:`.gas_turbine_surrogate.get_scaled_efficiency`. The power fraction is defined over the
available power ``P_des * delta(h)`` (ISA pressure ratio), so no power-limit surrogate is
stored. The dry engine mass remains a physics correlation of the design power. The training
box (altitude, Mach, power fraction) is stored as ``input_ranges``; the runtime model clips
its inputs to it.

The trainer refuses a map in which any point did not deliver its target power (columns
``Target_hp`` / ``Delivered_hp`` written by the generator), so an unconverged deck point
cannot be fitted silently.

The CSV itself comes from the pycycle engine cycle in ``data/Single_spool_GT.py``. Re-run
this script to regenerate the pkl after regenerating the CSV. Requires pandas + scikit-learn.

Run it:
    cd trunk/PhlyGreen/Systems/Powertrain && python train_gas_turbine_surrogate.py
"""

import os
import pickle

import numpy as np
import pandas as pd
from scipy.interpolate import Rbf
from sklearn.preprocessing import StandardScaler

try:
    from .gas_turbine_surrogate import calibrate_scaling_exponent
except ImportError:  # run as a plain script (no package context)
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from gas_turbine_surrogate import calibrate_scaling_exponent

_HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(_HERE, "data", "GT_Universal_Map.csv")
PKL_PATH = os.path.join(_HERE, "data", "GT_Engine_Model_Complete.pkl")

# Reference engine the universal map was generated for (must match Single_spool_GT.py and the
# runtime reference in gas_turbine_surrogate.py).
REF_HP = 2750.0

# Relative tolerance on delivered vs target shaft power (same as data/Single_spool_GT.py).
POWER_TOL = 1e-3


def calculate_physics_weight(design_hp):
    """Dry engine mass [lb] from WATE++-style correlations on design power [hp]."""
    W_air = design_hp / 145.0          # ~145 hp/(lb/s) for modern small turboshafts
    OPR = 15.0
    w_comp = 10.5 * (W_air ** 0.8) * (OPR ** 0.4)
    w_burner = 4.5 * (W_air ** 0.9) * (OPR ** 0.15)
    w_hpt = 14.5 * (W_air ** 0.85) * 2 * 0.8
    w_pt = 13.0 * (W_air ** 0.85) * 2
    w_acc = 35.0 + 1.2 * W_air
    core = w_comp + w_burner + w_hpt + w_pt
    return (core * 1.15 + w_acc) * 1.10


def main():
    df = pd.read_csv(CSV_PATH)
    print(f"Loaded {CSV_PATH} ({len(df)} points)")
    cols = set(df.columns)
    expected = {"Altitude_ft", "Mach", "Power", "Efficiency"}
    if not expected.issubset(cols):
        raise ValueError(
            f"{CSV_PATH} must be a universal map with columns {sorted(expected)}; got "
            f"{sorted(cols)}. Regenerate with data/Single_spool_GT.py.")

    # --- Every map point must have delivered its target power (deck converged) --------
    if not {"Target_hp", "Delivered_hp"}.issubset(cols):
        raise ValueError(f"{CSV_PATH} has no Target_hp/Delivered_hp columns, so its convergence "
                         f"cannot be checked. Regenerate it with data/Single_spool_GT.py.")
    power_error = (df["Delivered_hp"] - df["Target_hp"]).abs() / df["Target_hp"]
    if (power_error > POWER_TOL).any():
        bad = df[power_error > POWER_TOL]
        raise ValueError(f"{len(bad)} map points did not deliver their target power within "
                         f"{POWER_TOL:.0e}:\n{bad}")

    # --- Efficiency surrogate: eta(altitude_ft, mach, power_fraction) ----------------
    print("Training universal efficiency model...")
    X_raw = df[["Altitude_ft", "Mach", "Power"]].values
    y_eff = df["Efficiency"].values
    scaler_eff = StandardScaler()
    X_scaled = scaler_eff.fit_transform(X_raw)
    rbf_efficiency = Rbf(X_scaled[:, 0], X_scaled[:, 1], X_scaled[:, 2], y_eff,
                         function="linear", smooth=0)

    # --- Dry-mass surrogate: weight(design_hp) ---------------------------------------
    print("Training weight model...")
    hp_grid = np.linspace(300.0, 8000.0, 40).reshape(-1, 1)
    w_grid = np.array([calculate_physics_weight(h[0]) for h in hp_grid])
    scaler_wt = StandardScaler()
    Xw = scaler_wt.fit_transform(hp_grid)
    rbf_weight = Rbf(Xw[:, 0], w_grid, function="cubic", smooth=0)

    # --- Runtime size-scaling exponent (calibrated once here, stored in the pkl) ------
    n = calibrate_scaling_exponent()
    print(f"Calibrated size-scaling exponent n = {n:.5f} (reference {REF_HP:.0f} hp)")

    package = {
        "scaler_eff": scaler_eff, "model_eff": rbf_efficiency,
        "scaler_wt": scaler_wt, "model_wt": rbf_weight,
        "ref_hp": REF_HP, "scaling_n": n,
        "universal": True,
        "input_ranges": {
            "altitude_ft": (float(df["Altitude_ft"].min()), float(df["Altitude_ft"].max())),
            "mach": (float(df["Mach"].min()), float(df["Mach"].max())),
            "power_fraction": (float(df["Power"].min()), float(df["Power"].max())),
        },
    }
    with open(PKL_PATH, "wb") as f:
        pickle.dump(package, f)
    print(f"SUCCESS: universal surrogate saved to {PKL_PATH}")


if __name__ == "__main__":
    main()
