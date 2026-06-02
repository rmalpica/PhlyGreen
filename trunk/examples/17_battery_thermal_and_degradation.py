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
    c_rates = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    recharge, tfinal, cooling, cycles = [], [], [], []
    for c_rate in c_rates:
        r = aircraft.battery.thermal_degradation_analysis(charge_c_rate=c_rate)
        recharge.append(r['recharge_time_min']); tfinal.append(r['T_final'] - 273.15)
        cooling.append(r['peak_cooling_w'] / 1000); cycles.append(r['n_cycles'])
        print(f"{c_rate:>10.1f} C  | {r['recharge_time_min']:>6.1f} min | "
              f"{r['T_final'] - 273.15:>6.1f} C | {r['peak_cooling_w'] / 1000:>9.1f} kW | "
              f"{r['n_cycles']:>8.0f}")

    print("\nFaster charging shortens the turnaround but raises the cell temperature, the "
          "cooling power the TMS must reject, and the battery degradation (fewer cycles).")

    _plot(c_rates, recharge, tfinal, cooling, cycles)


def _plot(c_rates, recharge, tfinal, cooling, cycles):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    from common import savefig
    fig, ax = plt.subplots(2, 2, figsize=(12, 8))
    ax[0, 0].plot(c_rates, recharge, "o-", color="tab:blue")
    ax[0, 0].set_ylabel("recharge time [min]"); ax[0, 0].set_title("Turnaround")
    ax[0, 1].plot(c_rates, tfinal, "o-", color="tab:red")
    ax[0, 1].set_ylabel("final cell T [C]"); ax[0, 1].set_title("Peak temperature")
    ax[1, 0].plot(c_rates, cooling, "o-", color="tab:green")
    ax[1, 0].set_ylabel("peak cooling [kW]"); ax[1, 0].set_title("TMS cooling load")
    ax[1, 1].plot(c_rates, cycles, "o-", color="tab:purple")
    ax[1, 1].set_ylabel("cycles to EoL"); ax[1, 1].set_title("Battery life")
    for a in ax.flat:
        a.set_xlabel("charge C-rate [1/h]"); a.grid(alpha=0.3)
    fig.suptitle("Ground fast-charge: cooling vs turnaround vs battery life")
    fig.tight_layout()
    print("\nFigures:")
    savefig(fig, "17_battery_thermal_sweep.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
