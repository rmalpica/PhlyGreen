"""Example 02 — Design a hybrid-electric aircraft with a battery.

Same workflow as Example 01, but a *parallel hybrid*: part of the propulsive power comes
from a battery-fed electric motor. How much is set by the supplied-power ratio 'phi' on
each flight segment (see the Cruise segment in common.py, which ramps phi up to 0.5).

Run it:
    cd trunk && python examples/02_hybrid_with_battery.py
"""

import PhlyGreen as pg
from common import hybrid_config


def main():
    aircraft = pg.build_aircraft()
    config = hybrid_config()

    aircraft.configure(config)
    r = aircraft.results()

    print(f"Take-off weight   : {r.WTO:8.1f} kg")
    print(f"Mission fuel      : {r.Wf:8.1f} kg")
    print(f"Battery mass      : {r.WBat:8.1f} kg")
    print(f"Powertrain mass   : {r.WPT:8.1f} kg")
    print(f"Battery pack      : {r.pack_energy/3.6e6:8.1f} kWh, "
          f"{r.pack_power_max/1000:8.1f} kW (S{r.S_number:.0f}/P{r.P_number:.0f})")
    print(f"Well-to-wake Psi  : {r.Psi:8.4f}")

    # Try it: in common.py raise the cruise phi_end (e.g. 0.5 -> 0.7) and re-run.
    # The battery gets heavier while mission fuel drops — the core hybrid trade.


if __name__ == "__main__":
    main()
