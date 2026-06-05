"""Design execution: thin, cached, crash-safe wrappers around the public PhlyGreen API.

``run_design`` in the package is already a pure function (fresh aircraft per call, input never
mutated). Here we add only what a GUI needs on top: keep the *live aircraft* around (the
``postprocess`` plotters need it), turn a non-converging design into a friendly message instead
of a traceback, and memoize scalar results so a parameter sweep / architecture comparison does
not re-size an identical design twice.

No streamlit import here, so this module is unit-testable on its own.
"""

import json
import warnings

import PhlyGreen as pg

from templates import config_to_dict, clone
from controls import apply_overrides


def config_key(config):
    """A stable string key for a config (used to memoize and to cache in session state)."""
    return json.dumps(config_to_dict(config), sort_keys=True, default=str)


def design(config):
    """Build, configure and size an aircraft from a (copy of a) config; return the live aircraft.

    Mirrors ``pg.run_design`` but returns the aircraft instead of only the results, so the
    GUI can call the ``postprocess`` plotters on it. Warnings (e.g. Class-II power-limited
    notes) are silenced — the dashboard reports the sizing explicitly.
    """
    aircraft = pg.build_aircraft()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        aircraft.configure(clone(config))
    return aircraft


def safe_design(config):
    """Return ``(aircraft, error)``; ``error`` is a short message when the design did not close."""
    try:
        return design(config), None
    except Exception as exc:                      # noqa: BLE001 — surface, don't crash the UI
        return None, _friendly_error(exc)


def _friendly_error(exc):
    msg = str(exc)
    if "did not converge" in msg or "did not close" in msg:
        return ("The design did not close (the take-off weight loop diverged). Try a shorter "
                "range, a lighter payload, a higher battery specific energy, or — for hydrogen — "
                "a higher stack power density / lower design voltage.")
    return f"{type(exc).__name__}: {msg}"


# --- memoized scalar results (for sweeps / comparisons) ---------------------------------------
_RESULTS_CACHE = {}
_CACHE_CAP = 512


def results_dict(config):
    """Size the design and return ``AircraftResults.to_dict()`` (memoized on the config).

    Raises on a non-converging design — callers that want graceful handling use
    :func:`safe_results_dict`.
    """
    key = config_key(config)
    if key in _RESULTS_CACHE:
        return _RESULTS_CACHE[key]
    aircraft = design(config)
    res = aircraft.results().to_dict()
    if len(_RESULTS_CACHE) < _CACHE_CAP:
        _RESULTS_CACHE[key] = res
    return res


def safe_results_dict(config):
    try:
        return results_dict(config), None
    except Exception as exc:                      # noqa: BLE001
        return None, _friendly_error(exc)


def sweep(base_config, knob, values):
    """Size ``base_config`` for each value of one :class:`controls.Knob`.

    Returns a list of rows ``{'x': value, 'ok': bool, 'results': dict|None, 'error': str|None}``,
    using the knob's setter (the same one the Design tab uses).
    """
    rows = []
    for x in values:
        cfg = clone(base_config)
        knob.setter(cfg, x)
        res, err = safe_results_dict(cfg)
        rows.append({"x": float(x), "ok": err is None, "results": res, "error": err})
    return rows


def compare(labels_and_configs):
    """Size several designs; return ``[{'label', 'ok', 'results', 'error'}, ...]``."""
    out = []
    for label, cfg in labels_and_configs:
        res, err = safe_results_dict(cfg)
        out.append({"label": label, "ok": err is None, "results": res, "error": err})
    return out


# convenience: apply the Design-tab knob values, then size, in one call
def design_with_overrides(base_config, overrides):
    """Return ``(aircraft, error, config)`` for ``base_config`` with knob ``overrides`` applied."""
    cfg = apply_overrides(clone(base_config), overrides)
    aircraft, error = safe_design(cfg)
    return aircraft, error, cfg
