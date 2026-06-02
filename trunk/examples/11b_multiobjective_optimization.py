"""Example 11b — Multi-objective optimization with pymoo (NSGA-II), in parallel.

Where example 11 minimizes a single objective over one variable, this one finds the whole
*Pareto front* of a 6-variable hybrid-electric design with two competing objectives:

    minimize  (take-off mass WTO,  mission fuel mass Wf)

Design variables (x):
    x[0] phi_takeoff   battery power split at take-off              [-]
    x[1] phi_climb     battery power split during climb              [-]
    x[2] phi_cruise    battery power split during cruise             [-]
    x[3] P_gt          Class-II gas-turbine nominal power            [W]
    x[4] P_em          Class-II electric-motor nominal power         [W]
    x[5] W/S           design wing loading (W_TO/S)                  [N/m^2]

**Meaningful ranges come from a Class-I pre-pass.** Before searching, we size one cheap,
all-Class-I hybrid (constant efficiencies, Class-I battery & structures). From it we read the
natural scales — the installed power ``DesignPW * WTO``, the constraint-optimized ("nominal")
wing loading ``DesignWTOoS``, and the landing-limited maximum wing loading ``WTOoSLanding`` —
and set the design-variable bounds around them. The wing loading is allowed to range from
below the nominal up to the landing limit, so the optimizer can shift W/S *to the right* of
the nominal point if that helps.

The search itself uses the Class-II battery and the Class-II gas-turbine / electric-motor
response-surface models, so a single evaluation is expensive — hence NSGA-II runs in
**parallel across CPU cores** and for only a **few generations**. Raise ``POP_SIZE`` /
``N_GEN`` for a production front (it costs proportionally more).

Run it (needs pymoo: ``pip install pymoo``):
    cd trunk && python examples/11b_multiobjective_optimization.py
"""

import os
import warnings
import multiprocessing as mp

import numpy as np

import PhlyGreen as pg
from common import hybrid_config

# --- search budget (small so the example finishes in a few minutes) -------------------
POP_SIZE = 12
N_GEN = 3
PHI_MAX = 0.3            # battery-split upper bound (kept modest for speed/feasibility)
PENALTY = 1.0e9         # objective value for designs that fail to close


def _set_phi(segments, name_prefix, phi):
    """Set a constant battery power split on every segment whose name starts with prefix."""
    for s in segments:
        if s.name.startswith(name_prefix):
            if s.phi is not None:
                s.phi = phi
            else:
                s.phi_start = phi
                s.phi_end = phi


def class_i_reference():
    """Size one all-Class-I hybrid to derive meaningful design-variable scales.

    Returns ``(P_inst, WS_nom, WS_max)``: the installed power ``DesignPW * WTO`` [W], the
    constraint-optimized nominal wing loading ``DesignWTOoS`` [N/m^2], and the landing-limited
    maximum wing loading ``WTOoSLanding`` [N/m^2] (the right-most feasible W/S).
    """
    cfg = hybrid_config(battery_class='I')      # Class-I battery; constant GT/EM; Class-I structures
    aircraft = pg.build_aircraft()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        aircraft.configure(cfg)
    P_inst = aircraft.DesignPW * aircraft.weight.WTO
    WS_nom = float(aircraft.DesignWTOoS)
    # Largest feasible W/S = the landing-constraint limit (same range FindDesignPoint uses).
    c = aircraft.constraint
    feasible = c.WTOoS[c.WTOoS <= c.WTOoSLanding]
    WS_max = float(feasible.max())
    return P_inst, WS_nom, WS_max


