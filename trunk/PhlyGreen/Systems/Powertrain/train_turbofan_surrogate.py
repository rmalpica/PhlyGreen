"""Offline trainer for the turbofan response surface.

Reads ``data/Turbofan_Universal_Map.csv`` (written by ``data/HBTF_turbofan.py``) and fits
the artifact ``data/Turbofan_Engine_Model.pkl`` that :mod:`.turbofan_surrogate` loads at run
time. The packaging mirrors :mod:`.train_gas_turbine_surrogate`: a ``StandardScaler`` plus a
scipy ``Rbf`` per output, so the run-time model needs no pycycle.

Three surfaces are fitted:

* ``eta_o(alt_ft, Mach, ThrustFraction)`` -- overall efficiency, what the powertrain graph
  consumes as ``Pf/Pp = 1/eta_o``;
* ``TSFC(alt_ft, Mach, ThrustFraction)`` -- reported, not solved with; carried so results can
  be compared against published engine data;
* ``mdot_air3`` and ``mdot_inlet(alt_ft, Mach, ThrustFraction)`` -- the COMBUSTOR-INLET (core,
  post-bleed) and the TOTAL inlet air mass flow of the reference engine. Unlike efficiency and
  TSFC these are *not* size-independent, so the run-time model scales them by the ratio of the
  installed thrust to the reference F00;
* ``BPR(alt_ft, Mach, ThrustFraction)`` -- the bypass ratio, which in this deck is an off-design
  *balance* variable (solved against the bypass-nozzle throat area). It is fitted rather than
  assumed constant, which is also why total inlet flow cannot be recovered from the core flow
  and a fixed bypass ratio;
* ``ThrustLapse(alt_ft, Mach)`` -- available thrust as a fraction of the SLS rating, fitted
  from the deck's own full-throttle points rather than assumed from a lapse law.

The lapse depends only on the flight condition, so its rows are de-duplicated over thrust
fraction before fitting; feeding an RBF several identical points makes the interpolation
matrix singular.

Usage::

    python train_turbofan_surrogate.py
"""

import os
import pickle

import numpy as np
from scipy.interpolate import Rbf
from sklearn.preprocessing import StandardScaler

_HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(_HERE, "data", "Turbofan_Universal_Map.csv")
PKL_PATH = os.path.join(_HERE, "data", "Turbofan_Engine_Model.pkl")

EFF_INPUTS = ["alt_ft", "Mach", "ThrustFraction"]
LAPSE_INPUTS = ["alt_ft", "Mach"]


def _reference_f00(csv):
    """Sea-level-static thrust the map's lapse column is normalised by, cached beside the CSV."""
    import os
    path = os.path.splitext(csv)[0] + "_F00.txt"
    try:
        return float(open(path).read().strip())
    except Exception:
        return None


def main(csv=CSV_PATH, pkl=PKL_PATH, tag="CFM56-class HBTF"):
    import csv as _csv

    with open(csv) as f:
        rows = list(_csv.DictReader(f))
    if not rows:
        raise ValueError(f"{csv} is empty -- run data/HBTF_turbofan.py first.")

    col = lambda name: np.array([float(r[name]) for r in rows])
    alt, mach, frac = col("Altitude_ft"), col("Mach"), col("ThrustFraction")
    eta, tsfc, lapse = col("Efficiency"), col("TSFC"), col("ThrustLapse")
    mdot = col("mdot_air3")
    mdot_in = col("mdot_inlet")
    bpr = col("BPR")

    # --- eta_o and TSFC over (alt, Mach, thrust fraction) ---
    X = np.column_stack([alt, mach, frac])
    scaler_eff = StandardScaler().fit(X)
    Xs = scaler_eff.transform(X)
    # 'multiquadric' with a little smoothing: the deck's Newton solves carry a small amount
    # of convergence noise, and a pure interpolant would chase it.
    rbf_eff = Rbf(Xs[:, 0], Xs[:, 1], Xs[:, 2], eta, function="multiquadric", smooth=1e-3)
    rbf_tsfc = Rbf(Xs[:, 0], Xs[:, 1], Xs[:, 2], tsfc, function="multiquadric", smooth=1e-3)
    rbf_mdot = Rbf(Xs[:, 0], Xs[:, 1], Xs[:, 2], mdot, function="multiquadric", smooth=1e-3)
    rbf_mdot_in = Rbf(Xs[:, 0], Xs[:, 1], Xs[:, 2], mdot_in, function="multiquadric", smooth=1e-3)
    rbf_bpr = Rbf(Xs[:, 0], Xs[:, 1], Xs[:, 2], bpr, function="multiquadric", smooth=1e-3)

    # --- thrust lapse over (alt, Mach) only: one value per flight condition ---
    seen, xl, yl = set(), [], []
    for a, m, lp in zip(alt, mach, lapse):
        if (a, m) in seen:
            continue
        seen.add((a, m))
        xl.append([a, m])
        yl.append(lp)
    XL = np.array(xl)
    scaler_lapse = StandardScaler().fit(XL)
    XLs = scaler_lapse.transform(XL)
    rbf_lapse = Rbf(XLs[:, 0], XLs[:, 1], np.array(yl), function="multiquadric", smooth=1e-4)

    package = {
        "scaler_eff": scaler_eff, "model_eff": rbf_eff, "model_tsfc": rbf_tsfc,
        "model_mdot_air3": rbf_mdot, "model_mdot_inlet": rbf_mdot_in,
        "model_bpr": rbf_bpr,
        "scaler_lapse": scaler_lapse, "model_lapse": rbf_lapse,
        "eff_inputs": EFF_INPUTS, "lapse_inputs": LAPSE_INPUTS,
        "input_ranges": {
            "alt_ft": (float(alt.min()), float(alt.max())),
            "Mach": (float(mach.min()), float(mach.max())),
            "ThrustFraction": (float(frac.min()), float(frac.max())),
        },
        "ref_fn": _reference_f00(csv),
        "tag": tag,
        "universal": True,
    }
    with open(pkl, "wb") as f:
        pickle.dump(package, f)

    print(f"Fitted {len(rows)} map points ({len(xl)} flight conditions) -> {pkl}")
    print(f"  eta_o range  : {eta.min():.3f} .. {eta.max():.3f}")
    print(f"  TSFC range   : {tsfc.min():.3e} .. {tsfc.max():.3e} kg/(N s)")
    print(f"  lapse range  : {min(yl):.3f} .. {max(yl):.3f}")
    print(f"  core air flow: {mdot.min():.1f} .. {mdot.max():.1f} kg/s (reference engine)")
    print(f"  inlet flow   : {mdot_in.min():.1f} .. {mdot_in.max():.1f} kg/s (reference engine)")
    print(f"  bypass ratio : {bpr.min():.2f} .. {bpr.max():.2f}  (off-design balance variable)")
    return pkl


if __name__ == "__main__":
    main()
