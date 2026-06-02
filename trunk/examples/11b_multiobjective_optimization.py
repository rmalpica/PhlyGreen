"""Example 11b — Multi-objective optimization with pymoo (NSGA-II), in parallel.

Where example 11 minimizes a single objective over one variable, this one finds the whole
*Pareto front* of a 5-variable hybrid-electric design with two competing objectives:

    minimize  (take-off mass WTO,  mission fuel mass Wf)

Design variables (x):
    x[0] phi_takeoff   battery power split at take-off          [-]
    x[1] phi_climb     battery power split during climb          [-]
    x[2] phi_cruise    battery power split during cruise         [-]
    x[3] P_gt          Class-II gas-turbine nominal power        [W]
    x[4] P_em          Class-II electric-motor nominal power     [W]

The model uses the Class-II battery (cell-level) and the Class-II gas-turbine / electric-motor
response-surface models, so a single design evaluation is expensive — hence NSGA-II is run in
**parallel across CPU cores** and for only a **few generations**. Increase `POP_SIZE` /
`N_GEN` below for a production run (it will take proportionally longer).

More battery use (higher phi) burns less fuel but needs a bigger, heavier pack — so the two
objectives trade off and the result is a front, not a single point.

Run it (needs pymoo: ``pip install pymoo``):
    cd trunk && python examples/11b_multiobjective_optimization.py
"""

import os
import warnings
import multiprocessing as mp

import numpy as np

import PhlyGreen as pg
from common import hybrid_config

# --- search settings (small so the example finishes in a few minutes) -----------------
# A single Class-II (cell-level battery + response-surface GT/EM) design takes tens of
# seconds, and stiff high-hybridization cases more, so keep the budget small here and raise
# POP_SIZE / N_GEN for a production front. The battery-power-split upper bound is kept modest
# (0.3) and the gas-turbine lower bound generous (5 MW) so designs stay feasible and fast.
POP_SIZE = 12
N_GEN = 3
# Design-variable bounds: [phi_to, phi_climb, phi_cruise, P_gt (W), P_em (W)]
XL = np.array([0.0, 0.0, 0.0, 5.0e6, 3.0e5])
XU = np.array([0.3, 0.3, 0.3, 1.0e7, 2.0e6])
PENALTY = 1.0e9          # objective value for designs that fail to close


def _set_phi(segments, name_prefix, phi):
    """Set a constant battery power split on every segment whose name starts with prefix."""
    for s in segments:
        if s.name.startswith(name_prefix):
            if s.phi is not None:
                s.phi = phi
            else:
                s.phi_start = phi
                s.phi_end = phi


def evaluate_design(x):
    """Design one hybrid aircraft for parameter vector ``x`` -> (WTO, Wf) in kg.

    Top-level (picklable) so it can run in a multiprocessing pool. Returns a large penalty
    pair if the take-off-weight loop does not close (e.g. infeasible hybridization).
    """
    phi_to, phi_climb, phi_cruise, p_gt, p_em = x
    try:
        cfg = hybrid_config(battery_class='II')
        _set_phi(cfg.mission_stages.segments, 'Takeoff', float(phi_to))
        _set_phi(cfg.mission_stages.segments, 'Climb', float(phi_climb))
        _set_phi(cfg.mission_stages.segments, 'Cruise', float(phi_cruise))
        # Class-II propulsion at the chosen nominal powers.
        cfg.energy.eta_gas_turbine_model = 'ResponseSurface'
        cfg.energy.gt_design_power = float(p_gt)
        cfg.energy.eta_electric_motor_model = 'Smart'
        cfg.energy.em_design_power = float(p_em)
        cfg.energy.em_design_voltage = 800.0
        cfg.energy.em_design_rpm = 11000.0

        aircraft = pg.build_aircraft()
        aircraft.PropellerInput = {'Number of Engines': 2}    # ATR-class twin
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            aircraft.configure(cfg)
        res = aircraft.results()
        wto, wf = res.WTO, res.Wf
        if wto is None or wf is None or not np.isfinite(wto) or not np.isfinite(wf):
            return PENALTY, PENALTY
        return float(wto), float(wf)
    except Exception:
        return PENALTY, PENALTY


try:
    from pymoo.core.problem import ElementwiseProblem

    class HybridDesignProblem(ElementwiseProblem):
        """2-objective (WTO, Wf) problem over the 5 design variables. Module-level so the
        problem instance is picklable for the multiprocessing starmap runner."""

        def __init__(self, **kwargs):
            super().__init__(n_var=5, n_obj=2, xl=XL, xu=XU, **kwargs)

        def _evaluate(self, x, out, *args, **kwargs):
            out["F"] = list(evaluate_design(x))
except ImportError:               # pymoo not installed; main() will report it
    HybridDesignProblem = None


def main():
    from pymoo.algorithms.moo.nsga2 import NSGA2
    from pymoo.optimize import minimize
    try:                                              # pymoo >= 0.6.1
        from pymoo.parallelization import StarmapParallelization
    except ImportError:                               # older pymoo
        from pymoo.core.problem import StarmapParallelization

    n_proc = max(mp.cpu_count() - 1, 1)
    print(f"Running NSGA-II: pop={POP_SIZE}, gen={N_GEN}, on {n_proc} cores "
          f"(~{POP_SIZE * N_GEN} design evaluations).")

    with mp.Pool(n_proc) as pool:
        runner = StarmapParallelization(pool.starmap)
        problem = HybridDesignProblem(elementwise_runner=runner)
        result = minimize(problem, NSGA2(pop_size=POP_SIZE), ("n_gen", N_GEN),
                          seed=1, verbose=True)

    # Keep only feasible (closed) designs.
    F = result.F[np.all(result.F < PENALTY / 2, axis=1)]
    if F.size == 0:
        print("No feasible designs found — widen the bounds or increase the budget.")
        return
    order = np.argsort(F[:, 0])
    F = F[order]
    print("\nPareto-optimal designs (WTO, Wf) [kg]:")
    for wto, wf in F:
        print(f"  WTO {wto:8.0f}   Wf {wf:7.1f}")

    _plot_pareto(F)


def _plot_pareto(F):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir = os.path.join(os.path.dirname(__file__), "_output")
    os.makedirs(out_dir, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot(F[:, 0], F[:, 1], "o-", color="tab:blue", mfc="white")
    ax.set_xlabel("take-off mass WTO [kg]")
    ax.set_ylabel("mission fuel mass Wf [kg]")
    ax.set_title("Hybrid-electric Pareto front (NSGA-II)")
    ax.grid(alpha=0.3)
    path = os.path.join(out_dir, "11b_pareto_front.png")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    print(f"\nSaved Pareto front to {path}")


if __name__ == "__main__":
    main()
