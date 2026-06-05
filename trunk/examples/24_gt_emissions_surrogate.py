"""Example 24 — Gas-turbine pollutant emissions from the state-dependent surrogate.

Beyond CO2, the gas turbine emits NOx, CO and unburned hydrocarbons (UHC), and the *emission
index* (g pollutant / kg fuel) varies strongly along the mission — high NOx at high power, high
CO/UHC at low power, both falling with altitude. PhlyGreen ships a **PW127 emission-index
response surface** ``EI(altitude, Mach, power)`` built offline from a pyCycle cycle + a Cantera
chemical-reactor-network calibrated to ICAO data (CO/UHC from the CRN; NOx anchored to the PW127
certification points). Select it with ``einox_model='Surrogate'``.

Run it:
    cd trunk && python examples/24_gt_emissions_surrogate.py
"""

import numpy as np

import PhlyGreen as pg
from common import traditional_config, savefig
from PhlyGreen.config import ClimateImpactConfig, WellToTankConfig
from PhlyGreen.Systems.Powertrain.emissions_surrogate import EmissionSurrogate


def _climate_config(einox_model):
    cfg = traditional_config()
    cfg.climate_impact = ClimateImpactConfig(H=100, N=1.6e7, Y=30, einox_model=einox_model,
                                             wtw_co2=8.30e-3, grid_co2=9.36e-2)
    cfg.well_to_tank = WellToTankConfig(eta_charge=0.95, eta_grid=1., eta_extraction=1.,
                                        eta_production=1., eta_transportation=0.25)
    return cfg


def main():
    # 1. The packaged surrogate itself: EI at a few operating points.
    es = EmissionSurrogate()      # packaged PW127 model (no path needed)
    print(f"emission surrogate: {es.tag}, inputs {es.inputs}")
    print(f"{'condition':18} {'alt_ft':>7} {'Mach':>5} {'power':>6}  {'EINOx':>6} {'EICO':>6} {'EIUHC':>6}")
    for label, (a, m, p) in {
        "take-off":      (0,     0.15, 1.00),
        "climb":         (8000,  0.30, 0.90),
        "cruise":        (26000, 0.45, 0.55),
        "descent/idle":  (10000, 0.35, 0.30),
    }.items():
        ei = es.predict_op(a, m, p)
        print(f"{label:18} {a:7.0f} {m:5.2f} {p:6.2f}  {ei['EINOX']:6.1f} {ei['EICO']:6.1f} {ei['EIUHC']:6.3f}")

    # 2. Mission emissions: surrogate (NOx/CO/UHC) vs the legacy Filippone NOx correlation.
    em = {}
    for model in ("Filippone", "Surrogate"):
        aircraft = pg.build_aircraft()
        aircraft.configure(_climate_config(model))
        aircraft.MissionType = "Continue"
        aircraft.climateimpact.calculate_mission_emissions()
        em[model] = dict(aircraft.climateimpact.mission_emissions)
    print("\n=== mission emitted mass [kg] ===")
    print(f"  NOx : Filippone {em['Filippone']['nox']:7.2f}  |  surrogate {em['Surrogate']['nox']:7.2f}")
    print(f"  CO  :      n/a            |  surrogate {em['Surrogate']['co']:7.2f}")
    print(f"  UHC :      n/a            |  surrogate {em['Surrogate']['uhc']:7.3f}")
    print("\nThe surrogate also gives CO and UHC (which Filippone does not), and its NOx reflects the"
          "\naltitude / part-power dependence of the emission index along the mission.")

    _plot_ei_surface(es)


def _plot_ei_surface(es):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    pf = np.linspace(0.30, 1.00, 30)
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    for alt in (0, 15000, 30000):
        nox = [es.predict_op(alt, 0.4, p)["EINOX"] for p in pf]
        ax.plot(pf * 100, nox, "o-", ms=3, label=f"{alt:,} ft")
    ax.set_xlabel("power fraction [%]"); ax.set_ylabel("EINOx [g/kg fuel]")
    ax.set_title("PW127 NOx emission index vs power and altitude (surrogate)")
    ax.grid(alpha=0.3); ax.legend(title="altitude")
    fig.tight_layout()
    print("\nFigures:")
    savefig(fig, "24_emission_index_surface.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
