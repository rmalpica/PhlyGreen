"""Example 23 — Hybridizing a hydrogen fuel cell with a battery.

A fuel-cell + battery powertrain: the battery supplies a fraction ``phi`` of the propulsive
power and the (physics-based) fuel cell supplies the rest. Sweeping ``phi`` shows the trade:
the battery can shave the fuel-cell peak (a smaller stack), but batteries store little
energy per kg, so for a cruise-dominated mission the battery mass grows quickly with phi.

Run it:
    cd trunk && python examples/23_fuelcell_battery_hybrid.py
"""

import PhlyGreen as pg
from common import fuelcell_battery_config


def main():
    print(f"{'cruise phi':>11} {'WTO [kg]':>10} {'H2 [kg]':>9} {'battery [kg]':>13} "
          f"{'fuel cell [kg]':>15}")

    for phi in [0.00, 0.05, 0.10, 0.15]:
        aircraft = pg.build_aircraft()
        aircraft.configure(fuelcell_battery_config(cruise_phi=phi))
        r = aircraft.results()
        print(f"{phi:11.2f} {r.WTO:10.0f} {aircraft.weight.WH2_Fuel:9.1f} "
              f"{r.WBat:13.1f} {r.WPT:15.1f}")

    print("\nphi = battery share of propulsive power. Here the mission is cruise-dominated,")
    print("so battery *energy* (not power) sizes the pack and weight climbs with phi —")
    print("battery hybridization pays off for short, power-limited segments, not long cruise.")


if __name__ == "__main__":
    main()
