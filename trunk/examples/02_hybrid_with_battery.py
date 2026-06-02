"""Example 02 — Design a hybrid-electric aircraft with a battery.

Same workflow as Example 01, but a *parallel hybrid*: part of the propulsive power comes
from a battery-fed electric motor. How much is set by the supplied-power ratio 'phi' on
each flight segment (see the Cruise segment in common.py, which ramps phi up to 0.5).

Run it:
    cd trunk && python examples/02_hybrid_with_battery.py
"""

import PhlyGreen as pg
from common import hybrid_config, print_results, design_dashboard


def main():
    aircraft = pg.build_aircraft()
    config = hybrid_config()

    # Optional: fix the design wing loading W/S [N/m^2] (else it is optimized from the
    # constraint diagram). Uncomment to impose your own value:
    # config.design_wing_loading = 3000.0

    aircraft.configure(config)

    # Full summary (incl. battery pack specs, well-to-wake, and the mass breakdown).
    results = print_results(aircraft, "Parallel hybrid-electric ATR-like turboprop")

    # Echo every input that produced this design — handy to confirm exactly what was solved
    # (here: Hybrid/Parallel, Class-II battery, the cruise phi ramp, etc.).
    print()
    print(results.input_summary())

    # Dashboard: the energy panel also shows battery energy and state-of-charge; the
    # constraint diagram and mass breakdown round it out.
    print("\nFigures:")
    design_dashboard(aircraft, "02_hybrid_dashboard.png", "Hybrid-electric design")

    # Try it: in common.py raise the cruise phi_end (e.g. 0.5 -> 0.7) and re-run.
    # The battery gets heavier while mission fuel drops — the core hybrid trade.


if __name__ == "__main__":
    main()
