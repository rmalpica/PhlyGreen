"""Example 01 — Design a conventional (fuel-only) aircraft.

The simplest end-to-end use of PhlyGreen: build an aircraft, hand it a design
specification, run the sizing loop, and read the results.

Run it:
    cd trunk && python examples/01_design_traditional.py

Then try: open common.py and change `range_mission` or `payload_weight`, re-run, and watch
the take-off weight change.
"""

import os

import PhlyGreen as pg
from common import traditional_config, print_results, design_dashboard, OUTPUT_DIR


def main():
    # 1. A fully-wired aircraft (all subsystems created and cross-linked for you).
    aircraft = pg.build_aircraft()

    # 2. A validated design specification (see common.py).
    config = traditional_config()

    # Optional: fix the design wing loading W/S [N/m^2] instead of letting the constraint
    # analysis optimize it. Comment this out to recover the optimized design point.
    # config.design_wing_loading = 3000.0

    # 3. Size the aircraft: find the design point, then iterate take-off weight to
    #    convergence (Brent's method) so component masses are mutually consistent.
    aircraft.configure(config)            # runs the full DesignAircraft loop

    # 4. Print a full, human-readable summary (scalars + take-off mass breakdown).
    results = print_results(aircraft, "Conventional ATR-like turboprop")

    # 4b. Keep a record of *what was actually solved*: results.input_summary() echoes every
    #     configuration flag and input block (mission, aerodynamics, constraints, energy,
    #     flight segments, ...). results.inputs holds the same data as a dict.
    print()
    print(results.input_summary())

    # 5. Plot a dashboard: flight profile, cumulative fuel energy, the constraint diagram
    #    with the design point, and the mass breakdown.
    print("\nFigures:")
    design_dashboard(aircraft, "01_traditional_dashboard.png", "Traditional design")

    # 5b. Power flow over the mission: propulsive, gas-turbine and electric-motor power
    #     (totals for the whole aircraft; the electric motor is zero for a fuel-only design).
    _plot_power(aircraft, "01_power_timeseries.png", "Traditional — mission power")

    # 6. For debugging you can dump the time-evolving mission variables to a CSV — the raw ODE
    #    states, the derived mission quantities and the propulsive / gas-turbine / electric-motor
    #    power. write_timeseries automatically detects which components used a Class-II model;
    #    this constant-efficiency design has none, so no surrogate is loaded.
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    csv = aircraft.results().write_timeseries(os.path.join(OUTPUT_DIR, "01_timeseries.csv"))
    print(f"  saved {csv}  (mission states + powers vs time)")


def _plot_power(aircraft, name, title):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from PhlyGreen import postprocess as pp
    except Exception:
        return
    from common import savefig
    ax = pp.plot_power_timeseries(aircraft)
    ax.set_title(title)
    fig = ax.figure
    fig.tight_layout()
    savefig(fig, name)
    plt.close(fig)


if __name__ == "__main__":
    main()
