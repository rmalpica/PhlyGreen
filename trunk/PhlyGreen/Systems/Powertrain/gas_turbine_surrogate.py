"""Gas-turbine (turboshaft) response-surface model — *runtime*.

A Class-II gas-turbine efficiency model built from a **universal** (size-independent) RBF
surrogate, serialized to ``data/GT_Engine_Model_Complete.pkl``. The surrogate stores thermal
efficiency as a function of *altitude, Mach and power fraction* for a single reference engine;
this module loads and evaluates it (class :class:`GasTurbineResponseSurface`). The offline
trainer that fits the pkl is :mod:`.train_gas_turbine_surrogate`, and the pycycle cycle that
produces the CSV map is ``data/Single_spool_GT.py``.

**Size scaling happens here, at run time.** The map is universal, so the efficiency penalty
for *small* engines is applied when the surrogate is evaluated, keyed on the nominal (design)
power chosen before sizing: :func:`get_scaled_efficiency` raises the component losses for an
engine smaller than the reference, using an exponent :func:`calibrate_scaling_exponent` fits
once (cached) from real turboshaft SFC-vs-power data. The available power lapses with altitude
analytically (ISA pressure ratio). Loading needs only numpy + scipy (Rbf) + scikit-learn
(StandardScaler) — no pycycle/openmdao at run time.
"""

import os
import pickle

import numpy as np

_DEFAULT_PKL = os.path.join(os.path.dirname(__file__), "data", "GT_Engine_Model_Complete.pkl")

# Reference engine the universal map was generated for (must match Single_spool_GT.py /
# train_gas_turbine_surrogate.py).
REF_HP = 2750.0

_CALIBRATED_N = None   # process-level cache for the runtime scaling exponent


# ---------------------------------------------------------------------------------------
# Runtime size-scaling (moved here from the map generator so the map stays universal)
# ---------------------------------------------------------------------------------------
def get_scaled_efficiency(target_pwr, ref_pwr, ref_eff, n):
    """Scale a reference efficiency to a different engine *size* (design power).

    Smaller engine ⇒ lower efficiency. Scales the *losses*:
    ``(1 - eta) = (1 - eta_ref) * (P_ref / P_target) ** n``.
    """
    if target_pwr is None or target_pwr <= 0:
        return ref_eff
    loss_factor = (ref_pwr / target_pwr) ** n
    return 1.0 - (1.0 - ref_eff) * loss_factor


def calibrate_scaling_exponent():
    """Fit the size-scaling exponent ``n`` from real turboshaft SFC-vs-power data.

    Returns the exponent for :func:`get_scaled_efficiency`. Uses a small embedded dataset of
    representative turboshafts; ~0.1 typically. Cheap; the result is cached at module level.
    """
    global _CALIBRATED_N
    if _CALIBRATED_N is not None:
        return _CALIBRATED_N

    from scipy.optimize import curve_fit

    # [Power (shp), SFC (lb/hp-hr)] for representative turboshafts.
    data = np.array([
        [420, 0.650], [650, 0.592], [730, 0.580], [1000, 0.550], [1200, 0.540],
        [1700, 0.480], [2500, 0.460], [4500, 0.430], [5500, 0.640],
    ])
    powers_shp, sfc = data[:, 0], data[:, 1]
    LHV_BTU_lb = 18400.0
    eta_real = 2544.43 / (sfc * LHV_BTU_lb)
    loss_real = 1.0 - eta_real

    ref_idx = 6                     # 2500 hp reference row
    ref_pwr, ref_loss = powers_shp[ref_idx], loss_real[ref_idx]

    def model(pwr, n):
        return ref_loss * (ref_pwr / pwr) ** n

    popt, _ = curve_fit(model, powers_shp, loss_real, p0=[0.15])
    _CALIBRATED_N = float(popt[0])
    return _CALIBRATED_N


