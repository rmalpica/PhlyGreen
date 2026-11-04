"""Example 27 — Thermal management of a hydrogen fuel-cell aircraft: Class I vs Class II.

A PEM fuel cell turns only about half of the hydrogen energy into electricity; the rest is
low-temperature heat (~80 C) that a thermal-management system (TMS) must reject. Two models:

* **Class I** (default) — the exchanger mass is the peak fuel-cell heat divided by a
  specific power (``EnergyConfig.hex_specific_power_h2``, 5 kW/kg by default). The peak is
  taken over the mission AND the take-off/OEI point, where the fuel cell rejects the most heat.
* **Class II** — a geometric model: the coolant leaving the stack first warms the liquid
  hydrogen fuel, then rejects the rest to ram air. Each heat exchanger is sized from its
  geometry (plain/finned tube banks, plate-fin) with as many units in parallel as needed to
  respect per-unit mass and volume caps. The coolant pump is an electrical load on the fuel cell, and the ram-air duct
  drag is added to the drag polar. The design point is chosen over the mission: the
  lightest geometry that still rejects the heat at every mission point when the hardware
  is fixed.

The example sizes the same aircraft with both models and prints the TMS design. It then
rates the chosen geometry at every mission point, and shows how the ram-air drag at the
design point depends on the intake ram recovery. That parameter defaults to an ideal intake
(1.0), so the drag is a lower bound.

Needs CoolProp (pip install CoolProp). The Class-II design takes about a minute.

Run it:
    cd trunk && python examples/27_hydrogen_tms_class_ii.py
"""

import PhlyGreen as pg
from PhlyGreen.config import TMSConfig
from common import hydrogen_config, print_results, savefig


def design(tms_class):
    cfg = hydrogen_config()
    cfg.tms = TMSConfig(tms_class=tms_class)
    aircraft = pg.build_aircraft()
    aircraft.configure(cfg)
    return aircraft


def main():
    print("Sizing with the Class-I TMS (specific power) ...")
    a1 = design('I')
    print("Sizing with the Class-II TMS (geometric heat exchangers) ...")
    a2 = design('II')

    print_results(a1, "Hydrogen aircraft, TMS Class I")
    print_results(a2, "Hydrogen aircraft, TMS Class II")

    r1, r2 = a1.results(), a2.results()
    print("\n=== Class I vs Class II ===")
    print(f"{'':28s} {'Class I':>10s} {'Class II':>10s}")
    print(f"{'Take-off weight [kg]':28s} {r1.WTO:10.0f} {r2.WTO:10.0f}")
    print(f"{'TMS mass [kg]':28s} {r1.tms_mass:10.0f} {r2.tms_mass:10.0f}")
    print(f"{'Fuel-cell system [kg]':28s} {r1.WPT:10.0f} {r2.WPT:10.0f}")
    print(f"{'Hydrogen [kg]':28s} {a1.weight.WH2_Fuel:10.0f} {a2.weight.WH2_Fuel:10.0f}")
    print(f"{'Fuel-cell rating [kW]':28s} {a1.fuelcell.P_fc_rated/1e3:10.0f} {a2.fuelcell.P_fc_rated/1e3:10.0f}")
    print(f"{'Pump power [kW]':28s} {0.0:10.1f} {r2.tms_pump_power/1e3:10.1f}")
    print(f"{'Ram-air drag [N]':28s} {0.0:10.0f} {r2.tms_ram_drag:10.0f}")
    Q_peak = max(a2.mission.Max_FC_Thermal_Pwr, a2.mission.TO_FC_Thermal_Pwr)
    print(f"{'Peak heat / TMS mass [kW/kg]':28s} "
          f"{max(a1.mission.Max_FC_Thermal_Pwr, a1.mission.TO_FC_Thermal_Pwr)/1e3/r1.tms_mass:10.2f} "
          f"{Q_peak/1e3/r2.tms_mass:10.2f}")

    tms, res = a2.tms, a2.weight.tms_result
    print()
    tms.report()

    print("\nDesign-point selection (each candidate geometry rated at every mission point):")
    print(f"  {'candidate':22s} {'mass [kg]':>10s} {'worst shortfall':>16s}  at")
    for c in res.candidates:
        print(f"  {c['point']:22s} {c['mass']:10.0f} {100*c['worst_shortfall']:15.1f}%  "
              f"{c['worst_shortfall_at'] or '-'}")

    print("\nChosen geometry rated over the mission (fixed pump flow and intake area,")
    print("flap fully open): heat to reject vs heat the hardware can reject")
    print(f"  {'point':22s} {'Q_fc [kW]':>10s} {'required [kW]':>14s} {'capacity [kW]':>14s}")
    rows = []
    for p in a2.mission.thermal_profile:
        q_cap, q_req = tms.RateAtPoint(res, p, capped=False)
        rows.append((p['name'], q_req, q_cap))
        print(f"  {p['name']:22s} {p['Q_fc']/1e3:10.0f} {q_req/1e3:14.0f} {q_cap/1e3:14.0f}")

    print("\nRam-air drag at the design point vs intake ram recovery (geometry re-sized):")
    for eta in (1.0, 0.9, 0.8, 0.7):
        tms.ram_recovery = eta
        r = tms.SizeAtPoint(res.design_point)
        print(f"  ram recovery {eta:.1f}: drag {r.ram_drag:7.0f} N  "
              f"(momentum balance {r.ram_drag_raw:7.0f} N), TMS {r.total_mass:6.0f} kg")
    tms.ram_recovery = 1.0

    _plot_rating(rows)


def _plot_rating(rows):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import numpy as np
    except Exception:
        return
    names = [r[0] for r in rows]
    x = np.arange(len(rows))
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.bar(x - 0.2, [r[1] / 1e3 for r in rows], 0.4, label="heat to reject")
    ax.bar(x + 0.2, [r[2] / 1e3 for r in rows], 0.4, label="capacity of the chosen TMS")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=45, ha="right")
    ax.set_ylabel("heat [kW]")
    ax.set_title("Class-II TMS rated over the mission")
    ax.legend()
    fig.tight_layout()
    savefig(fig, "27_tms_rating.png")


if __name__ == "__main__":
    main()
