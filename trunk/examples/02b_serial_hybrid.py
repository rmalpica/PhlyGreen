"""Example 02b — Serial vs parallel hybrid-electric topology.

Example 02 designs a *parallel* hybrid (the gas turbine and the electric motor both drive
the propeller). This example designs the *serial* topology and puts the two side by side.

In a **serial** hybrid the gas turbine never touches the propeller: it spins a generator
that feeds the electric bus, and an electric motor drives the propeller. So *all* shaft
power flows through the electric chain, paying two conversions — generator
(``eta_electric_motor_1``) and motor (``eta_electric_motor_2``) — instead of the single,
mostly-mechanical parallel path. That extra loss is the price of the serial layout's
freedom (engine runs at its best point, simpler gearing); here it shows up as a heavier
aircraft for the same mission.

Both topologies are the same `hybrid_config`; only `hybrid_type` changes.

Run it:
    cd trunk && python examples/02b_serial_hybrid.py
"""

import PhlyGreen as pg
from common import hybrid_config, print_results, design_dashboard


def _design(hybrid_type):
    aircraft = pg.build_aircraft()
    # Class-I battery here so the comparison is fast and the battery mass is a simple,
    # transparent specific-energy/specific-power sizing (no cell-level thermal loop).
    aircraft.configure(hybrid_config(battery_class='I', hybrid_type=hybrid_type))
    return aircraft


def main():
    parallel = _design('Parallel')
    serial = _design('Serial')

    print_results(serial, "Serial hybrid-electric ATR-like turboprop")

    # Side-by-side: the serial path's two electric conversions cost fuel and battery mass.
    def row(label, fn):
        p, s = fn(parallel), fn(serial)
        print(f"  {label:24s} {p:10.1f} {s:10.1f} {100*(s-p)/p:+8.1f}%")

    print("\nSerial vs parallel hybrid (same mission, same battery model)")
    print(f"  {'quantity':24s} {'Parallel':>10s} {'Serial':>10s} {'delta':>9s}")
    row("Take-off weight [kg]", lambda a: a.weight.WTO)
    row("Mission fuel [kg]", lambda a: a.weight.Wf)
    row("Battery mass [kg]", lambda a: a.weight.WBat)

    print("\nFigures:")
    design_dashboard(serial, "02b_serial_dashboard.png", "Serial hybrid-electric design")

    # Try it: the gap widens if you lower eta_electric_motor_1/2 in common._energy()
    # (worse generator/motor) — the serial chain's double conversion is what you are paying for.


if __name__ == "__main__":
    main()
