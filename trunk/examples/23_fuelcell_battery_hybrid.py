"""Example 23 — Hybridizing a hydrogen fuel cell with a battery: when does it pay?

A fuel-cell + battery powertrain has a battery supply a fraction ``phi`` of the propulsive
power and the (physics-based) fuel cell supply the rest. The fuel cell is sized for the
largest power it must deliver: max(take-off/OEI share, mission peak share). A battery can
only make the aircraft lighter if it lowers that sizing power by more than its own mass
(and the snowball of that mass) costs. Three strategies:

* **Take-off assist** — the battery covers ``phi`` of the take-off run only (no taxi, no
  climb). The run lasts well under a minute, so the battery is sized by *power*, not
  energy. It removes stack mass only if the take-off peak is what sizes the fuel cell.
* **Take-off + climb assist** — the battery also covers ``phi`` of every climb segment. The
  climb to 8,000 m lasts ~27 minutes, so the battery becomes an *energy* battery.
* **Energy hybridization** — the battery covers ``phi`` of the cruise power. The pack is
  sized by cruise energy.

Two conditions decide whether the take-off assist pays, and the example varies one lever
for each:

1. **The take-off must size the fuel cell.** Lever: the take-off field.
   - the **baseline** field, 1,107 m (ATR 42-600 take-off distance at MTOW, ISA, sea level);
   - a **short** field, 800 m, the runway length the ATR 42-600S (short take-off and landing
     version) is advertised for (ATR, "ATR 42-600S" factsheet, 2022).
   On the baseline field the climb needs more power than the take-off; on the short field
   the take-off needs more. The power balance gives the share at which the battery brings
   the fuel cell's take-off load down to its climb load,

       phi* = 1 - P_climb,peak / P_take-off ,

   beyond which the climb sizes the fuel cell again and the battery only adds mass.

2. **The battery must be lighter per kW than what it removes.** Lever: the battery
   specific power. The stack shrinks, and with it the balance of plant and the TMS, but the
   motor and PMAD do not: the battery power flows through them too, so they still carry the
   full take-off power. Two packs are compared:
   - 1.5 kW/kg, the default of ``common.fuelcell_battery_config`` (an energy-oriented pack);
   - 3 kW/kg, a power-oriented pack. This is an ASSUMED technology level for the study, not
     a sourced value; replace it with the datasheet value of the pack you want to study.
   A final scan of the specific power at the predicted phi* on the short field locates the
   break-even specific power.

Energy hybridization is shown once, on the baseline field.

The example sizes ~35 aircraft and takes about 15-20 minutes.

Run it:
    cd trunk && python examples/23_fuelcell_battery_hybrid.py
"""

import PhlyGreen as pg
from common import fuelcell_battery_config, savefig

FIELDS = {"baseline field (1,107 m)": 1107.0, "short field (800 m, ATR 42-600S)": 800.0}
BATTERIES = {"1.5 kW/kg pack (default)": 1500.0, "3 kW/kg power pack (assumed)": 3000.0}
PHIS_TAKEOFF = [0.00, 0.05, 0.10, 0.15, 0.20, 0.30]   # fine grid: the optimum is the point
PHIS_CLIMB = [0.00, 0.10, 0.20]                       # coarse: the trend is monotonic
PHIS_ENERGY = [0.00, 0.10, 0.20]
SPECIFIC_POWER_SCAN = [1500.0, 1750.0, 2000.0, 2500.0, 3000.0, 5000.0]   # [W/kg]


def fcb_config(phi, strategy, field_m=1107.0, battery_specific_power=1500.0):
    """A FuelCellBattery config with battery share ``phi`` applied per ``strategy``
    ('takeoff', 'takeoff+climb' or 'energy') on a take-off field of ``field_m`` metres.

    The battery takes no share of the taxi power (``taxi_phi = 0``), so the take-off-assist
    battery covers the take-off run only."""
    cfg = fuelcell_battery_config(cruise_phi=0.0)
    cfg.constraints.phases["Take Off"]["sTO"] = field_m
    cfg.energy.battery_specific_power = battery_specific_power
    cfg.mission.taxi_phi = 0.0
    for seg in cfg.mission_stages.segments:
        if seg.name == "Takeoff":
            seg.phi = phi if strategy in ("takeoff", "takeoff+climb") else 0.0
        elif seg.segment_type == "ConstantRateClimb":
            seg.phi_start = seg.phi_end = phi if strategy == "takeoff+climb" else 0.0
        elif seg.segment_type == "ConstantMachCruise":
            seg.phi_start = seg.phi_end = phi if strategy == "energy" else 0.0
    return cfg