def evaluate_design(x):
    """Design one hybrid aircraft for parameter vector ``x`` -> (WTO, Wf) in kg.

    Top-level (picklable) so it can run in a multiprocessing pool. Returns a large penalty
    pair if the take-off-weight loop does not close (e.g. infeasible hybridization / wing).
    """
    phi_to, phi_climb, phi_cruise, p_gt, p_em, ws = x
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
        # Fix the design wing loading instead of letting the constraint diagram optimize it.
        cfg.design_wing_loading = float(ws)

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
        """2-objective (WTO, Wf) problem over the 6 design variables. Module-level so the
        problem instance is picklable for the multiprocessing starmap runner."""

        def __init__(self, xl, xu, **kwargs):
            super().__init__(n_var=len(xl), n_obj=2,
                             xl=np.asarray(xl, float), xu=np.asarray(xu, float), **kwargs)

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

    # 1. Class-I pre-pass -> meaningful design-variable ranges.
    P_inst, WS_nom, WS_max = class_i_reference()
    print("Class-I reference (sets the variable ranges):")
    print(f"  installed power  DesignPW*WTO : {P_inst/1e3:8.0f} kW")
    print(f"  nominal wing loading W/S      : {WS_nom:8.0f} N/m^2")
    print(f"  landing-limited max W/S       : {WS_max:8.0f} N/m^2")

    #            phi_to   phi_climb phi_cruise  P_gt          P_em          W/S
    xl = np.array([0.0,    0.0,      0.0,       1.0 * P_inst, 0.1 * P_inst, 0.8 * WS_nom])
    xu = np.array([PHI_MAX, PHI_MAX, PHI_MAX,   2.5 * P_inst, 1.0 * P_inst, WS_max])
    print(f"  P_gt range : {xl[3]/1e3:.0f} - {xu[3]/1e3:.0f} kW;  "
          f"P_em range : {xl[4]/1e3:.0f} - {xu[4]/1e3:.0f} kW;  "
          f"W/S range : {xl[5]:.0f} - {xu[5]:.0f} N/m^2")

    n_proc = max(mp.cpu_count() - 1, 1)
    print(f"\nRunning NSGA-II: pop={POP_SIZE}, gen={N_GEN}, on {n_proc} cores "
          f"(~{POP_SIZE * N_GEN} design evaluations).")

    with mp.Pool(n_proc) as pool:
        runner = StarmapParallelization(pool.starmap)
        problem = HybridDesignProblem(xl, xu, elementwise_runner=runner)
        result = minimize(problem, NSGA2(pop_size=POP_SIZE), ("n_gen", N_GEN),
                          seed=1, verbose=True)

    # 2. Keep only feasible (closed) designs and sort by take-off mass.
    F, X = result.F, np.atleast_2d(result.X)
    mask = np.all(F < PENALTY / 2, axis=1)
    F, X = F[mask], X[mask]
    if F.size == 0:
        print("No feasible designs found — widen the bounds or increase the budget.")
        return
    order = np.argsort(F[:, 0])
    F, X = F[order], X[order]

    print("\nPareto-optimal designs:")
    print(f"  {'WTO[kg]':>8} {'Wf[kg]':>7} | {'phiTO':>5} {'phiCl':>5} {'phiCr':>5} "
          f"{'Pgt[kW]':>8} {'Pem[kW]':>8} {'W/S':>6}  (W/S vs nom)")
    for (wto, wf), xr in zip(F, X):
        rel = xr[5] / WS_nom
        flag = "  >nominal" if rel > 1.02 else ("  <nominal" if rel < 0.98 else "  ~nominal")
        print(f"  {wto:8.0f} {wf:7.1f} | {xr[0]:5.2f} {xr[1]:5.2f} {xr[2]:5.2f} "
              f"{xr[3]/1e3:8.0f} {xr[4]/1e3:8.0f} {xr[5]:6.0f}  ({rel:4.2f} {flag.strip()})")

    n_right = int(np.sum(X[:, 5] > WS_nom * 1.02))
    print(f"\n{n_right} of {len(F)} Pareto designs sit to the RIGHT of the nominal W/S "
          f"({WS_nom:.0f} N/m^2).")

    _plot_pareto(F, X, WS_nom)


def _plot_pareto(F, X, WS_nom):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    out_dir = os.path.join(os.path.dirname(__file__), "_output")
    os.makedirs(out_dir, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.5, 5))
    # Colour each Pareto design by its wing loading to reveal whether right-shifted W/S
    # appears on the front.
    sc = ax.scatter(F[:, 0], F[:, 1], c=X[:, 5], cmap="viridis", s=70,
                    edgecolor="black", zorder=3)
    ax.plot(F[:, 0], F[:, 1], "-", color="grey", alpha=0.5, zorder=2)
    cbar = fig.colorbar(sc, label="design wing loading W/S [N/m$^2$]")
    cbar.ax.axhline(WS_nom, color="red", lw=2)
    cbar.ax.text(1.6, WS_nom, " nominal", color="red", va="center", fontsize=8)
    ax.set_xlabel("take-off mass WTO [kg]")
    ax.set_ylabel("mission fuel mass Wf [kg]")
    ax.set_title("Hybrid-electric Pareto front (NSGA-II), coloured by W/S")
    ax.grid(alpha=0.3)
    path = os.path.join(out_dir, "11b_pareto_front.png")
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    print(f"\nSaved Pareto front to {path}")


if __name__ == "__main__":
    main()
