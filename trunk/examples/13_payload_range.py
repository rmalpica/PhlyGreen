"""Example 13 — A payload–range study (a 2-D design sweep).

Sweeping two parameters at once maps out the design space. Here we size the aircraft across
a grid of payloads and ranges and tabulate the block fuel — the kind of study that feeds a
payload–range diagram. It reuses the same `pg.evaluate` building block as the other outer
loops, just over two parameters.

Run it:
    cd trunk && python examples/13_payload_range.py
"""

import numpy as np

import PhlyGreen as pg
from common import traditional_config


def apply_payload_range(config, x):
    payload, range_nm = x
    config.mission.payload_weight = payload
    config.mission.range_mission = range_nm


def main():
    base = traditional_config()
    payloads = [3000, 4000, 5000]
    ranges = [400, 700, 1000]

    print("Block fuel [kg] over a payload x range grid:")
    print("payload\\range " + "".join(f"{r:>10.0f}" for r in ranges))
    grid = np.zeros((len(payloads), len(ranges)))
    for i, p in enumerate(payloads):
        row = []
        for j, r in enumerate(ranges):
            res = pg.evaluate(base, apply_payload_range, (p, r))
            grid[i, j] = res.block_fuel
            row.append(res.block_fuel)
        print(f"{p:>12.0f} " + "".join(f"{v:10.1f}" for v in row))

    _maybe_contour(payloads, ranges, grid)


def _maybe_contour(payloads, ranges, grid):
    try:
        import os
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    R, P = np.meshgrid(ranges, payloads)
    fig, ax = plt.subplots()
    cs = ax.contourf(R, P, grid, levels=12, cmap="viridis")
    fig.colorbar(cs, label="block fuel [kg]")
    ax.set_xlabel("range [nm]"); ax.set_ylabel("payload [kg]")
    os.makedirs("examples/_output", exist_ok=True)
    fig.savefig("examples/_output/payload_range.png", dpi=120, bbox_inches="tight")
    print("\nSaved examples/_output/payload_range.png")


if __name__ == "__main__":
    main()
