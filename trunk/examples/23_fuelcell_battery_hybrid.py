"""Example 23 — Hybridizing a hydrogen fuel cell with a battery: when does it pay?

A fuel-cell + battery powertrain has a battery supply a fraction ``phi`` of the propulsive
power and the (physics-based) fuel cell supply the rest. The fuel cell is sized for the
largest power it must deliver: max(take-off/OEI share, mission peak share). A battery can
only make the aircraft lighter if it lowers that sizing power by more than its own mass
(and the snowball of that mass) costs. Three strategies:

* **Take-off assist** — the battery covers ``phi`` of the take-off power only. The take-off
  run lasts well under a minute, so the battery is sized by *power*, not energy, and stays
  small. It removes stack mass only if the take-off peak is what sizes the fuel cell.
* **Take-off + climb assist** — the battery also covers ``phi`` of every climb segment. The
  climb to 8,000 m lasts ~27 minutes, so the battery becomes an *energy* battery and grows quickly.
* **Energy hybridization** — the battery covers ``phi`` of the cruise power. The pack is
  sized by cruise energy and its mass explodes for a cruise-dominated mission.

The example runs the first two strategies on two take-off fields:

- the **baseline** field, 1,107 m (ATR 42-600 take-off distance at MTOW, ISA, sea level);
- a **short** field, 800 m, the runway length the ATR 42-600S (short take-off and landing
  version) is advertised for (ATR, "ATR 42-600S" factsheet, 2022).

On the baseline field the climb, not the take-off, sizes the fuel cell, and no battery pays.
On the short field the take-off power rises above the climb power, the take-off peak sizes
the fuel cell, and a small take-off battery makes the aircraft lighter. The script computes
the optimum share predicted by the power balance,

    phi* = 1 - P_climb,peak / P_take-off ,

(the share at which the battery brings the fuel cell's take-off load down to its climb load;
beyond it the climb sizes the fuel cell again and the battery only adds mass) and compares it
with the sweep. Energy hybridization is shown once, on the baseline field.

It sizes ~20 aircraft and takes a few minutes.

Run it:
    cd trunk && python examples/23_fuelcell_battery_hybrid.py
"""

import PhlyGreen as pg
from common import fuelcell_battery_config, savefig

FIELDS = {"baseline field (1,107 m)": 1107.0, "short field (800 m, ATR 42-600S)": 800.0}
PHIS_TAKEOFF = [0.00, 0.05, 0.10, 0.15, 0.20, 0.30]   # fine grid: the optimum is the point
PHIS_CLIMB = [0.00, 0.10, 0.20]                       # coarse: the trend is monotonic
PHIS_ENERGY = [0.00, 0.10, 0.20]


def fcb_config(phi, strategy, field_m=1107.0):
    """A FuelCellBattery config with battery share ``phi`` applied per ``strategy``
    ('takeoff', 'takeoff+climb' or 'energy') on a take-off field of ``field_m`` metres."""
    cfg = fuelcell_battery_config(cruise_phi=0.0)
    cfg.constraints.phases["Take Off"]["sTO"] = field_m
    for seg in cfg.mission_stages.segments:
        if seg.name == "Takeoff":
            seg.phi = phi if strategy in ("takeoff", "takeoff+climb") else 0.0
        elif seg.segment_type == "ConstantRateClimb":
            seg.phi_start = seg.phi_end = phi if strategy == "takeoff+climb" else 0.0
        elif seg.segment_type == "ConstantMachCruise":
            seg.phi_start = seg.phi_end = phi if strategy == "energy" else 0.0
    return cfg


def design(phi, strategy, field_m=1107.0):
    """Size one design; return a dict of results, or None if the weight loop does not close."""
    try:
        a = pg.build_aircraft()
        a.configure(fcb_config(phi, strategy, field_m))
    except Exception as exc:                       # the weight loop diverges -> infeasible
        print(f"    (phi={phi:.2f}, {strategy}: infeasible — {type(exc).__name__})")
        return None
    r, m = a.results(), a.mission
    return {"WTO": r.WTO, "H2": a.weight.WH2_Fuel, "bat": r.WBat or 0.0, "fc": r.WPT,
            "P_TO": m.TO_PP + m.TO_PBat, "P_climb": m.Max_PEng / max(1e-9, 1.0 - _climb_phi(phi, strategy))}


def _climb_phi(phi, strategy):
    return phi if strategy == "takeoff+climb" else 0.0


def print_sweep(title, phis, rows):
    print(f"\n=== {title} ===")
    print(f"{'phi':>6} {'WTO [kg]':>10} {'H2 [kg]':>9} {'battery [kg]':>13} {'fuel cell [kg]':>15}")
    for phi, r in zip(phis, rows):
        if r:
            print(f"{phi:6.2f} {r['WTO']:10.0f} {r['H2']:9.1f} {r['bat']:13.1f} {r['fc']:15.1f}")


