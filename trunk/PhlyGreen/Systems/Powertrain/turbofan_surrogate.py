"""Turbofan (high-bypass) response-surface model — *runtime*.

The turbofan counterpart of :mod:`.gas_turbine_surrogate`. Where that model returns the
shaft-power efficiency of a turboshaft, this one returns the **overall efficiency** of a
turbofan,

    eta_o = F * V / (mdot_f * LHV),

as a function of *altitude, Mach and thrust fraction*, plus the **TSFC** and the
**thrust lapse** fitted from the same sweep. Serialized to
``data/Turbofan_Engine_Model.pkl``; the offline trainer is
:mod:`.train_turbofan_surrogate` and the pyCycle cycle that produces the CSV map is
``data/HBTF_turbofan.py``.

Why overall efficiency and not TSFC: the powertrain graph normalises on propulsive power,
so ``Pf/Pp = 1/eta_o`` drops straight into the existing fuel closure. The two are the same
information -- ``TSFC = V/(eta_o * LHV)`` -- and the map carries TSFC as well so results can
be compared against published engine data.

**Thrust fraction is a native coordinate.** The pyCycle deck is run twice at each
(altitude, Mach): once at full throttle to get ``F_max``, once in ``percent_thrust`` mode at
each fraction of it. So the map is *universal* in the same sense as the turboshaft map --
it describes the cycle, not one particular engine size.

**No size scaling is applied.** The turboshaft map corrects small-engine efficiency with an
exponent fitted to turboshaft SFC-vs-shaft-power data; that dataset and that law do not
describe turbofans, and applying it here would be quietly wrong. Modern high-bypass engines
also vary far less across the 100-150 kN band this map targets. Loading needs only
numpy + scipy + scikit-learn — no pycycle/openmdao at run time.
"""

import os
import pickle

import numpy as np

_DEFAULT_PKL = os.path.join(os.path.dirname(__file__), "data", "Turbofan_Engine_Model.pkl")


