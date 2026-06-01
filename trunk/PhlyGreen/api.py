"""A small, stateless API for driving the aircraft model from outer loops.

Optimization, uncertainty quantification and parameter sweeps all need the same thing: a
*pure function* that maps a design specification to results, with no shared state between
calls so it is safe to run in a loop (or in parallel). That is :func:`run_design`.

:func:`evaluate` adds the usual outer-loop pattern: take a baseline config, apply some
parameters to a fresh copy of it, design, and return the results — without ever mutating
the baseline.
"""

import copy

from .factory import build_aircraft


def run_design(config, design=True):
    """Build, configure and (by default) size an aircraft from a typed config.

    This is a pure function: it works on a deep copy of ``config`` and builds a fresh
    aircraft each call, so repeated calls are independent and the input is never mutated.

    Args:
        config (AircraftConfig): the design specification.
        design (bool): run the full ``DesignAircraft`` sizing loop (True) or only
            ``ReadInput`` (False).

    Returns:
        AircraftResults: the structured design outcome.
    """
    cfg = copy.deepcopy(config)
    aircraft = build_aircraft()
    aircraft.configure(cfg, design=design)
    return aircraft.results()


def evaluate(base_config, apply, x, design=True):
    """Evaluate the design for parameter set ``x`` applied to a copy of ``base_config``.

    Args:
        base_config (AircraftConfig): the baseline, left untouched.
        apply (callable): ``apply(config, x)`` mutates the *copy* to encode ``x`` (e.g.
            set a cruise altitude, a hybridization ratio, a wing aspect ratio, ...).
        x: the parameter(s) for this evaluation (scalar, array, dict — your choice).
        design (bool): forwarded to :func:`run_design` semantics.

    Returns:
        AircraftResults: results for this parameter set.
    """
    cfg = copy.deepcopy(base_config)
    apply(cfg, x)
    aircraft = build_aircraft()
    aircraft.configure(cfg, design=design)
    return aircraft.results()
