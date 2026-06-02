"""Example 10 — A parameter sweep (the simplest outer loop).

`pg.evaluate(base_config, apply, x)` runs one design for parameter `x` applied to a fresh
copy of the baseline — it never mutates the baseline, so it is safe to call in a loop.
Here we sweep the design range and look at how take-off weight and block fuel grow.

Run it:
    cd trunk && python examples/10_parameter_sweep.py
"""

import numpy as np

import PhlyGreen as pg
from common import traditional_config, savefig


def set_range(config, range_nm):
    """Encode the parameter: set the design mission range [nautical miles]."""
    config.mission.range_mission = range_nm


def main():
    base = traditional_config()
    ranges = np.linspace(400, 1000, 7)

    print(f"{'range [nm]':>11} {'WTO [kg]':>10} {'empty [kg]':>11} {'block fuel [kg]':>16}")
    wto, empty, fuel = [], [], []
    for r in ranges:
        res = pg.evaluate(base, set_range, r)
        wto.append(res.WTO); empty.append(res.empty_weight); fuel.append(res.block_fuel)
        print(f"{r:11.0f} {res.WTO:10.1f} {res.empty_weight:11.1f} {res.block_fuel:16.1f}")

    growth = (wto[-1] - wto[0]) / (ranges[-1] - ranges[0])
    print(f"\nTake-off-weight growth: {growth:.1f} kg per extra nm of design range.")

    _maybe_plot(ranges, wto, empty, fuel)


def _maybe_plot(ranges, wto, empty, fuel):
    try:
        import matplotlib
        matplotlib.use("Agg")  # headless: just save a file
        import matplotlib.pyplot as plt
    except Exception:
        return
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(13, 4.5))
    axL.plot(ranges, wto, "o-", color="tab:blue", label="WTO")
    axL.plot(ranges, empty, "^-", color="tab:green", label="empty weight")
    axL.set_xlabel("design range [nm]"); axL.set_ylabel("mass [kg]")
    axL.set_title("Weights vs design range"); axL.grid(alpha=0.3); axL.legend()

    axR.plot(ranges, fuel, "s--", color="tab:red")
    axR.set_xlabel("design range [nm]"); axR.set_ylabel("block fuel [kg]")
    axR.set_title("Block fuel vs design range"); axR.grid(alpha=0.3)
    fig.tight_layout()
    print("\nFigures:")
    savefig(fig, "10_parameter_sweep.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
