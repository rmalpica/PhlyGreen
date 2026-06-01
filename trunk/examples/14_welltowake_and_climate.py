"""Example 14 — Well-to-wake energy, emissions and climate impact.

A hybrid design carries a well-to-tank chain and a climate-impact model, so beyond the
take-off weight you can look at the *source* energy (well-to-wake), the mission emissions,
and the resulting climate metric (ATR — Average Temperature Response).

Run it:
    cd trunk && python examples/14_welltowake_and_climate.py
"""

import PhlyGreen as pg
from common import hybrid_config


def main():
    aircraft = pg.build_aircraft()
    aircraft.configure(hybrid_config())   # hybrid carries WellToTank + ClimateImpact inputs

    # --- Well-to-wake energy (fuel + electricity traced back to the primary source) ---
    print("=== Well-to-wake ===")
    print(f"source energy : {aircraft.welltowake.SourceEnergy/1e6:10.1f} MJ")
    print(f"Psi (electric source fraction) : {aircraft.welltowake.Psi:6.4f}")

    # --- Mission emissions and climate impact ---
    aircraft.MissionType = 'Continue'
    aircraft.climateimpact.calculate_mission_emissions()
    emissions = aircraft.climateimpact.mission_emissions
    print("\n=== Mission emissions [kg] ===")
    for species, value in emissions.items():
        print(f"  {species:5s}: {float(value):10.2f}")

    atr = aircraft.climateimpact.ATR()
    print(f"\nClimate impact (ATR): {atr:.3e} K")

    _maybe_plot(emissions)


def _maybe_plot(emissions):
    try:
        import os
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar([k.upper() for k in emissions], [float(v) for v in emissions.values()],
           color="tab:brown")
    ax.set_ylabel("mission emissions [kg]"); ax.set_yscale("log")
    ax.grid(axis="y", alpha=0.3)
    os.makedirs("examples/_output", exist_ok=True)
    fig.savefig("examples/_output/emissions.png", dpi=120, bbox_inches="tight")
    print("\nSaved examples/_output/emissions.png")


if __name__ == "__main__":
    main()