def design(phi, strategy, field_m=1107.0, battery_specific_power=1500.0):
    """Size one design; return a dict of results, or None if the weight loop does not close."""
    try:
        a = pg.build_aircraft()
        a.configure(fcb_config(phi, strategy, field_m, battery_specific_power))
    except Exception as exc:                       # the weight loop diverges -> infeasible
        print(f"    (phi={phi:.2f}, {strategy}: infeasible — {type(exc).__name__})")
        return None
    w, m = a.weight, a.mission
    climb_phi = phi if strategy == "takeoff+climb" else 0.0
    return {"WTO": w.WTO, "H2": w.WH2_Fuel, "bat": w.WBat or 0.0,
            "fc_system": w.WPT,                    # stack + BoP + PMAD + motor
            "stack_bop_pmad": w.WThermal, "motor": w.WElectric,
            "tms": w.WHeat_Exchanger or 0.0,
            "P_TO": m.TO_PP + m.TO_PBat,
            "P_climb": m.Max_PEng / max(1e-9, 1.0 - climb_phi)}


def print_sweep(title, phis, rows):
    print(f"\n=== {title} ===")
    print(f"{'phi':>6} {'WTO [kg]':>10} {'H2 [kg]':>9} {'battery [kg]':>13} {'FC system [kg]':>15} "
          f"{'TMS [kg]':>9}")
    for phi, r in zip(phis, rows):
        if r:
            print(f"{phi:6.2f} {r['WTO']:10.0f} {r['H2']:9.1f} {r['bat']:13.1f} {r['fc_system']:15.1f} "
                  f"{r['tms']:9.1f}")


def mass_balance(base, r):
    """Mass changes of a design ``r`` against the pure-hydrogen design ``base`` [kg]."""
    d = {"stack + BoP + PMAD": r["stack_bop_pmad"] - base["stack_bop_pmad"],
         "motor": r["motor"] - base["motor"],
         "TMS": r["tms"] - base["tms"],
         "battery": r["bat"] - base["bat"],
         "hydrogen": r["H2"] - base["H2"]}
    d["structure and the rest (snowball)"] = (r["WTO"] - base["WTO"]) - sum(d.values())
    d["take-off weight"] = r["WTO"] - base["WTO"]
    return d


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
        print(f"  predicted optimum phi* = 1 - P_climb/P_TO = {phi_star:.3f}")
    if best_phi == 0.0:
        print("  sweep: the pure-hydrogen design (phi = 0) is the lightest; the battery does not pay.")
    else:
        print(f"  sweep: lightest design at phi = {best_phi:.2f}: WTO {best['WTO']:,.0f} kg "
              f"({best['WTO'] - base['WTO']:+,.0f} kg, {100*(best['WTO']/base['WTO'] - 1):+.1f} % "
              f"vs pure H2)")
    return phi_star, best_phi


