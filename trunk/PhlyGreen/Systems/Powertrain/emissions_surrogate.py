"""Gas-turbine EMISSION-INDEX response surface — runtime loader.

Companion to :mod:`.gas_turbine_surrogate`. Where that model returns thermal efficiency at an
operating point, this one returns **emission indices** (EINOx, EICO, EIUHC) [g/kg fuel] at an
operating point, so the mission can integrate ``EI x fuel_flow`` into emitted mass — a
state-dependent alternative to the Filippone NOx correlation in
:class:`PhlyGreen.ClimateImpact.ClimateImpact`.

Provenance / how the surrogate is built (offline): a Chemical Reactor Network (CRN, Cantera)
calibrated to ICAO LTO data produces emission indices as a function of the combustor inlet
state, and a pyCycle engine deck maps the operating point ``(altitude, Mach, power fraction)``
to that combustor state. Fitting EI over either the combustor state or directly over
``(alt, Mach, power fraction)`` gives the response surface this class loads. The packaging
format (a dict of ``StandardScaler`` + scipy ``Rbf`` / scikit-learn estimators per output)
mirrors :mod:`.train_gas_turbine_surrogate`.

**Two artifacts ship.** ``Emission_Model_PW127.pkl`` is the turboprop map (certification-
anchored NOx) that backs the universal turboshaft map; ``Emission_Model_Turbofan.pkl`` is the
CFM56-class map built from the native CFM56 CRN calibration, keyed on **thrust** fraction rather
than shaft-power fraction. Pick one with :func:`default_model_path` or an explicit
``model_path``; a combustor calibration is engine-specific and the two are not interchangeable.
"""

import os
import pickle

import numpy as np

_DATA = os.path.join(os.path.dirname(__file__), "data")
_DEFAULT_PKL = os.path.join(_DATA, "Emission_Model_PW127.pkl")       # turboprop (shaft-power fraction)
_TURBOFAN_PKL = os.path.join(_DATA, "Emission_Model_Turbofan.pkl")   # CFM56-class (thrust fraction)


def default_model_path(configuration=None):
    """Artifact for an aircraft configuration.

    A combustor calibration does not transfer between engine classes -- the turboprop map is a
    lean, staged combustor keyed on shaft-power fraction; the turbofan map is a single-annular
    CFM56-class combustor keyed on thrust fraction. Selecting by configuration keeps a caller
    from silently getting the wrong one.
    """
    return _TURBOFAN_PKL if configuration == "Turbofan" else _DEFAULT_PKL


class EmissionSurrogate:
    """Emission-index response surface loaded from a serialized package.

    The package is a dict ``{"inputs": [...], "outputs": [...], "models": {out: entry}}`` where
    each ``entry`` is ``{"kind": "rbf"|"rf", "scaler": StandardScaler, "model": ..., "log": bool}``
    — the format written by the offline fitter. ``inputs`` are the feature columns in order
    (e.g. ``["alt_ft", "Mach", "PC"]`` for the direct map, or the combustor-state columns).

    Args:
        model_path: path to the ``.pkl``. Defaults to the (not-yet-shipped) PW127 artifact; a
            clear error is raised if absent so the caller supplies the scaffold path explicitly.
    """

    def __init__(self, model_path=None):
        path = model_path or _DEFAULT_PKL
        if not os.path.isfile(path):
            raise FileNotFoundError(
                f"No emission-index surrogate at {path!r}. Build it with "
                f"emissions_pipeline/build_pw127_surrogate.py (turboprop) or "
                f"build_turbofan_surrogate.py (CFM56-class turbofan), or pass model_path to an "
                f"existing artifact.")
        with open(path, "rb") as f:
            pkg = pickle.load(f)
        self.inputs = list(pkg["inputs"])
        self.outputs = list(pkg["outputs"])
        self._models = pkg["models"]
        self.tag = pkg.get("tag", "unknown")
        # Training-domain box; predictions are clipped to it to avoid wild extrapolation at
        # operating points the CRN dataset never covered (e.g. ground-static idle).
        self._ranges = pkg.get("input_ranges")
        self.loaded = True

    # --- core ------------------------------------------------------------------------------
    def _clip(self, X):
        X = np.atleast_2d(np.asarray(X, float)).copy()
        if self._ranges:
            for j, col in enumerate(self.inputs):
                lo, hi = self._ranges[col]
                X[:, j] = np.clip(X[:, j], lo, hi)
        return X

    def _predict_entry(self, entry, Xs_clipped):
        Xs = entry["scaler"].transform(Xs_clipped)
        m = entry["model"]
        y = m(*Xs.T) if entry["kind"] == "rbf" else m.predict(Xs)
        return 10.0 ** y if entry["log"] else y

    def predict(self, X):
        """Return ``{output: ndarray}`` for inputs ``X`` (shape ``(n, n_inputs)`` or ``(n_inputs,)``)
        with columns in ``self.inputs`` order. Inputs are clipped to the training domain."""
        Xc = self._clip(X)
        return {o: self._predict_entry(self._models[o], Xc) for o in self.outputs}

    # --- convenience for the direct (alt, Mach, power-fraction) map ------------------------
    def predict_op(self, altitude_ft, mach, power_fraction):
        """Emission indices [g/kg fuel] at one operating point (direct-map artifacts only).

        Returns a plain ``{output: float}``. Requires the artifact's inputs to be
        ``["alt_ft", "Mach", "PC"]`` (the operating-point map). For combustor-state artifacts,
        use :meth:`predict` with the state vector instead.
        """
        expected = ["alt_ft", "Mach", "PC"]
        if self.inputs != expected:
            raise ValueError(
                f"predict_op expects a direct (alt, Mach, power) map with inputs {expected}; "
                f"this artifact has inputs {self.inputs}. Use predict(X) instead.")
        out = self.predict([float(altitude_ft), float(mach), float(power_fraction)])
        return {k: float(np.ravel(v)[0]) for k, v in out.items()}
