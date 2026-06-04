"""Shared helpers for the PhlyGreen *learning* tutorials (``trunk/tutorials/``).

These notebooks are **educational**. They use the real PhlyGreen design API wherever a
capability exists, and fall back to small, *transparent* and clearly-labelled pedagogical
proxies where the full capability is not exposed (formal constraint feasibility, a non-CO2
climate weighting). Every proxy in this file is commented as such — it is a teaching device,
not a validated engineering model.

The functions here only exist to remove repetition across notebooks (path setup, a
crash-safe design call, a couple of config mutators, the closed-form Breguet equation and a
toy climate proxy). The heavy lifting always goes through the public API
(``PhlyGreen.run_design`` / ``PhlyGreen.evaluate``) and the baseline configs in
``examples/common.py``.
"""

import math
import os
import sys


# ---------------------------------------------------------------------------
# 0. Make the package and the example baselines importable from a notebook.
# ---------------------------------------------------------------------------
def add_examples_to_path():
    """Put ``trunk/examples`` (and this folder) on ``sys.path``.

    Lets a notebook do ``from common import traditional_config`` and
    ``from _learning_utils import ...`` regardless of whether it is launched from
    ``trunk/`` or from ``trunk/tutorials/``. Uses only *relative* locations resolved from
    this file — no hard-coded absolute paths.
    """
    here = os.path.dirname(os.path.abspath(__file__))      # .../trunk/tutorials
    trunk = os.path.dirname(here)                          # .../trunk
    for path in (here, os.path.join(trunk, "examples")):
        if os.path.isdir(path) and path not in sys.path:
            sys.path.insert(0, path)


# ---------------------------------------------------------------------------
# 1. A crash-safe design call (so a sweep marks infeasible points, not raises).
# ---------------------------------------------------------------------------
def safe_design(config):
    """Size an aircraft, returning ``(results | None, feasible, note)``.

    The PhlyGreen take-off-weight loop *raises* when a design cannot close (e.g. the battery
    is so heavy the weight loop diverges, or a constraint cannot be met). For a teaching
    sweep we want to *flag* such points as infeasible and keep going, rather than crash the
    whole notebook. ``feasible`` is ``True`` only if the design closed; ``note`` carries a
    short reason when it did not.
    """
    import PhlyGreen as pg
    try:
        res = pg.run_design(config)
        # A design that "closes" numerically but returns no take-off weight is still a fail.
        if res is None or res.WTO is None or not math.isfinite(res.WTO):
            return None, False, "no converged take-off weight"
        return res, True, ""
    except Exception as exc:                      # noqa: BLE001 — intentional broad catch
        return None, False, f"{type(exc).__name__}: {exc}"


# ---------------------------------------------------------------------------
# 2. Small config mutators used by more than one notebook.
# ---------------------------------------------------------------------------
def set_battery_specific_energy(config, wh_per_kg):
    """Set the (Class-I) battery cell specific energy [Wh/kg] on a hybrid config.

    This is the *cell/pack* specific energy the sizing model divides the required battery
    energy by. Note it is **not** the aircraft-level specific energy (see notebook 04).
    """
    config.cell.specific_energy = float(wh_per_kg)
    return config


def set_cruise_altitude(config, altitude_m):
    """Move the whole cruise to ``altitude_m`` and keep the profile self-consistent.

    Sets the cruise segment altitude, the end of the last climb and the start of the first
    descent to the same value, so the altitude timeline stays monotonic. Assumes the
    ``examples/common.py`` profile (a ``ConstantMachCruise`` cruise bracketed by a final
    ``ConstantRateClimb`` named ``Climb3`` and a ``ConstantRateDescent``).
    """
    alt = float(altitude_m)
    for seg in config.mission_stages.segments:
        if seg.segment_type == "ConstantMachCruise":
            seg.inputs["Altitude"] = alt
        elif seg.name == "Climb3":
            seg.inputs["EndAltitude"] = alt
        elif seg.segment_type == "ConstantRateDescent":
            seg.inputs["StartAltitude"] = alt
    return config


