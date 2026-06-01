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
from common import hydrogen_config


def main():
    aircraft = pg.build_aircraft()
    aircraft.configure(hydrogen_config())     # size + fly the mission

    r = aircraft.results()
    fc = aircraft.fuelcell
    w = aircraft.weight

    print("=== Hydrogen fuel-cell aircraft ===")
    print(f"Take-off weight    : {r.WTO:9.1f} kg")
    print(f"Usable H2 fuel     : {w.WH2_Fuel:9.1f} kg")
    print(f"Fuel-cell system   : {r.WPT:9.1f} kg")
    print(f"H2 tank (empty)    : {w.WTank:9.1f} kg")
    print(f"Cooling system     : {w.WHeat_Exchanger:9.1f} kg")
    print(f"Structure          : {r.WStructure:9.1f} kg")
    print(f"Wing area          : {r.WingSurface:9.1f} m^2")
    print()
    print("--- Fuel-cell stack ---")
    print(f"Rated net power    : {fc.P_fc_rated/1000:9.1f} kW")
    print(f"Number of cells    : {fc.N_cells:9d}")
    print(f"Design cell voltage: {fc.V_cell_design:9.3f} V")
    print(f"Active area / cell  : {fc.A_cell_reale:9.1f} cm^2")

    # The polarization curve is the heart of the model: cell voltage vs current density.
    print("\nPolarization curve (at the design pressure):")
    print(f"{'i [A/cm^2]':>10} {'V_cell [V]':>10}")
    for i_dens in (0.1, 0.5, 1.0, 1.5, 2.0):
        print(f"{i_dens:10.2f} {fc.PolarizationCurve(i_dens, fc.Target_Press):10.3f}")


if __name__ == "__main__":
    main()
