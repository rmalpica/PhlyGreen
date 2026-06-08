"""Well-to-wake energy / CO₂ accounting and gas-turbine CO₂-equivalent for the Compare tab.

Mirrors the *learning* tutorial ``03_compare_propulsion_architectures_same_mission``: PhlyGreen's
ClimateImpact module only prices a kerosene-burning gas turbine, so to compare carriers as
different as Jet-A, hydrogen and grid electricity on one footing we use **illustrative lifecycle
intensity factors** (not a physics model — change them and the ranking changes; that is the
lesson). The gas-turbine **non-CO₂** effect (NOx-ozone, contrails) is taken from the real
PW127 emission surrogate + the ATR machinery.

No streamlit import — pure computation, callable from ``runner``.
"""

import copy
import warnings

import PhlyGreen as pg


# (a) Well-to-wake CO₂ intensity [g CO₂e / MJ of delivered energy].
WTW_CO2 = {"jetA": 89.0, "saf": 20.0, "h2_green": 5.0, "grid": 56.0}
# (b) Tank-to-wake (combustion / use) CO₂ [g CO₂ / MJ] — the part emitted onboard. The rest of the
# well-to-wake total is well-to-tank (upstream). Jet-A combustion ≈ 3.16 kgCO₂/kg / 43.2 MJ/kg;
# SAF is biogenic (net ≈ 0 at the tailpipe); hydrogen (fuel cell) and grid electricity emit nothing
# onboard, so all their CO₂ is upstream.
TTW_CO2 = {"jetA": 73.2, "saf": 0.0, "h2_green": 0.0, "grid": 0.0}
# (c) Well-to-tank ENERGY ratio [primary energy in / delivered energy out].
WTT_ENERGY = {"jetA": 1.18, "saf": 2.7, "h2_green": 2.0, "grid": 1.15}

# Which fuel carrier each lab template burns (battery share is always 'grid' electricity).
CARRIER = {
    "Traditional turboprop": "jetA",
    "Hybrid GT + battery": "jetA",
    "Hydrogen fuel cell": "h2_green",
    "Hybrid fuel cell + battery": "h2_green",
}

_GT_CONFIGS = ("Traditional", "Hybrid")     # architectures with a kerosene gas turbine


def _battery_specific_energy(cfg):
    cell = getattr(cfg, "cell", None)
    if cell is not None and cell.specific_energy:
        return cell.specific_energy
    return getattr(cfg.energy, "battery_specific_energy", 0.0) or 0.0


def _onboard_energy(aircraft, cfg):
    """Onboard chemical and electrical energy [MJ] -> ``(e_fuel, e_batt)``."""
    w = aircraft.weight
    fuel = getattr(w, "WH2_Fuel", None) or getattr(w, "Wf", 0.0) or 0.0   # H2 if present, else fuel
    batt = getattr(w, "WBat", 0.0) or 0.0
    e_fuel = fuel * cfg.energy.Ef / 1e6                                    # chemical [MJ]
    e_batt = batt * _battery_specific_energy(cfg) * 3600.0 / 1e6          # electrical [MJ]
    return e_fuel, e_batt


def wtw_breakdown(label, aircraft, cfg, wtw_co2=None, ttw_co2=None, wtt_energy=None, nonco2=None):
    """Well-to-wake energy / CO₂ / CO₂-equivalent split into well-to-tank (WTT, upstream) and
    tank-to-wake (TTW, onboard use), using the illustrative carrier intensity factors.

    Energy: TTW is the energy delivered to (and used from) the tank; WTT is the extra primary energy
    burned upstream to produce and deliver it. CO₂: TTW is what is emitted onboard (combustion); WTT
    is the upstream production/transport. CO₂e adds the gas-turbine non-CO₂ effect (a TTW,
    combustion-driven term) from the PW127 emission surrogate + the ATR model.

    ``wtw_co2`` / ``ttw_co2`` / ``wtt_energy`` override the carrier factor dicts (so the user can
    edit the lifecycle assumptions); ``nonco2`` overrides the (expensive) gas-turbine non-CO₂ term
    so the breakdown can be recomputed instantly while the factors are edited.
    """
    WTW = wtw_co2 if wtw_co2 is not None else WTW_CO2
    TTW = ttw_co2 if ttw_co2 is not None else TTW_CO2
    WTTE = wtt_energy if wtt_energy is not None else WTT_ENERGY

    e_fuel, e_batt = _onboard_energy(aircraft, cfg)
    carrier = CARRIER.get(label, "jetA")
    r_fuel, r_grid = WTTE[carrier], WTTE["grid"]

    ttw_e = e_fuel + e_batt                                   # delivered / used onboard [MJ]
    wtt_e = e_fuel * (r_fuel - 1.0) + e_batt * (r_grid - 1.0)  # upstream production overhead [MJ]

    ttw_co2 = (e_fuel * TTW[carrier]) / 1000.0               # combustion only (battery emits none)
    wtt_co2 = (e_fuel * (WTW[carrier] - TTW[carrier])
               + e_batt * WTW["grid"]) / 1000.0               # upstream fuel + grid electricity

    if nonco2 is None:
        nonco2 = gt_nonco2_co2e(cfg)                         # GT non-CO₂ (NOx-ozone, contrails) [kg]
    return {
        "wtt_MJ": wtt_e, "ttw_MJ": ttw_e, "wtw_MJ": wtt_e + ttw_e,
        "wtt_co2": wtt_co2, "ttw_co2": ttw_co2, "wtw_co2": wtt_co2 + ttw_co2,
        "nonco2": nonco2,
        "wtt_co2e": wtt_co2, "ttw_co2e": ttw_co2 + nonco2, "wtw_co2e": wtt_co2 + ttw_co2 + nonco2,
    }