# ---------------------------------------------------------------------------
# 3. The Breguet range equation (closed form) — used by notebook 01.
# ---------------------------------------------------------------------------
def breguet_fuel_fraction(range_m, velocity_ms, overall_efficiency, lift_to_drag,
                          fuel_energy_J_per_kg=43.5e6, g=9.81):
    """Return the cruise fuel fraction ``Wf/W0`` from the energy form of Breguet.

    Uses the *energy-specific* form (handy when you think in efficiencies rather than SFC):

        R = (eta_overall / g) * (E_f / 1) * (L/D) * ln(W0 / W1)

    so the cruise weight ratio is ``W0/W1 = exp( R * g / (eta * E_f * L/D) )`` and the fuel
    fraction is ``Wf/W0 = 1 - W1/W0``. ``velocity_ms`` is accepted for completeness /
    teaching symmetry but cancels in the energy form.

    Args:
        range_m: cruise range [m].
        velocity_ms: cruise true airspeed [m/s] (informational here).
        overall_efficiency: thermal x transmission x propulsive efficiency [-].
        lift_to_drag: cruise L/D [-].
        fuel_energy_J_per_kg: fuel lower heating value [J/kg] (Jet-A ~ 43.5e6).
        g: gravity [m/s^2].
    """
    weight_ratio = math.exp(range_m * g / (overall_efficiency * fuel_energy_J_per_kg * lift_to_drag))
    return 1.0 - 1.0 / weight_ratio


def breguet_range(fuel_fraction, overall_efficiency, lift_to_drag,
                  fuel_energy_J_per_kg=43.5e6, g=9.81):
    """Inverse of :func:`breguet_fuel_fraction`: range [m] for a given fuel fraction."""
    weight_ratio = 1.0 / (1.0 - fuel_fraction)
    return overall_efficiency * fuel_energy_J_per_kg * lift_to_drag / g * math.log(weight_ratio)


# ---------------------------------------------------------------------------
# 4. A *pedagogical* climate proxy — used by notebook 06.
# ---------------------------------------------------------------------------
# WARNING — TEACHING PROXY, NOT A VALIDATED CLIMATE MODEL.
# Real non-CO2 aviation forcing (persistent contrails, contrail cirrus, altitude-amplified
# NOx ozone production) depends on the local atmospheric state (temperature, ice
# super-saturation), not on a single number. The crude monotonic curve below only captures
# the *qualitative* fact that non-CO2 effects grow with cruise altitude in the upper
# troposphere. Use it to reason about trade-offs, never to quote a figure.
def nonco2_multiplier(altitude_m, base=0.2, top=2.2, ceiling_m=9500.0):
    """Illustrative non-CO2 'effective forcing' multiplier vs cruise altitude [-].

    Rises roughly linearly from ``base`` near the ground to ``top`` at ``ceiling_m`` — a
    stand-in for the way contrail/NOx climate forcing intensifies at higher, colder cruise
    altitudes. Clearly a teaching device (see module warning above).
    """
    frac = max(0.0, min(1.0, altitude_m / ceiling_m))
    return base + (top - base) * frac


def climate_proxy(block_fuel_kg, altitude_m, co2_per_kg_fuel=3.16):
    """Illustrative total-climate proxy in 'CO2-equivalent kg' for one mission.

    Combines the well-mixed CO2 from burning the fuel (``~3.16 kg CO2 / kg Jet-A``) with the
    altitude-dependent non-CO2 multiplier from :func:`nonco2_multiplier`:

        climate ~ CO2_fuel * (1 + nonco2_multiplier(altitude))

    So two designs with the *same* fuel burn can have different climate impact purely
    because they cruise at different altitudes — the whole point of notebook 06. Pedagogical
    only.
    """
    co2 = block_fuel_kg * co2_per_kg_fuel
    return co2 * (1.0 + nonco2_multiplier(altitude_m))