class TurbofanResponseSurface:
    """Overall-efficiency / TSFC / thrust-lapse response surface for a turbofan.

    Args:
        model_path: path to the ``.pkl``; defaults to the packaged artifact.

    Raises:
        FileNotFoundError: if no artifact is present. Unlike the turboshaft loader this
            does **not** fall back to a silent default efficiency — a missing map is a
            configuration error, and returning a plausible-looking number for it would
            corrupt a design without any sign that it had.
    """

    def __init__(self, model_path=None):
        path = model_path or _DEFAULT_PKL
        if not os.path.isfile(path):
            raise FileNotFoundError(
                f"No turbofan surrogate at {path!r}. Generate the map with "
                f"data/HBTF_turbofan.py (needs pycycle) and fit it with "
                f"train_turbofan_surrogate.py, or pass model_path to an existing artifact.")
        with open(path, "rb") as f:
            pkg = pickle.load(f)
        self.scaler_eff = pkg["scaler_eff"]      # inputs: [altitude_ft, mach, thrust_fraction]
        self.model_eff = pkg["model_eff"]
        self.model_tsfc = pkg["model_tsfc"]
        self.model_mdot_air3 = pkg.get("model_mdot_air3")
        self.model_mdot_inlet = pkg.get("model_mdot_inlet")
        self.model_bpr = pkg.get("model_bpr")
        self.scaler_lapse = pkg["scaler_lapse"]  # inputs: [altitude_ft, mach]
        self.model_lapse = pkg["model_lapse"]
        self.ref_fn = pkg.get("ref_fn")
        self.tag = pkg.get("tag", "unknown")
        # Training-domain box; inputs are clipped to it so an operating point the pyCycle
        # sweep never covered cannot send the RBF somewhere wild.
        self._ranges = pkg.get("input_ranges", {})

    # ------------------------------------------------------------------
    def _clip(self, name, value):
        lo_hi = self._ranges.get(name)
        if lo_hi is None:
            return float(value)
        return float(np.clip(value, lo_hi[0], lo_hi[1]))

    def thrust_lapse(self, altitude_ft, mach):
        """Full-throttle available thrust as a fraction of the SLS value."""
        x = np.array([[self._clip("alt_ft", altitude_ft), self._clip("Mach", mach)]])
        xs = self.scaler_lapse.transform(x)
        return float(np.clip(self.model_lapse(xs[0, 0], xs[0, 1]), 1e-3, 1.5))

    def core_air_flow(self, design_thrust_N, altitude_ft, mach, thrust_fraction):
        """Combustor-inlet (core, post-bleed) air mass flow [kg/s].

        Unlike the efficiency and TSFC surfaces this is **not** size-independent: it is the flow
        of the reference engine the map was generated for, scaled linearly by the ratio of the
        installed thrust to that engine's sea-level-static rating. Linear scaling with thrust is
        the usual first-order rubber-engine assumption and is good enough for reporting, not for
        sizing a flow path.

        This is the CORE flow at station 3, after the bypass split and the compressor bleeds.
        For the TOTAL flow the engine swallows use :meth:`inlet_air_flow` -- do not scale this
        one by (1 + BPR), because the bypass ratio is an off-design balance variable in the deck
        and varies across the envelope.
        """
        if self.model_mdot_air3 is None or not self.ref_fn:
            raise AttributeError(
                "this artifact carries no core-air-flow surface; regenerate it with "
                "train_turbofan_surrogate.py")
        x = np.array([[self._clip("alt_ft", altitude_ft), self._clip("Mach", mach),
                       self._clip("ThrustFraction", thrust_fraction)]])
        xs = self.scaler_eff.transform(x)
        mdot_ref = float(self.model_mdot_air3(xs[0, 0], xs[0, 1], xs[0, 2]))
        return mdot_ref * (design_thrust_N / self.ref_fn)

    def _surface(self, model, name, design_thrust_N, altitude_ft, mach, thrust_fraction,
                 scale_with_thrust):
        if model is None or (scale_with_thrust and not self.ref_fn):
            raise AttributeError(
                f"this artifact carries no {name} surface; regenerate it with "
                f"data/HBTF_turbofan.py and train_turbofan_surrogate.py")
        x = np.array([[self._clip("alt_ft", altitude_ft), self._clip("Mach", mach),
                       self._clip("ThrustFraction", thrust_fraction)]])
        xs = self.scaler_eff.transform(x)
        value = float(model(xs[0, 0], xs[0, 1], xs[0, 2]))
        return value * (design_thrust_N / self.ref_fn) if scale_with_thrust else value

    def inlet_air_flow(self, design_thrust_N, altitude_ft, mach, thrust_fraction):
        """TOTAL air mass flow through the inlet [kg/s] (core + bypass), size-scaled.

        Taken straight from the cycle's inlet station rather than reconstructed from the core
        flow, because the bypass ratio is solved off-design and is not a constant.
        """
        return self._surface(self.model_mdot_inlet, "inlet-air-flow", design_thrust_N,
                             altitude_ft, mach, thrust_fraction, True)

    def bypass_ratio(self, altitude_ft, mach, thrust_fraction):
        """Bypass ratio at the operating point [-]; size-independent, so no thrust scaling."""
        return self._surface(self.model_bpr, "bypass-ratio", 1.0,
                             altitude_ft, mach, thrust_fraction, False)

    def predict(self, design_thrust_N, altitude_ft, mach, required_thrust_N):
        """Return ``(eta_o, tsfc, thrust_avail_N, is_limited)`` at an operating point.

        ``tsfc`` is in kg/(N s). ``is_limited`` flags that the requested thrust exceeds what
        the engine can deliver at this condition; the efficiency is then reported at full
        throttle. The caller decides what to do about it (``report_class_ii_sizing``-style),
        exactly as the turboshaft path does.
        """
        if design_thrust_N is None or design_thrust_N <= 0:
            raise ValueError("design_thrust_N must be positive [N].")
        if not np.isfinite(required_thrust_N) or not np.isfinite(mach):
            raise ValueError(
                f"non-finite operating point: thrust={required_thrust_N}, mach={mach}")

        thrust_avail = design_thrust_N * self.thrust_lapse(altitude_ft, mach)

        is_limited = required_thrust_N > thrust_avail
        used = thrust_avail if is_limited else required_thrust_N
        frac = used / thrust_avail if thrust_avail > 0 else 0.0

        x = np.array([[self._clip("alt_ft", altitude_ft), self._clip("Mach", mach),
                       self._clip("ThrustFraction", frac)]])
        xs = self.scaler_eff.transform(x)
        eta = float(self.model_eff(xs[0, 0], xs[0, 1], xs[0, 2]))
        tsfc = float(self.model_tsfc(xs[0, 0], xs[0, 1], xs[0, 2]))
        # A physical overall efficiency; the bound is wide enough not to shape the answer,
        # narrow enough to catch an extrapolation that has gone nonsensical.
        eta = float(np.clip(eta, 0.01, 0.75))
        return eta, tsfc, thrust_avail, is_limited
