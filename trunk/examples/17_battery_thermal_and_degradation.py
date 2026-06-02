"""Example 17 — Class-II battery thermal management & cycle-life degradation.

The Class-II battery already carries an in-flight electro-thermal model. On top of that, this
example runs the *opt-in, post-design* analysis (`battery.thermal_degradation_analysis()`):

1. size a hybrid-electric aircraft with the Class-II (cell-level) battery, as usual;
2. then analyse, for a chosen ground fast-charge C-rate:
   - the recharge time from the end-of-flight SOC back to full,
   - the cell temperature reached during the recharge,
   - the **peak active-cooling power** the thermal-management system (TMS) must reject,
   - the expected **number of cycles to end-of-life** (Wang et al. fade + Miner damage).

This analysis never changes the baseline design — it is a separate study run after sizing — so
you can sweep the charge C-rate to trade fast turnaround against cooling load and battery life.

Run it:
    cd trunk && python examples/17_battery_thermal_and_degradation.py
"""

import warnings

import PhlyGreen as pg
from common import hybrid_config


def _design(charge_c_rate, discharge_c_rate, eol_capacity=0.8):
    """Size a Class-II hybrid and attach the degradation/cooling inputs to its config."""
    cfg = hybrid_config(battery_class='II')
    cfg.cell.charge_c_rate = charge_c_rate
    cfg.cell.discharge_c_rate = discharge_c_rate
    cfg.cell.eol_capacity = eol_capacity
    cfg.cell.coolant_temperature = 20.0          # ground coolant inlet [C]
    cfg.cell.ground_cooling_coefficient = 150.0  # liquid cold-plate h [W/m^2K]
    aircraft = pg.build_aircraft()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        aircraft.configure(cfg)
    return aircraft


def main():
    print("=== Class-II battery: ground fast-charge cooling & cycle life ===\n")
    aircraft = _design(charge_c_rate=2.0, discharge_c_rate=3.0)
    print(f"Designed hybrid: WTO = {aircraft.weight.WTO:.0f} kg, "
          f"battery = {aircraft.weight.WBat:.0f} kg "
          f"(S{int(aircraft.battery.S_number)} x P{int(aircraft.battery.P_number)})\n")

    print(f"{'charge C-rate':>13} | {'recharge':>9} | {'T_final':>8} | "
          f"{'peak cooling':>12} | {'cycles':>8}")
    print("-" * 62)
    for c_rate in (1.0, 2.0, 3.0, 4.0):
        r = aircraft.battery.thermal_degradation_analysis(charge_c_rate=c_rate)
        print(f"{c_rate:>10.1f} C  | {r['recharge_time_min']:>6.1f} min | "
              f"{r['T_final'] - 273.15:>6.1f} C | {r['peak_cooling_w'] / 1000:>9.1f} kW | "
              f"{r['n_cycles']:>8.0f}")

    print("\nFaster charging shortens the turnaround but raises the cell temperature, the "
          "cooling power the TMS must reject, and the battery degradation (fewer cycles).")


if __name__ == "__main__":
    main()