def wtw_metrics(label, aircraft, cfg):
    """Return ``(onboard_MJ, well_to_wake_MJ, co2_kg)`` for a sized design (illustrative factors)."""
    w = aircraft.weight
    fuel = getattr(w, "WH2_Fuel", None) or getattr(w, "Wf", 0.0) or 0.0      # H2 if present, else fuel
    batt = getattr(w, "WBat", 0.0) or 0.0
    e_fuel = fuel * cfg.energy.Ef / 1e6                                       # onboard chemical [MJ]
    e_batt = batt * _battery_specific_energy(cfg) * 3600.0 / 1e6             # onboard electrical [MJ]
    carrier = CARRIER.get(label, "jetA")
    wtw = e_fuel * WTT_ENERGY[carrier] + e_batt * WTT_ENERGY["grid"]
    co2 = (e_fuel * WTW_CO2[carrier] + e_batt * WTW_CO2["grid"]) / 1000.0     # kg CO₂e
    return e_fuel + e_batt, wtw, co2


# --- gas-turbine pollutant emissions (CO, NOx, UHC) + non-CO₂ (NOx-ozone, contrails) -------------
EINOX_MODELS = ("Surrogate", "Filippone")    # NOx (and, for Surrogate, CO/UHC) emission models


def attach_climate(cfg, einox_model="Surrogate"):
    """Ensure ``cfg`` carries a climate-impact + well-to-tank section so that *designing* it
    yields a climate-ready aircraft (emissions computable without a second sizing pass).

    Preserves whatever the template already set; only (re)sets the EINOx model. Mutates and
    returns ``cfg``.
    """
    from PhlyGreen.config import ClimateImpactConfig, WellToTankConfig
    if cfg.climate_impact is None:
        cfg.climate_impact = ClimateImpactConfig(H=100, N=1.6e7, Y=30, einox_model=einox_model,
                                                 wtw_co2=8.30e-3, grid_co2=9.36e-2)
    else:
        cfg.climate_impact.einox_model = einox_model
    if cfg.well_to_tank is None:
        cfg.well_to_tank = WellToTankConfig(eta_charge=0.95, eta_grid=1., eta_extraction=1.,
                                            eta_production=1., eta_transportation=0.25)
    return cfg


# Backwards-compatible private alias (older callers).
_attach_climate = attach_climate


def _climate_atr(aircraft, co2_only=False):
    ci = aircraft.climateimpact
    if not ci.mission_emissions_calculated:
        aircraft.MissionType = "Continue"
        ci.calculate_mission_emissions()
    if not co2_only:
        return ci.ATR()
    original_rf = ci.rf
    ci.rf = lambda year: ci.rf_co2(year)        # restrict the forcing to the CO₂ term
    try:
        return ci.ATR()
    finally:
        ci.rf = original_rf


def gt_emissions(cfg, einox_model="Surrogate", aircraft=None):
    """Mission gas-turbine emissions for a gas-turbine design (``Traditional`` / ``Hybrid``).

    Returns the mission masses ``nox`` / ``co`` / ``uhc`` [kg] (``None`` when the model does not
    provide them) plus the non-CO₂ CO₂-equivalent ``nonco2`` [kg] (NOx-ozone + contrails, from
    ``co2 · (ATR_full/ATR_CO2only − 1)``). Returns zero/None entries for non-gas-turbine
    architectures or on any failure (so callers never crash).

    If ``aircraft`` is given it must be an **already-sized, climate-attached** design (built from a
    config passed through :func:`attach_climate`): the emissions are read off that existing mission
    solution — no second take-off-weight sizing. If ``aircraft`` is ``None`` a climate-attached copy
    of ``cfg`` is sized here (the slow path, kept for standalone callers).
    """
    blank = {"nox": None, "co": None, "uhc": None, "nonco2": 0.0}
    if cfg.configuration not in _GT_CONFIGS:
        return blank
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            if aircraft is None:
                c = attach_climate(copy.deepcopy(cfg), einox_model)
                aircraft = pg.build_aircraft()
                aircraft.configure(c)
            ci = aircraft.climateimpact
            aircraft.MissionType = "Continue"
            ci.calculate_mission_emissions()
            em = ci.mission_emissions
            full = _climate_atr(aircraft, co2_only=False)
            co2_only = _climate_atr(aircraft, co2_only=True)
        uplift = full / co2_only if co2_only else 1.0
        return {
            "nox": _scalar(em.get("nox")), "co": _scalar(em.get("co")), "uhc": _scalar(em.get("uhc")),
            "nonco2": float(_scalar(em.get("co2", 0.0)) * (uplift - 1.0)),
        }
    except Exception:
        return blank


def _scalar(v):
    """Coerce a possibly-array emission total to a float (or None)."""
    if v is None:
        return None
    try:
        import numpy as np
        return float(np.sum(v))
    except Exception:
        try:
            return float(v)
        except Exception:
            return None


def gt_nonco2_co2e(cfg, einox_model="Surrogate", aircraft=None):
    """Absolute non-CO₂ CO₂-equivalent [kg] of a gas-turbine design (0 for fuel-cell architectures).

    Pass an already-sized, climate-attached ``aircraft`` to reuse its mission solution instead of
    sizing a fresh design (see :func:`gt_emissions`).
    """
    return gt_emissions(cfg, einox_model, aircraft=aircraft)["nonco2"]
