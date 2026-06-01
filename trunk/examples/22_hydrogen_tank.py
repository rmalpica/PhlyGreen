"""Example 22 — The cryogenic liquid-hydrogen (LH2) tank.

Hydrogen is stored as a cryogenic liquid (~20 K). Heat leaking through the insulation
boils some of it off, raising the tank pressure; a valve vents gas when the pressure
reaches its maximum, and a heater adds power when it drops to the minimum. This example
sizes the tank for the design hydrogen load, then re-flies the mission while advancing the
tank's thermodynamic state, and plots:

  * tank pressure vs time (regulated between P_min and P_max),
  * stored hydrogen mass vs time (depletes as it is consumed + vented),
  * vent flow and heat flows vs time.

Requires CoolProp (para-hydrogen properties). Install with: pip install CoolProp

Run it:
    cd trunk && python examples/22_hydrogen_tank.py
"""

import numpy as np

import PhlyGreen as pg
from common import hydrogen_config


def main():
    # 1. Size the hydrogen aircraft *with* a cryogenic tank (TankConfig attached).
    aircraft = pg.build_aircraft()
    aircraft.configure(hydrogen_config(tank=True))
    tank = aircraft.tank

    print("=== LH2 tank (sized for the design hydrogen load) ===")
    print(f"Stored hydrogen     : {aircraft.weight.WH2_Fuel:8.1f} kg")
    print(f"Tank empty mass     : {aircraft.weight.WTank:8.1f} kg ({tank.n_tanks} tank(s))")
    print(f"Geometry            : {tank.shape}, r_inner = {tank.r_inner:.2f} m, "
          f"D_outer = {tank.D_outer:.2f} m")
    print(f"Gravimetric index   : {tank.gravimetric_index:8.3f}  (H2 / (H2 + tank))")
    print(f"Pressure limits     : {tank.P_min/1e5:.2f} - {tank.P_max/1e5:.2f} bar")

    # 2. Re-fly the mission with the tank thermodynamics switched on.
    aircraft.mission.track_tank = True
    aircraft.mission.EvaluateMission(aircraft.weight.WTO)
    h = aircraft.tank.history

    t = np.array(h['t']) / 60.0          # minutes
    P = np.array(h['P'])                 # bar
    m = np.array(h['m_tot'])             # kg
    vent = np.array(h['Vent'])           # kg/s
    print("\n=== Mission tank behavior ===")
    print(f"Pressure swing      : {P.min():.3f} - {P.max():.3f} bar")
    print(f"Hydrogen mass       : {m[0]:.1f} -> {m[-1]:.1f} kg")
    print(f"Total vented        : {h['m_vent_cum'][-1]:.2f} kg")
    print(f"Peak heat leak      : {max(h['Q_in']):.0f} W;  peak heater: {max(h['Q_heater']):.0f} W")

    _maybe_plot(t, P, m, vent, h)


def _maybe_plot(t, P, m, vent, h):
    try:
        import os
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(8, 9))
    axes[0].plot(t, P, color="tab:blue"); axes[0].set_ylabel("pressure [bar]")
    axes[0].axhline(P.min(), ls=":", c="grey"); axes[0].axhline(P.max(), ls=":", c="grey")
    axes[1].plot(t, m, color="tab:green"); axes[1].set_ylabel("stored H2 [kg]")
    axes[2].plot(t, vent, color="tab:red"); axes[2].set_ylabel("vent flow [kg/s]")
    axes[2].set_xlabel("time [min]")
    for ax in axes:
        ax.grid(alpha=0.3)
    os.makedirs("examples/_output", exist_ok=True)
    fig.savefig("examples/_output/hydrogen_tank.png", dpi=120, bbox_inches="tight")
    print("\nSaved examples/_output/hydrogen_tank.png")


if __name__ == "__main__":
    main()
