"""Example 10 — A parameter sweep (the simplest outer loop).

`pg.evaluate(base_config, apply, x)` runs one design for parameter `x` applied to a fresh
copy of the baseline — it never mutates the baseline, so it is safe to call in a loop.
Here we sweep the design range and look at how take-off weight and block fuel grow.

Run it:
    cd trunk && python examples/10_parameter_sweep.py
"""

import numpy as np

import PhlyGreen as pg
from common import traditional_config


def set_range(config, range_nm):
    """Encode the parameter: set the design mission range [nautical miles]."""
    config.mission.range_mission = range_nm


def main():
    base = traditional_config()
    ranges = np.linspace(400, 1000, 7)

    print(f"{'range [nm]':>11} {'WTO [kg]':>10} {'block fuel [kg]':>16}")
    wto, fuel = [], []
    for r in ranges:
        res = pg.evaluate(base, set_range, r)
        wto.append(res.WTO)
        fuel.append(res.block_fuel)
        print(f"{r:11.0f} {res.WTO:10.1f} {res.block_fuel:16.1f}")

    _maybe_plot(ranges, wto, fuel)


def _maybe_plot(ranges, wto, fuel):
    try:
        import os
        import matplotlib
        matplotlib.use("Agg")  # headless: just save a file
        import matplotlib.pyplot as plt
    except Exception:
        return
    fig, ax1 = plt.subplots()
    ax1.plot(ranges, wto, "o-", color="tab:blue", label="WTO")
    ax1.set_xlabel("design range [nm]"); ax1.set_ylabel("WTO [kg]", color="tab:blue")
    ax2 = ax1.twinx()
    ax2.plot(ranges, fuel, "s--", color="tab:red", label="block fuel")
    ax2.set_ylabel("block fuel [kg]", color="tab:red")
    os.makedirs("examples/_output", exist_ok=True)
    fig.savefig("examples/_output/parameter_sweep.png", dpi=120, bbox_inches="tight")
    print("\nSaved examples/_output/parameter_sweep.png")


if __name__ == "__main__":
    main()