def analyse(label, phis, rows):
    """Predicted optimum share vs the sweep, for the take-off-assist strategy."""
    base = rows[0]
    phi_star = max(0.0, 1.0 - base["P_climb"] / base["P_TO"])
    ok = [(p, r) for p, r in zip(phis, rows) if r]
    best_phi, best = min(ok, key=lambda pr: pr[1]["WTO"])
    print(f"\n{label}: take-off propulsive power {base['P_TO']/1e3:,.0f} kW, mission (climb) peak "
          f"{base['P_climb']/1e3:,.0f} kW")
    if phi_star <= 0.0:
        print("  the climb peak is the larger one: the take-off does not size the fuel cell, so a")
        print("  take-off battery cannot remove stack mass (predicted phi* = 0).")
    else:
        print(f"  predicted optimum phi* = 1 - P_climb/P_TO = {phi_star:.2f}")
    print(f"  sweep: lightest design at phi = {best_phi:.2f}: WTO {best['WTO']:,.0f} kg "
          f"({best['WTO'] - base['WTO']:+,.0f} kg vs pure H2), fuel cell {best['fc']:,.0f} kg "
          f"({best['fc'] - base['fc']:+,.0f} kg), battery {best['bat']:,.0f} kg")
    return phi_star, best_phi


def main():
    results = {}
    for label, field in FIELDS.items():
        for strategy, phis in (("takeoff", PHIS_TAKEOFF), ("takeoff+climb", PHIS_CLIMB)):
            rows = [design(phi, strategy, field) for phi in phis]
            results[(label, strategy)] = (phis, rows)
            print_sweep(f"{label}: battery on {strategy}", phis, rows)

    energy = [design(phi, "energy") for phi in PHIS_ENERGY]
    print_sweep("baseline field: ENERGY hybridization (battery in cruise)", PHIS_ENERGY, energy)

    print("\n=== Analysis: take-off assist ===")
    for label in FIELDS:
        analyse(label, *results[(label, "takeoff")])

    print("""
Discussion
- The fuel cell is sized for max(take-off share, climb peak share). A take-off battery lowers
  only the first term. On the baseline field the climb already needs more power than the
  take-off, so the battery removes no stack mass and only adds its own (and the snowball).
- On the 800 m field the take-off needs more power than the climb. The battery brings the
  fuel cell's take-off load down to the climb load; up to phi* the stack shrinks faster than the
  battery grows, and the aircraft gets lighter. Beyond phi* the climb sizes the fuel cell again.
- The battery must be a POWER battery: the take-off lasts under a minute, so the pack is sized
  by its specific power. Covering the climb too makes it an ENERGY battery (the climb to
  8,000 m lasts ~27 min), and that never pays here, on either field.
- Energy hybridization (battery in cruise) is the worst choice: the pack is sized by cruise
  energy and the take-off weight runs away.
- The gain is modest (a few percent) because the battery's specific power (1.5 kW/kg) is close
  to the fuel-cell system's. A lighter power battery, or a steeper take-off/climb peak, widens it.""")

    _plot(results, energy)


def _plot(results, energy):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception:
        return

    def col(rows, key):
        return [r[key] if r else np.nan for r in rows]

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13, 4.8))
    styles = {"takeoff": "o-", "takeoff+climb": "s--"}
    colours = dict(zip(FIELDS, ("tab:blue", "tab:orange")))
    for (label, strategy), (phis, rows) in results.items():
        axL.plot(phis, col(rows, "WTO"), styles[strategy], color=colours[label],
                 label=f"{label}, battery on {strategy}")
    axL.plot(PHIS_ENERGY, col(energy, "WTO"), "^:", color="tab:red", label="baseline field, energy (cruise)")
    axL.set_xlabel("battery share phi"); axL.set_ylabel("take-off weight [kg]")
    axL.set_ylim(top=min(axL.get_ylim()[1], 32000))
    axL.set_title("Where (and when) the battery pays")
    axL.grid(alpha=0.3); axL.legend(fontsize=7)

    for label in FIELDS:
        phis, rows = results[(label, "takeoff")]
        axR.plot(phis, col(rows, "fc"), "o-", color=colours[label], label=f"fuel cell, {label}")
        axR.plot(phis, col(rows, "bat"), "s--", color=colours[label], label=f"battery, {label}")
    axR.set_xlabel("battery share phi (take-off only)"); axR.set_ylabel("mass [kg]")
    axR.set_title("Take-off assist: stack shrinks only if the take-off sizes it")
    axR.grid(alpha=0.3); axR.legend(fontsize=7)

    fig.tight_layout()
    print("\nFigures:")
    savefig(fig, "23_fuelcell_battery_sweep.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
