"""Example 11 — Optimization: choose the cruise Mach that minimizes block fuel.

A design optimization is just "minimize an objective computed by a design run, over some
parameters". Here the parameter is the cruise Mach number and the objective is block fuel.
We use SciPy's bounded scalar minimizer so the example runs with no extra dependencies.

For multi-objective / population methods (e.g. NSGA-II for a Pareto front) the same
`objective(x)` plugs straight into `pymoo` — see the note at the bottom.

Run it:
    cd trunk && python examples/11_optimization.py
"""

import numpy as np
from scipy.optimize import minimize_scalar

import PhlyGreen as pg
from common import traditional_config, savefig


def set_cruise_mach(config, mach):
    """Encode the parameter: set the cruise segment's Mach number."""
    for seg in config.mission_stages.segments:
        if seg.name == "Cruise":
            seg.inputs["Mach"] = float(mach)


def main():
    base = traditional_config()

    def objective(mach):
        fuel = pg.evaluate(base, set_cruise_mach, mach).block_fuel
        print(f"  cruise Mach {mach:.3f}  ->  block fuel {fuel:8.1f} kg")
        return fuel

    print("Searching cruise Mach in [0.32, 0.50] for minimum block fuel:")
    result = minimize_scalar(objective, bounds=(0.32, 0.50), method="bounded",
                             options={"xatol": 1e-3})

    print(f"\nOptimum cruise Mach : {result.x:.3f}")
    print(f"Minimum block fuel  : {result.fun:.1f} kg")

    # Map the whole objective curve so the optimum is visible, not just asserted.
    machs = np.linspace(0.32, 0.50, 10)
    fuels = [pg.evaluate(base, set_cruise_mach, m).block_fuel for m in machs]
    _plot(machs, fuels, result.x, result.fun)

    # Production multi-objective version (Pareto front) lives in example 11b
    # (pymoo NSGA-II over several design variables, in parallel).


def _plot(machs, fuels, x_opt, f_opt):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(machs, fuels, "o-", color="tab:blue", label="block fuel")
    ax.plot([x_opt], [f_opt], "*", ms=16, color="tab:red", label="optimum")
    ax.set_xlabel("cruise Mach"); ax.set_ylabel("block fuel [kg]")
    ax.set_title("Block fuel vs cruise Mach"); ax.grid(alpha=0.3); ax.legend()
    fig.tight_layout()
    print("\nFigures:")
    savefig(fig, "11_optimization_curve.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