def _isa_pressure_ratio(altitude_ft):
    """ISA pressure ratio delta = p/p_SL (troposphere), matching the map generator."""
    P_std_sl, T_std_sl = 14.696, 518.67     # psia, degR
    T_amb = T_std_sl - 3.566e-3 * altitude_ft
    if T_amb < 390.0:
        T_amb = 390.0
    P_amb = P_std_sl * (T_amb / T_std_sl) ** 5.2561
    return P_amb / P_std_sl


class GasTurbineResponseSurface:
    """Universal RBF response surface for turboshaft efficiency, with runtime size scaling.

    Args:
        model_path: path to the serialized universal model package (``scaler_eff``/
            ``model_eff`` over ``[altitude_ft, mach, power_fraction]``, plus optional
            ``scaler_wt``/``model_wt`` for dry mass and ``ref_hp``/``scaling_n``). Defaults to
            the packaged ``GT_Engine_Model_Complete.pkl``.
    """

    def __init__(self, model_path=None):
        path = model_path or _DEFAULT_PKL
        with open(path, "rb") as f:
            pkg = pickle.load(f)
        self.scaler_eff = pkg["scaler_eff"]   # inputs: [altitude_ft, mach, power_fraction]
        self.model_eff = pkg["model_eff"]
        self.scaler_wt = pkg.get("scaler_wt")  # input: [design_hp]
        self.model_wt = pkg.get("model_wt")
        self.ref_hp = pkg.get("ref_hp", REF_HP)
        # Scaling exponent: stored with the model if present, else calibrated on demand.
        self._n = pkg.get("scaling_n")
        self.loaded = True

    @property
    def scaling_n(self):
        if self._n is None:
            self._n = calibrate_scaling_exponent()
        return self._n

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

        The efficiency is the universal (reference-engine) value at this operating point,
        scaled to the actual engine *size* via :func:`get_scaled_efficiency` keyed on
        ``design_hp`` — so a smaller nominal engine is less efficient.

        Args:
            design_hp: engine design (rated) shaft power [hp], per engine.
            altitude_ft: altitude [ft].
            mach: flight Mach number.
            required_power_hp: required shaft power [hp] (per engine).
        """
        if not self.loaded:
            return 0.30, 0.0, 99999.9, False
        if design_hp is None or design_hp <= 0:
            return 0.30, 0.0, 99999.9, False
        if np.isnan(required_power_hp) or np.isinf(required_power_hp):
            return 0.30, 0.0, 99999.9, False
        if np.isnan(mach) or np.isinf(mach):
            mach = 0.0

        try:
            # 1. Available power lapses with altitude (ISA); the map is universal in size.
            delta = _isa_pressure_ratio(altitude_ft)
            max_power_avail = design_hp * delta

            used_power = required_power_hp
            is_limited = False
            if required_power_hp > max_power_avail:
                used_power = max_power_avail
                is_limited = True

            # 2. Power fraction (req / available); clip to the map's trained range.
            frac = used_power / max_power_avail if max_power_avail > 0 else 0.0
            frac = float(np.clip(frac, 0.05, 1.0))

            # 3. Universal (reference-engine) efficiency at [altitude, mach, fraction].
            eff_scaled = self.scaler_eff.transform(np.array([[altitude_ft, mach, frac]]))
            eff_ref = float(self.model_eff(eff_scaled[0, 0], eff_scaled[0, 1], eff_scaled[0, 2]))

            # 4. Scale for engine size (smaller design power ⇒ lower efficiency).
            eff_sized = get_scaled_efficiency(design_hp, self.ref_hp, eff_ref, self.scaling_n)
            efficiency = float(np.clip(eff_sized, 0.01, 0.45))

            # 5. Dry engine mass.
            if self.model_wt is not None and self.scaler_wt is not None:
                wt_scaled = self.scaler_wt.transform(np.array([[design_hp]]))
                weight_lb = float(self.model_wt(wt_scaled[0, 0]))
            else:
                weight_lb = self.calculate_physics_weight(design_hp)

            return efficiency, weight_lb, max_power_avail, is_limited
        except Exception:
            return 0.30, 0.0, 99999.9, False
