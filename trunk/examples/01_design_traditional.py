"""Example 01 — Design a conventional (fuel-only) aircraft.

The simplest end-to-end use of PhlyGreen: build an aircraft, hand it a design
specification, run the sizing loop, and read the results.

Run it:
    cd trunk && python examples/01_design_traditional.py

Then try: open common.py and change `range_mission` or `payload_weight`, re-run, and watch
the take-off weight change.
"""

import PhlyGreen as pg
from common import traditional_config


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

    # 4. Read the outcome as a structured object (no parsing of printed text).
    results = aircraft.results()
    print(f"Take-off weight : {results.WTO:8.1f} kg")
    print(f"Mission fuel    : {results.Wf:8.1f} kg")
    print(f"Empty weight    : {results.empty_weight:8.1f} kg")
    print(f"Wing area       : {results.WingSurface:8.1f} m^2")
    print(f"Engine rating   : {results.engineRating/1000:8.1f} kW")


if __name__ == "__main__":
    main()
