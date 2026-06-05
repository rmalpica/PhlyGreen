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


# (a) CO₂ intensity [g CO₂e / MJ of delivered energy].
WTW_CO2 = {"jetA": 89.0, "saf": 20.0, "h2_green": 5.0, "grid": 56.0}
# (b) Well-to-tank ENERGY ratio [primary energy in / delivered energy out].
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


# --- gas-turbine non-CO₂ (NOx-ozone, contrails) via the emission surrogate + ATR ----------------
def _attach_climate(cfg):
    from PhlyGreen.config import ClimateImpactConfig, WellToTankConfig
    cfg.climate_impact = ClimateImpactConfig(H=100, N=1.6e7, Y=30, einox_model="Surrogate",
                                             wtw_co2=8.30e-3, grid_co2=9.36e-2)
    cfg.well_to_tank = WellToTankConfig(eta_charge=0.95, eta_grid=1., eta_extraction=1.,
                                        eta_production=1., eta_transportation=0.25)
    return cfg


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


def gt_nonco2_co2e(cfg):
    """Absolute non-CO₂ CO₂-equivalent [kg] of a gas-turbine design (0 for fuel-cell architectures).

    Sizes a climate-attached copy of the design (the emission surrogate gives NOx/CO/UHC over the
    mission), then returns ``co2 · (ATR_full/ATR_CO2only − 1)`` — the part of the warming the CO₂
    number alone misses. Returns 0.0 on any failure, so the comparison never crashes.
    """
    if cfg.configuration not in _GT_CONFIGS:
        return 0.0
    try:
        c = _attach_climate(copy.deepcopy(cfg))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            aircraft = pg.build_aircraft()
            aircraft.configure(c)
            ci = aircraft.climateimpact
            aircraft.MissionType = "Continue"
            ci.calculate_mission_emissions()
            co2 = ci.mission_emissions["co2"]
            full = _climate_atr(aircraft, co2_only=False)
            co2_only = _climate_atr(aircraft, co2_only=True)
        uplift = full / co2_only if co2_only else 1.0
        return float(co2 * (uplift - 1.0))
    except Exception:
        return 0.0
