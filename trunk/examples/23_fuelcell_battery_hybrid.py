"""Example 23 — Hybridizing a hydrogen fuel cell with a battery.

A fuel-cell + battery powertrain: the battery supplies a fraction ``phi`` of the propulsive
power and the (physics-based) fuel cell supplies the rest. Sweeping ``phi`` shows the trade:
the battery can shave the fuel-cell peak (a smaller stack), but batteries store little
energy per kg, so for a cruise-dominated mission the battery mass grows quickly with phi.

Run it:
    cd trunk && python examples/23_fuelcell_battery_hybrid.py
"""

import PhlyGreen as pg
from common import fuelcell_battery_config, savefig


def main():
    print(f"{'cruise phi':>11} {'WTO [kg]':>10} {'H2 [kg]':>9} {'battery [kg]':>13} "
          f"{'fuel cell [kg]':>15}")

    phis = [0.00, 0.05, 0.10, 0.15]
    wto, h2, bat, fc = [], [], [], []
    for phi in phis:
        aircraft = pg.build_aircraft()
        aircraft.configure(fuelcell_battery_config(cruise_phi=phi))
        r = aircraft.results()
        wto.append(r.WTO); h2.append(aircraft.weight.WH2_Fuel); bat.append(r.WBat); fc.append(r.WPT)
        print(f"{phi:11.2f} {r.WTO:10.0f} {aircraft.weight.WH2_Fuel:9.1f} "
              f"{r.WBat:13.1f} {r.WPT:15.1f}")

    print("\nphi = battery share of propulsive power. Here the mission is cruise-dominated,")
    print("so battery *energy* (not power) sizes the pack and weight climbs with phi —")
    print("battery hybridization pays off for short, power-limited segments, not long cruise.")

    _plot(phis, wto, h2, bat, fc)


def _plot(phis, wto, h2, bat, fc):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13, 4.5))
    axL.plot(phis, wto, "o-", color="tab:blue")
    axL.set_xlabel("cruise phi (battery share)"); axL.set_ylabel("WTO [kg]")
    axL.set_title("Take-off weight"); axL.grid(alpha=0.3)
    axR.plot(phis, h2, "o-", color="tab:red", label="H2 fuel")
    axR.plot(phis, bat, "s-", color="tab:green", label="battery")
    axR.plot(phis, fc, "^-", color="tab:purple", label="fuel-cell system")
    axR.set_xlabel("cruise phi (battery share)"); axR.set_ylabel("mass [kg]")
    axR.set_title("Component masses"); axR.grid(alpha=0.3); axR.legend()
    fig.tight_layout()
    print("\nFigures:")
    savefig(fig, "23_fuelcell_battery_sweep.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
