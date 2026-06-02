"""Example 20 — Size a hydrogen fuel-cell aircraft and fly the full mission.

A pure fuel-cell electric aircraft: no battery, no gas turbine. The fuel cell turns
hydrogen into electricity, which drives the propeller through a motor and gearbox. Sizing
finds the take-off weight at which structure + fuel-cell system + hydrogen + tank + cooling
+ payload + crew add up consistently, while the full mission is flown segment by segment
through the cell's polarization physics.

Run it:
    cd trunk && python examples/20_hydrogen_fuel_cell.py
"""

import PhlyGreen as pg
from common import hydrogen_config, print_results, design_dashboard, savefig


def main():
    aircraft = pg.build_aircraft()
    aircraft.configure(hydrogen_config())     # size + fly the mission

    fc = aircraft.fuelcell

    # Full design summary (the mass breakdown now includes the H2 tank and cooling).
    print_results(aircraft, "Hydrogen fuel-cell aircraft")

    print("\n--- Fuel-cell stack ---")
    print(f"Rated net power    : {fc.P_fc_rated/1000:9.1f} kW")
    print(f"Number of cells    : {fc.N_cells:9d}")
    print(f"Design cell voltage: {fc.V_cell_design:9.3f} V")
    print(f"Active area / cell  : {fc.A_cell_reale:9.1f} cm^2")

    # The polarization curve is the heart of the model: cell voltage vs current density.
    print("\nPolarization curve (at the design pressure):")
    print(f"{'i [A/cm^2]':>10} {'V_cell [V]':>10}")
    for i_dens in (0.1, 0.5, 1.0, 1.5, 2.0):
        print(f"{i_dens:10.2f} {fc.PolarizationCurve(i_dens, fc.Target_Press):10.3f}")

    print("\nFigures:")
    _plot_polarization(fc)
    design_dashboard(aircraft, "20_hydrogen_dashboard.png", "Hydrogen fuel-cell design")


def _plot_polarization(fc):
    """Plot the polarization curve and the resulting power-density curve."""
    try:
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    i = np.linspace(0.02, 2.0, 120)
    v = np.array([fc.PolarizationCurve(x, fc.Target_Press) for x in i])
    p = i * v                                   # power density [W/cm^2]
    fig, ax = plt.subplots(figsize=(7.5, 5))
    ax.plot(i, v, color="tab:blue", label="cell voltage")
    ax.axvline(fc.i_rated if hasattr(fc, "i_rated") else np.nan, ls=":", c="grey")
    ax.set_xlabel("current density [A/cm$^2$]"); ax.set_ylabel("cell voltage [V]", color="tab:blue")
    ax2 = ax.twinx()
    ax2.plot(i, p, color="tab:red", ls="--", label="power density")
    ax2.set_ylabel("power density [W/cm$^2$]", color="tab:red")
    ax.set_title("Fuel-cell polarization & power density"); ax.grid(alpha=0.3)
    fig.tight_layout()
    savefig(fig, "20_polarization_curve.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
