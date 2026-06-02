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
from common import traditional_config, savefig


def apply_payload_range(config, x):
    payload, range_nm = x
    config.mission.payload_weight = payload
    config.mission.range_mission = range_nm


def main():
    base = traditional_config()
    payloads = np.array([3000, 3500, 4000, 4500, 5000])
    ranges = np.array([400, 550, 700, 850, 1000])

    print("Block fuel [kg] over a payload x range grid:")
    print("payload\\range " + "".join(f"{r:>10.0f}" for r in ranges))
    fuel = np.zeros((len(payloads), len(ranges)))
    wto = np.zeros_like(fuel)
    for i, p in enumerate(payloads):
        row = []
        for j, r in enumerate(ranges):
            res = pg.evaluate(base, apply_payload_range, (p, r))
            fuel[i, j] = res.block_fuel
            wto[i, j] = res.WTO
            row.append(res.block_fuel)
        print(f"{p:>12.0f} " + "".join(f"{v:10.1f}" for v in row))

    _maybe_contour(payloads, ranges, fuel, wto)


def _maybe_contour(payloads, ranges, fuel, wto):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    R, P = np.meshgrid(ranges, payloads)
    fig, (axF, axW) = plt.subplots(1, 2, figsize=(13, 5))
    for ax, Z, label in ((axF, fuel, "block fuel [kg]"), (axW, wto, "WTO [kg]")):
        cs = ax.contourf(R, P, Z, levels=14, cmap="viridis")
        ax.contour(R, P, Z, levels=8, colors="white", linewidths=0.5, alpha=0.6)
        fig.colorbar(cs, ax=ax, label=label)
        ax.set_xlabel("range [nm]"); ax.set_ylabel("payload [kg]")
        ax.set_title(label.split(" [")[0])
    fig.tight_layout()
    print("\nFigures:")
    savefig(fig, "13_payload_range.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
