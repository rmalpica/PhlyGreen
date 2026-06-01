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
from common import traditional_config, hybrid_config, atr_flops_input


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


if __name__ == "__main__":
    structures_comparison()
    battery_comparison()
