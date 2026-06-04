"""Example 22 — The cryogenic liquid-hydrogen (LH2) tank.

Hydrogen is stored as a cryogenic liquid (~20 K). Heat leaking through the insulation
boils some of it off, raising the tank pressure; a valve vents gas when the pressure
reaches its maximum, and a heater adds power when it drops to the minimum. This example
sizes the tank for the design hydrogen load, then re-flies the mission while advancing the
tank's thermodynamic state, and plots:

  * tank pressure vs time (regulated between P_min and P_max),
  * stored hydrogen mass vs time (depletes as it is consumed + vented),
  * H2 mass flow leaving the tank into the fuel cell (the propulsive demand),
  * vent flow and heat flows vs time.

Requires CoolProp (para-hydrogen properties). Install with: pip install CoolProp

Run it:
    cd trunk && python examples/22_hydrogen_tank.py
"""

import numpy as np

import PhlyGreen as pg
from common import hydrogen_config, print_results, design_dashboard, savefig


def main():
    # 1. Size the hydrogen aircraft *with* a cryogenic tank (TankConfig attached).
    aircraft = pg.build_aircraft()
    aircraft.configure(hydrogen_config(tank=True))
    tank = aircraft.tank

    print_results(aircraft, "Hydrogen aircraft with cryogenic LH2 tank")

    print("\n=== LH2 tank (sized for the design hydrogen load) ===")
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
    feed = np.array(h['Consumption'])    # kg/s — H2 drawn from the tank to feed the fuel cell
    print("\n=== Mission tank behavior ===")
    print(f"Pressure swing      : {P.min():.3f} - {P.max():.3f} bar")
    print(f"Hydrogen mass       : {m[0]:.1f} -> {m[-1]:.1f} kg")
    print(f"Total vented        : {h['m_vent_cum'][-1]:.2f} kg")
    print(f"H2 feed to fuel cell: {feed.min()*1000:.2f} - {feed.max()*1000:.2f} g/s")
    print(f"Peak heat leak      : {max(h['Q_in']):.0f} W;  peak heater: {max(h['Q_heater']):.0f} W")

    print("\nFigures:")
    _maybe_plot(t, P, m, vent, feed, h)
    design_dashboard(aircraft, "22_hydrogen_dashboard.png", "Hydrogen + LH2 tank design")


def _maybe_plot(t, P, m, vent, feed, h):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    Q_in = np.array(h['Q_in'])
    Q_heat = np.array(h['Q_heater'])
    fig, axes = plt.subplots(5, 1, sharex=True, figsize=(8, 13))
    axes[0].plot(t, P, color="tab:blue"); axes[0].set_ylabel("pressure [bar]")
    axes[0].axhline(P.min(), ls=":", c="grey"); axes[0].axhline(P.max(), ls=":", c="grey")
    axes[1].plot(t, m, color="tab:green"); axes[1].set_ylabel("stored H2 [kg]")
    # H2 mass flow leaving the tank and going into the fuel cell (the propulsive demand).
    axes[2].plot(t, feed * 1000.0, color="tab:cyan"); axes[2].set_ylabel("H2 to fuel cell [g/s]")
    axes[3].plot(t, vent, color="tab:red"); axes[3].set_ylabel("vent flow [kg/s]")
    axes[4].plot(t, Q_in, color="tab:orange", label="heat leak")
    axes[4].plot(t, Q_heat, color="tab:purple", label="heater")
    axes[4].set_ylabel("heat flow [W]"); axes[4].legend(fontsize=8)
    axes[4].set_xlabel("time [min]")
    for ax in axes:
        ax.grid(alpha=0.3)
    fig.suptitle("LH2 tank state over the mission")
    fig.tight_layout()
    savefig(fig, "22_hydrogen_tank.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
