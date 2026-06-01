"""Example 11 — Optimization: choose the cruise Mach that minimizes block fuel.

A design optimization is just "minimize an objective computed by a design run, over some
parameters". Here the parameter is the cruise Mach number and the objective is block fuel.
We use SciPy's bounded scalar minimizer so the example runs with no extra dependencies.

For multi-objective / population methods (e.g. NSGA-II for a Pareto front) the same
`objective(x)` plugs straight into `pymoo` — see the note at the bottom.

Run it:
    cd trunk && python examples/11_optimization.py
"""

from scipy.optimize import minimize_scalar

import PhlyGreen as pg
from common import traditional_config


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

    # Production multi-objective version (Pareto front), if pymoo is installed:
    #   from pymoo.core.problem import ElementwiseProblem
    #   class P(ElementwiseProblem):
    #       def _evaluate(self, x, out, *a, **k):
    #           r = pg.evaluate(base, set_cruise_mach, x[0])
    #           out["F"] = [r.WTO, r.block_fuel]
    #   ... then minimize(P(n_var=1, n_obj=2, xl=[0.32], xu=[0.50]), NSGA2(), ...)


if __name__ == "__main__":
    main()