def main():
    takeoff = {}       # (field label, battery label) -> (phis, rows)
    for f_label, field in FIELDS.items():
        base = design(0.0, "takeoff", field)        # phi = 0 has no battery: one run per field
        for b_label, sp in BATTERIES.items():
            rows = [base] + [design(phi, "takeoff", field, sp) for phi in PHIS_TAKEOFF[1:]]
            takeoff[(f_label, b_label)] = (PHIS_TAKEOFF, rows)
            print_sweep(f"{f_label}, {b_label}: battery on the take-off run", PHIS_TAKEOFF, rows)

    short = "short field (800 m, ATR 42-600S)"
    power_pack = "3 kW/kg power pack (assumed)"
    climb = [takeoff[(short, power_pack)][1][0]] + [design(phi, "takeoff+climb", FIELDS[short], BATTERIES[power_pack])
                                                    for phi in PHIS_CLIMB[1:]]
    print_sweep(f"{short}, {power_pack}: battery on take-off + climb", PHIS_CLIMB, climb)

    energy = [takeoff[("baseline field (1,107 m)", "1.5 kW/kg pack (default)")][1][0]] + \
             [design(phi, "energy") for phi in PHIS_ENERGY[1:]]
    print_sweep("baseline field: ENERGY hybridization (battery in cruise)", PHIS_ENERGY, energy)

    print("\n=== Analysis: take-off assist ===")
    for (f_label, b_label), (phis, rows) in takeoff.items():
        analyse(f"{f_label}, {b_label}", phis, rows)

    # Where the mass goes at the predicted optimum on the short field, for both packs.
    base_short = takeoff[(short, power_pack)][1][0]
    phi_star = round(1.0 - base_short["P_climb"] / base_short["P_TO"], 2)
    i_star = PHIS_TAKEOFF.index(min(PHIS_TAKEOFF, key=lambda p: abs(p - phi_star)))
    print(f"\n=== Mass changes vs pure H2, {short}, phi = {PHIS_TAKEOFF[i_star]:.2f} [kg] ===")
    balances = {b: mass_balance(base_short, takeoff[(short, b)][1][i_star]) for b in BATTERIES}
    print(f"{'':36s}" + "".join(f"{b:>32s}" for b in BATTERIES))
    for key in balances[power_pack]:
        print(f"{key:36s}" + "".join(f"{balances[b][key]:+32.0f}" for b in BATTERIES))

    # Break-even battery specific power at phi* on the short field.
    scan = [design(PHIS_TAKEOFF[i_star], "takeoff", FIELDS[short], sp) for sp in SPECIFIC_POWER_SCAN]
    print(f"\n=== {short}, phi = {PHIS_TAKEOFF[i_star]:.2f}: take-off weight vs battery specific power ===")
    for sp, r in zip(SPECIFIC_POWER_SCAN, scan):
        if r:
            print(f"  {sp/1e3:4.2f} kW/kg: WTO {r['WTO']:,.0f} kg ({r['WTO'] - base_short['WTO']:+,.0f} kg vs pure H2)")

    print("""
Discussion
- The fuel cell is sized for max(take-off share, climb peak share). A take-off battery lowers
  only the first term. On the baseline field the climb already needs more power than the
  take-off, so the battery removes no stack mass and only adds its own (and the snowball),
  whatever its specific power.
- On the short field the take-off sizes the fuel cell. Up to phi* the battery shrinks the
  stack, its balance of plant and the TMS. Beyond phi* the climb sizes the fuel cell again and
  the battery only adds mass, so the lightest design sits close to the predicted phi*.
- The motor and PMAD do not shrink with the stack: the battery feeds the same drive, which
  still carries the full take-off power (it shrinks only through the snowball of a lighter
  aircraft). The battery must therefore save more fuel-cell-system and TMS mass
  than it weighs. With the default 1.5 kW/kg pack it does not; with a power-oriented pack it
  does, and the snowball multiplies the saving. The specific-power scan shows the break-even.
- Covering the climb too makes the battery an ENERGY battery (the climb lasts ~27 min); its
  mass is then set by the specific energy, and a high specific power no longer helps.
- Energy hybridization (battery in cruise) is the worst choice: the pack is sized by cruise
  energy and the take-off weight runs away.
- The 3 kW/kg pack is an assumed technology level. The conclusion depends on it: check the
  specific power of the pack you have in mind against the break-even of the scan.""")

    _plot(takeoff, climb, energy, scan, base_short, PHIS_TAKEOFF[i_star])


def _plot(takeoff, climb, energy, scan, base_short, phi_scan):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception:
        return

    def col(rows, key):
        return np.array([r[key] if r else np.nan for r in rows])

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13, 4.8))
    colours = dict(zip(FIELDS, ("tab:blue", "tab:orange")))
    styles = dict(zip(BATTERIES, ("o--", "o-")))
    for (f_label, b_label), (phis, rows) in takeoff.items():
        base = rows[0]["WTO"]
        axL.plot(phis, col(rows, "WTO") - base, styles[b_label], color=colours[f_label],
                 label=f"{f_label}, {b_label}")
    short = "short field (800 m, ATR 42-600S)"
    axL.plot(PHIS_CLIMB, col(climb, "WTO") - climb[0]["WTO"], "s:", color=colours[short],
             label=f"{short}, 3 kW/kg, take-off + climb")
    axL.axhline(0.0, color="k", lw=0.8)
    axL.set_xlabel("battery share phi"); axL.set_ylabel("take-off weight change vs pure H2 [kg]")
    axL.set_ylim(-1500, 3000)
    axL.set_title("Take-off assist pays only on the short field, with a power battery")
    axL.grid(alpha=0.3); axL.legend(fontsize=7)

    sp = np.array(SPECIFIC_POWER_SCAN) / 1e3
    axR.plot(sp, col(scan, "WTO") - base_short["WTO"], "o-", color=colours[short])
    axR.axhline(0.0, color="k", lw=0.8)
    axR.set_xlabel("battery specific power [kW/kg]")
    axR.set_ylabel("take-off weight change vs pure H2 [kg]")
    axR.set_title(f"Short field, phi = {phi_scan:.2f}: break-even specific power")
    axR.grid(alpha=0.3)

    fig.tight_layout()
    print("\nFigures:")
    savefig(fig, "23_fuelcell_battery_sweep.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
