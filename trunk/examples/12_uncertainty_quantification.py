"""Example 12 — Uncertainty quantification by Monte Carlo.

Real inputs are uncertain. Here we treat the gas-turbine efficiency, the fuel specific
energy and the payload as random, sample many designs, and look at the resulting spread in
take-off weight. This uses plain NumPy random sampling so it runs anywhere.

For spectral methods (polynomial chaos, far fewer model runs for smooth responses) the same
`model(sample)` plugs into `chaospy` — see the note at the bottom.

Run it (takes a few seconds):
    cd trunk && python examples/12_uncertainty_quantification.py
"""

import numpy as np

import PhlyGreen as pg
from common import traditional_config

N_SAMPLES = 64   # increase for smoother statistics (each sample is one full design)


def apply_sample(config, sample):
    """Encode one random draw onto the config."""
    eta_gt, Ef, payload = sample
    config.energy.eta_gas_turbine = eta_gt
    config.energy.Ef = Ef
    config.mission.payload_weight = payload


def main():
    rng = np.random.default_rng(seed=0)   # reproducible
    base = traditional_config()

    # Draw the uncertain inputs.
    eta_gt = rng.uniform(0.20, 0.24, N_SAMPLES)         # gas-turbine efficiency
    Ef = rng.normal(43.5e6, 0.5e6, N_SAMPLES)           # fuel specific energy [J/kg]
    payload = rng.normal(4560, 150, N_SAMPLES)          # payload [kg]

    wto = np.array([pg.evaluate(base, apply_sample, s).WTO
                    for s in zip(eta_gt, Ef, payload)])

    print(f"Take-off weight over {N_SAMPLES} random designs:")
    print(f"  mean   : {wto.mean():8.1f} kg")
    print(f"  std    : {wto.std():8.1f} kg")
    print(f"  min/max: {wto.min():8.1f} / {wto.max():8.1f} kg")
    print(f"  5-95%  : {np.percentile(wto, 5):8.1f} - {np.percentile(wto, 95):8.1f} kg")

    _plot(wto, eta_gt)

    # Polynomial-chaos version (if chaospy is installed):
    #   import chaospy
    #   dist = chaospy.J(chaospy.Uniform(0.20, 0.24), chaospy.Normal(43.5e6, 0.5e6),
    #                    chaospy.Normal(4560, 150))
    #   nodes, weights = chaospy.generate_quadrature(3, dist, rule="gaussian")
    #   evals = [pg.evaluate(base, apply_sample, n).WTO for n in nodes.T]
    #   surrogate = chaospy.fit_quadrature(chaospy.generate_expansion(3, dist),
    #                                      nodes, weights, evals)
    #   print(chaospy.E(surrogate, dist), chaospy.Std(surrogate, dist))


def _plot(wto, eta_gt):
    """Histogram of the WTO spread + its sensitivity to the gas-turbine efficiency."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    from common import savefig
    fig, (axH, axS) = plt.subplots(1, 2, figsize=(13, 4.5))
    axH.hist(wto, bins=16, color="tab:blue", edgecolor="white")
    axH.axvline(wto.mean(), color="tab:red", ls="--", label=f"mean {wto.mean():.0f} kg")
    axH.set_xlabel("take-off weight [kg]"); axH.set_ylabel("count")
    axH.set_title(f"WTO distribution ({len(wto)} samples)"); axH.legend()

    axS.scatter(eta_gt, wto, s=18, color="tab:green", alpha=0.7)
    axS.set_xlabel("gas-turbine efficiency [-]"); axS.set_ylabel("WTO [kg]")
    axS.set_title("Sensitivity to GT efficiency")
    for ax in (axH, axS):
        ax.grid(alpha=0.3)
    fig.tight_layout()
    print("\nFigures:")
    savefig(fig, "12_uncertainty.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
