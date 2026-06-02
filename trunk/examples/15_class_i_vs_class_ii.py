"""Example 15 — Class-I vs Class-II models (structures and battery).

PhlyGreen offers two fidelity levels for several subsystems:

* **Structures** — Class I (regression on take-off weight) vs Class II (FLOPS component
  build-up, which needs a detailed `FLOPSInput`).
* **Battery** — Class I (specific energy/power) vs Class II (cell-level electro-thermal
  model with pack sizing).

This example sizes each pair and compares the results.

Run it:
    cd trunk && python examples/15_class_i_vs_class_ii.py
"""

import PhlyGreen as pg
from common import traditional_config, hybrid_config, atr_flops_input, savefig


def structures_comparison():
    print("=== Structures: Class I (regression) vs Class II (FLOPS) ===")

    # Class I — the default regression structural model.
    ac1 = pg.build_aircraft()
    ac1.configure(traditional_config())   # weight_class defaults to 'I'

    # Class II — FLOPS component build-up; needs a detailed FLOPSInput on the aircraft.
    ac2 = pg.build_aircraft()
    ac2.FLOPSInput = atr_flops_input()
    cfg = traditional_config()
    cfg.weight_class = 'II'
    ac2.configure(cfg)

    print(f"{'':14}{'Class I':>12}{'Class II':>12}")
    print(f"{'structure [kg]':14}{ac1.weight.WStructure:12.1f}{ac2.weight.WStructure:12.1f}")
    print(f"{'WTO [kg]':14}{ac1.weight.WTO:12.1f}{ac2.weight.WTO:12.1f}")
    return ac1, ac2


def battery_comparison():
    print("\n=== Battery: Class I (specific energy/power) vs Class II (cell thermal) ===")

    ac1 = pg.build_aircraft()
    ac1.configure(hybrid_config(battery_class='I'))

    ac2 = pg.build_aircraft()
    ac2.configure(hybrid_config(battery_class='II'))

    print(f"{'':16}{'Class I':>12}{'Class II':>12}")
    print(f"{'battery [kg]':16}{ac1.weight.WBat:12.1f}{ac2.weight.WBat:12.1f}")
    print(f"{'WTO [kg]':16}{ac1.weight.WTO:12.1f}{ac2.weight.WTO:12.1f}")
    # Class II also exposes the sized pack:
    print(f"Class II pack: {ac2.battery.pack_energy/3.6e6:.1f} kWh, "
          f"{ac2.battery.pack_power_max/1000:.1f} kW (S{ac2.battery.S_number:.0f}/P{ac2.battery.P_number:.0f})")
    return ac1, ac2


def _plot(struct, batt):
    try:
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    s1, s2 = struct
    b1, b2 = batt
    fig, (axS, axB) = plt.subplots(1, 2, figsize=(13, 4.5))
    x = np.arange(2); w = 0.35
    axS.bar(x - w/2, [s1.weight.WStructure, s1.weight.WTO], w, label="Class I", color="tab:blue")
    axS.bar(x + w/2, [s2.weight.WStructure, s2.weight.WTO], w, label="Class II", color="tab:orange")
    axS.set_xticks(x); axS.set_xticklabels(["structure", "WTO"])
    axS.set_ylabel("mass [kg]"); axS.set_title("Structures: I vs II (FLOPS)"); axS.legend()

    axB.bar(x - w/2, [b1.weight.WBat, b1.weight.WTO], w, label="Class I", color="tab:blue")
    axB.bar(x + w/2, [b2.weight.WBat, b2.weight.WTO], w, label="Class II", color="tab:orange")
    axB.set_xticks(x); axB.set_xticklabels(["battery", "WTO"])
    axB.set_ylabel("mass [kg]"); axB.set_title("Battery: I vs II (cell thermal)"); axB.legend()
    for ax in (axS, axB):
        ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    print("\nFigures:")
    savefig(fig, "15_class_i_vs_ii.png")
    plt.close(fig)


if __name__ == "__main__":
    struct = structures_comparison()
    batt = battery_comparison()
    _plot(struct, batt)
