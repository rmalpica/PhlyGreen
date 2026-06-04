"""Example 23 — Hybridizing a hydrogen fuel cell with a battery (the right way).

A fuel-cell + battery powertrain has a battery supply a fraction ``phi`` of the propulsive
power and the (physics-based) fuel cell supply the rest. *Where* you spend that battery
decides whether it helps or hurts — there are two opposite strategies:

* **Power hybridization** — the battery covers part of the short, high-power **take-off +
  climb** peak, so the fuel cell only has to be sized for the much lower **cruise** power.
  The stack shrinks; the battery stays small (it delivers *power*, not energy). Cruise runs
  on hydrogen alone (``phi = 0``).
* **Energy hybridization** — the battery supplies part of the **cruise** power for a long
  time. Because batteries store little energy per kg, the pack is then sized by cruise
  *energy* and its mass explodes for a cruise-dominated mission.

This example sweeps both and shows the contrast: power hybridization drops the take-off
weight *below* the pure-hydrogen design (a smaller fuel cell), while energy hybridization
sends it through the roof.

Run it:
    cd trunk && python examples/23_fuelcell_battery_hybrid.py
"""

import PhlyGreen as pg
from common import fuelcell_battery_config, savefig


def fcb_config(phi, strategy):
    """A FuelCellBattery config with battery share ``phi`` applied per ``strategy``.

    ``strategy='power'``  → ``phi`` on take-off + climb, cruise on hydrogen only.
    ``strategy='energy'`` → ``phi`` on cruise (the naive choice).
    """
    cfg = fuelcell_battery_config(cruise_phi=0.0)
    for seg in cfg.mission_stages.segments:
        if strategy == "power":
            if seg.name == "Takeoff":
                seg.phi = phi
            elif seg.segment_type == "ConstantRateClimb":
                seg.phi_start = seg.phi_end = phi
            elif seg.segment_type == "ConstantMachCruise":
                seg.phi_start = seg.phi_end = 0.0
        else:  # energy
            if seg.segment_type == "ConstantMachCruise":
                seg.phi_start = seg.phi_end = phi
    return cfg


def design(phi, strategy):
    """Size one design; return (WTO, H2, battery, fuel-cell) masses or None if infeasible."""
    try:
        aircraft = pg.build_aircraft()
        aircraft.configure(fcb_config(phi, strategy))
        r = aircraft.results()
        return r.WTO, aircraft.weight.WH2_Fuel, (r.WBat or 0.0), r.WPT
    except Exception as exc:                       # the weight loop diverges → infeasible
        print(f"    (phi={phi:.2f}, {strategy}: infeasible — {type(exc).__name__})")
        return None


def sweep(phis, strategy):
    rows = [design(phi, strategy) for phi in phis]
    return rows


def main():
    phis = [0.00, 0.10, 0.20, 0.30, 0.40]

    print("=== Power hybridization: battery on take-off + climb (fuel cell sized for cruise) ===")
    print(f"{'phi':>6} {'WTO [kg]':>10} {'H2 [kg]':>9} {'battery [kg]':>13} {'fuel cell [kg]':>15}")
    power = sweep(phis, "power")
    for phi, row in zip(phis, power):
        if row:
            wto, h2, bat, fc = row
            print(f"{phi:6.2f} {wto:10.0f} {h2:9.1f} {bat:13.1f} {fc:15.1f}")

    print("\n=== Energy hybridization: battery in cruise (the naive choice) ===")
    print(f"{'phi':>6} {'WTO [kg]':>10} {'H2 [kg]':>9} {'battery [kg]':>13} {'fuel cell [kg]':>15}")
    energy = sweep(phis, "energy")
    for phi, row in zip(phis, energy):
        if row:
            wto, h2, bat, fc = row
            print(f"{phi:6.2f} {wto:10.0f} {h2:9.1f} {bat:13.1f} {fc:15.1f}")

    base_wto = power[0][0]
    best_i = min((i for i, r in enumerate(power) if r), key=lambda i: power[i][0])
    print(f"\nPure-hydrogen take-off weight (phi=0)        : {base_wto:8.0f} kg")
    print(f"Best POWER-hybrid take-off weight (phi={phis[best_i]:.2f})  : {power[best_i][0]:8.0f} kg "
          f"({power[best_i][0] - base_wto:+.0f} kg, fuel cell {power[best_i][3]:.0f} kg "
          f"vs {power[0][3]:.0f} kg)")
    print("\nPower hybridization shaves the take-off/climb peak so the fuel cell can be sized for")
    print("cruise — a smaller, lighter stack — and the take-off weight dips *below* the pure-H2")
    print("design before the growing battery mass takes over. Energy (cruise) hybridization, by")
    print("contrast, sizes the pack by cruise energy and the weight runs away (and soon won't close).")

    _plot(phis, power, energy)


def _plot(phis, power, energy):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception:
        return

    def col(rows, j):
        return [rows[i][j] if rows[i] else np.nan for i in range(len(rows))]

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13, 4.5))

    # Left: WTO vs phi, both strategies (power dips, energy explodes / goes infeasible).
    axL.plot(phis, col(power, 0), "o-", color="tab:blue", label="power (take-off + climb)")
    axL.plot(phis, col(energy, 0), "s--", color="tab:red", label="energy (cruise)")
    axL.axhline(power[0][0], color="tab:gray", ls=":", label="pure H2 (phi=0)")
    axL.set_xlabel("battery share phi"); axL.set_ylabel("take-off weight [kg]")
    axL.set_title("WTO: where you spend the battery matters")
    axL.grid(alpha=0.3); axL.legend(fontsize=8)

    # Right: for the power strategy, the mechanism — fuel cell shrinks, battery grows.
    axR.plot(phis, col(power, 3), "^-", color="tab:purple", label="fuel-cell system")
    axR.plot(phis, col(power, 2), "s-", color="tab:green", label="battery")
    axR.set_xlabel("battery share phi (take-off + climb)"); axR.set_ylabel("mass [kg]")
    axR.set_title("Power hybridization: smaller fuel cell, small battery")
    axR.grid(alpha=0.3); axR.legend(fontsize=8)

    fig.tight_layout()
    print("\nFigures:")
    savefig(fig, "23_fuelcell_battery_sweep.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
