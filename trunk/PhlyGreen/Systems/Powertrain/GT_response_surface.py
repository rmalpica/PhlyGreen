"""Gas-turbine (turboshaft) response-surface model.

A Class-II gas-turbine efficiency model: a set of radial-basis-function (RBF) surrogates,
trained offline from a physics engine cycle (pycycle, see ``Single_spool_GT.py``) and a
universal ratio map (see ``Response_Surface_GT.py``), and serialized to
``data/GT_Engine_Model_Complete.pkl``.

The surrogate is *universal* (normalized by design power), so one map covers any engine
size: given the design shaft power, the flight condition (altitude, Mach) and the required
power, it returns the thermal efficiency, the power available, and whether the engine is
power-limited. Loading needs only numpy + scipy (Rbf) + scikit-learn (StandardScaler) — no
pycycle/openmdao at run time.
"""

import os
import pickle

import numpy as np

_DEFAULT_PKL = os.path.join(os.path.dirname(__file__), "data", "GT_Engine_Model_Complete.pkl")


class GasTurbineResponseSurface:
    """RBF response surface for turboshaft efficiency and power limit.

    Args:
        model_path: path to the serialized model package (a dict with ``scaler_eff``/
            ``model_eff`` for efficiency and ``scaler_lim``/``model_lim`` for the power
            limit). Defaults to the packaged ``GT_Engine_Model_Complete.pkl``.
    """

    def __init__(self, model_path=None):
        path = model_path or _DEFAULT_PKL
        with open(path, "rb") as f:
            pkg = pickle.load(f)
        self.scaler_eff = pkg["scaler_eff"]   # inputs: [design_hp, altitude_ft, mach, actual_hp]
        self.model_eff = pkg["model_eff"]
        self.scaler_lim = pkg["scaler_lim"]   # inputs: [design_hp, altitude_ft, mach]
        self.model_lim = pkg["model_lim"]
        self.scaler_wt = pkg.get("scaler_wt")  # input: [design_hp]
        self.model_wt = pkg.get("model_wt")
        self.loaded = True

    def calculate_physics_weight(self, design_hp):
        """Dry engine mass [lb] from WATE++-style correlations on design power [hp]."""
        W_air = design_hp / 145.0
        OPR = 15.0
        w_comp = 10.5 * (W_air ** 0.8) * (OPR ** 0.4)
        w_burner = 4.5 * (W_air ** 0.9) * (OPR ** 0.15)
        w_hpt = 14.5 * (W_air ** 0.85) * 2 * 0.8
        w_pt = 13.0 * (W_air ** 0.85) * 2
        w_acc = 35.0 + 1.2 * W_air
        core_weight = w_comp + w_burner + w_hpt + w_pt
        return (core_weight * 1.15 + w_acc) * 1.10

    def predict(self, design_hp, altitude_ft, mach, required_power_hp):
        """Return ``(efficiency, weight_lb, max_power_avail_hp, is_limited)``.

        Args:
            design_hp: engine design (rated) shaft power [hp].
            altitude_ft: altitude [ft].
            mach: flight Mach number.
            required_power_hp: required shaft power [hp] (per engine).
        """
        if not self.loaded:
            return 0.30, 0.0, 99999.9, False
        if np.isnan(required_power_hp) or np.isinf(required_power_hp):
            return 0.30, 0.0, 99999.9, False
        if np.isnan(mach) or np.isinf(mach):
            mach = 0.0

        try:
            # 1. Maximum available shaft power at this (design power, altitude, Mach).
            lim_scaled = self.scaler_lim.transform(np.array([[design_hp, altitude_ft, mach]]))
            max_power_avail = float(self.model_lim(lim_scaled[0, 0], lim_scaled[0, 1], lim_scaled[0, 2]))

            used_power = required_power_hp
            is_limited = False
            if required_power_hp > max_power_avail:
                used_power = max_power_avail
                is_limited = True

            # 2. Thermal efficiency at (design power, altitude, Mach, used power).
            eff_scaled = self.scaler_eff.transform(
                np.array([[design_hp, altitude_ft, mach, used_power]]))
            eff_raw = float(self.model_eff(
                eff_scaled[0, 0], eff_scaled[0, 1], eff_scaled[0, 2], eff_scaled[0, 3]))
            efficiency = float(np.clip(eff_raw, 0.01, 0.45))

            # 3. Dry engine mass: surrogate if present, else the physics correlation.
            if self.model_wt is not None and self.scaler_wt is not None:
                wt_scaled = self.scaler_wt.transform(np.array([[design_hp]]))
                weight_lb = float(self.model_wt(wt_scaled[0, 0]))
            else:
                weight_lb = self.calculate_physics_weight(design_hp)

            return efficiency, weight_lb, max_power_avail, is_limited
        except Exception:
            return 0.30, 0.0, 99999.9, False
