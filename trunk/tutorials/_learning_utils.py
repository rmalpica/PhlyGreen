"""Shared helpers for the PhlyGreen *learning* tutorials (``trunk/tutorials/``).

These notebooks are **educational**. They use the real PhlyGreen design API wherever a
capability exists, and fall back to a small, *transparent* and clearly-labelled pedagogical
proxy only where the full capability is not exposed (a formal constraint-feasibility map in
notebook 02). Climate impact (notebook 06) uses PhlyGreen's real ClimateImpact model — no
proxy.

The functions here only exist to remove repetition across notebooks (path setup, a
crash-safe design call, a couple of config mutators, the closed-form Breguet equation and
thin wrappers around the real climate model). The heavy lifting always goes through the
public API (``PhlyGreen.run_design`` / ``PhlyGreen.evaluate``) and the baseline configs in
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

    The climb is several stacked ``ConstantRateClimb`` segments. To retarget the cruise for any
    number of segments, linearly rescale every climb segment's start/end altitude from the
    template climb span ``[ground, top]`` to ``[ground, altitude_m]`` so the breakpoints stay in
    proportion and the climb stays monotonic; the cruise altitude and the top of the descent are
    set to ``altitude_m`` too.
    """
    alt = float(altitude_m)
    climbs = [s for s in config.mission_stages.segments if s.segment_type == "ConstantRateClimb"]
    if climbs:
        lo = min(s.inputs["StartAltitude"] for s in climbs)
        hi = max(s.inputs["EndAltitude"] for s in climbs)
        span = (hi - lo) or 1.0
        for s in climbs:
            s.inputs["StartAltitude"] = lo + (s.inputs["StartAltitude"] - lo) / span * (alt - lo)
            s.inputs["EndAltitude"] = lo + (s.inputs["EndAltitude"] - lo) / span * (alt - lo)
    for seg in config.mission_stages.segments:
        if seg.segment_type == "ConstantMachCruise":
            seg.inputs["Altitude"] = alt
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
# 4. PhlyGreen's *real* climate-impact model — used by notebook 06.
# ---------------------------------------------------------------------------
# No proxy here: notebook 06 uses PhlyGreen's ClimateImpact module, which models real
# gas-turbine emissions (CO2, H2O, SO4, soot and NOx/CO/UHC from the
# PW127 gas-turbine emission-index surrogate), the radiative forcing of every species
# (including altitude-dependent NOx-ozone chemistry and persistent contrails / AIC), and
# rolls them into an Average Temperature Response (ATR). The two helpers below just make it
# easy to attach the model to a config and to read the ATR out of a designed aircraft.
def attach_climate_model(config, einox_model='Surrogate', H=100, N=1.6e7, Y=30,
                         wtw_co2=8.30e-3, grid_co2=9.36e-2):
    """Attach PhlyGreen's real ClimateImpact (+ WellToTank) inputs to ``config``.

    Lets a kerosene (Traditional) design compute its mission emissions and ATR with the
    *same* machinery as ``examples/14`` — no proxy. ``einox_model='Surrogate'`` (default) uses
    the PW127 gas-turbine emission-index response surface for NOx/CO/UHC; ``'Filippone'`` is the
    legacy NOx correlation. ``H``/``N``/``Y`` are the climate
    time horizon, flights per year and operative years; ``wtw_co2``/``grid_co2`` the
    well-to-wake fuel and grid CO2 intensities. Defaults match the hybrid baseline in
    ``examples/common.py``.
    """
    from PhlyGreen.config import ClimateImpactConfig, WellToTankConfig
    config.climate_impact = ClimateImpactConfig(H=H, N=N, Y=Y, einox_model=einox_model,
                                                wtw_co2=wtw_co2, grid_co2=grid_co2)
    config.well_to_tank = WellToTankConfig(eta_charge=0.95, eta_grid=1., eta_extraction=1.,
                                           eta_production=1., eta_transportation=0.25)
    return config


def climate_atr(aircraft, co2_only=False):
    """Return the Average Temperature Response [K] of a *designed* aircraft.

    Computes the mission emissions on first call. With ``co2_only=True`` it temporarily
    restricts the total radiative forcing to the CO2 term, so you can compare the full
    (CO2 + non-CO2) ATR against the CO2-only ATR and read off how much warming a
    *CO2-only* accounting would miss. The aircraft must carry a ClimateImpact model (see
    :func:`attach_climate_model`).
    """
    ci = aircraft.climateimpact
    if not ci.mission_emissions_calculated:
        aircraft.MissionType = 'Continue'
        ci.calculate_mission_emissions()
    if not co2_only:
        return ci.ATR()
    original_rf = ci.rf
    ci.rf = lambda year: ci.rf_co2(year)     # isolate the well-mixed CO2 forcing
    try:
        return ci.ATR()
    finally:
        ci.rf = original_rf


def climate_co2_equivalent(aircraft):
    """Mission CO2-equivalent mass [kg] = CO2 x (full ATR / CO2-only ATR).

    Expresses the *total* climate impact (CO2 + the non-CO2 effects the emission model and the
    ClimateImpact radiative-forcing machinery capture — NOx-ozone, contrails, ...) as an
    equivalent mass of CO2, by scaling the emitted CO2 by the ratio of the full to the CO2-only
    Average Temperature Response. Uses whichever NOx model the config selected (with
    ``attach_climate_model`` that is the PW127 emission surrogate).
    """
    ci = aircraft.climateimpact
    if not ci.mission_emissions_calculated:
        aircraft.MissionType = 'Continue'
        ci.calculate_mission_emissions()
    co2 = ci.mission_emissions['co2']
    full = climate_atr(aircraft, co2_only=False)
    co2_only = climate_atr(aircraft, co2_only=True)
    uplift = full / co2_only if co2_only else 1.0
    return co2 * uplift, uplift
