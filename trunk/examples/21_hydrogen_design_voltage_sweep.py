"""Example 21 — Sweep the fuel-cell design voltage.

The design cell voltage is a key fuel-cell sizing choice. At a *higher* design voltage each
cell runs at lower current density (more efficient locally), but it also takes more active
area / heavier stack to make the rated power — and because a heavier powertrain needs more
hydrogen, which needs an even bigger fuel cell, the design can "snowball". The sweep below
shows that competition: there is a take-off-weight *optimum* at a moderate design voltage,
with the weight climbing steeply as the voltage gets too high (until the design no longer
closes at all).

It reuses the stateless `pg.evaluate(base, apply, x)` outer-loop helper from the other
examples — here the parameter is the design cell voltage.

Run it (sizes one aircraft per voltage, takes a little while):
    cd trunk && python examples/21_hydrogen_design_voltage_sweep.py
"""

import PhlyGreen as pg
from common import hydrogen_config


def set_design_voltage(config, v_cell):
    """Encode the parameter: set the fuel-cell design cell voltage [V]."""
    config.energy.v_cell_design = float(v_cell)


def main():
    base = hydrogen_config()
    voltages = [0.40, 0.45, 0.50, 0.55, 0.60]

    print(f"{'V_design [V]':>12} {'WTO [kg]':>10} {'H2 fuel [kg]':>13} "
          f"{'FC mass [kg]':>13} {'N_cells':>8}")

    rows = []
    for v in voltages:
        # We want a couple of extra fuel-cell numbers, so build the aircraft explicitly
        # (pg.evaluate would only return the AircraftResults dataclass).
        aircraft = pg.build_aircraft()
        aircraft.configure(hydrogen_config(v_cell_design=v))
        r = aircraft.results()
        rows.append((v, r.WTO))
        print(f"{v:12.2f} {r.WTO:10.1f} {aircraft.weight.WH2_Fuel:13.1f} "
              f"{r.WPT:13.1f} {aircraft.fuelcell.N_cells:8d}")

    best_v, best_wto = min(rows, key=lambda row: row[1])
    print(f"\nLightest design in this range: V = {best_v:.2f} V  (WTO {best_wto:.0f} kg).")
    print("Past the optimum the fuel-cell mass snowballs; very high voltages fail to close.")

    # The same parameter also works through the generic outer-loop helper:
    wto = pg.evaluate(base, set_design_voltage, best_v).WTO
    print(f"(via pg.evaluate, V={best_v:.2f} -> WTO {wto:.1f} kg)")


if __name__ == "__main__":
    main()
