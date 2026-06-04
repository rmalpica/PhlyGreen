"""Example 05 — The powertrain graph and pluggable efficiency models.

The powertrain solves a power balance over a graph of components. You can: read the power
ratios for the built-in architectures, make a component's efficiency depend on the
operating point with a Class-II model, and assemble an entirely new architecture (here a
fuel cell + battery) from the same primitives.

Run it:
    cd trunk && python examples/05_powertrain_graph_and_efficiency_models.py
"""

import PhlyGreen as pg
from PhlyGreen.Systems.Powertrain.graph import parallel_hybrid_graph, fuelcell_battery_graph
from PhlyGreen.Systems.Powertrain.efficiency import MotorEfficiencyModel, OperatingPoint
from common import hybrid_config, savefig


def builtin_architecture():
    # Assemble a parallel-hybrid power balance directly and solve it. The result is the
    # set of component powers normalized by the propulsive power Pp.
    g = parallel_hybrid_graph(eta_gt=0.3, eta_gb=0.96, eta_pm=0.99,
                              eta_em=0.98, eta_pp=0.85, phi=0.3)
    print("Parallel-hybrid power ratios (per unit propulsive power):")
    for name, value in g.solution().items():
        print(f"  {name:5s}: {value:6.3f}")


def operating_point_dependent_efficiency():
    # Attach a Class-II d-q electric-motor model; its efficiency now varies with power, so
    # the solved battery power ratio changes between two load levels.
    aircraft = pg.build_aircraft()
    aircraft.configure(hybrid_config(), design=False)
    pt = aircraft.powertrain
    pt.em_model = MotorEfficiencyModel(design_kw=2000, design_v=800, design_rpm=1200)

    low = pt.Hybrid(0.3, 8000, 120, 3.0e5)[5]   # battery ratio at light load
    high = pt.Hybrid(0.3, 8000, 120, 3.0e6)[5]   # battery ratio at heavy load
    print(f"\nMotor efficiency depends on load -> battery power ratio: "
          f"{low:.3f} (light) vs {high:.3f} (heavy)")
    print(f"Motor efficiency at 1 MW: "
          f"{pt.em_model.eta(OperatingPoint(power=1e6, rpm=1200)):.3f}")


def new_architecture_fuel_cell_battery():
    # A gas-turbine-free hybrid: a fuel cell and a battery share an electrical bus. Built
    # from the same primitives — no new matrix algebra.
    g = fuelcell_battery_graph(eta_fc=0.55, eta_pm=0.99, eta_em=0.98,
                               eta_gb=0.96, eta_pp=0.85, phi=0.3)
    sol = g.solution()
    print("\nFuel-cell + battery architecture:")
    print(f"  hydrogen power : {sol['PfH2']:.3f}")
    print(f"  battery power  : {sol['Pbat']:.3f}")


def component_performance_maps():
    """Plot the Class-II GT / electric-motor / propeller efficiency maps.

    Each is a real Class-II model: the gas turbine and propeller are response surfaces
    trained offline; the electric motor is a d-q physics model. Requires matplotlib (and
    pandas for the propeller surrogate); skipped gracefully if unavailable.
    """
    try:
        import os
        import numpy as np
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        print("\n(matplotlib not available — skipping performance-map plots)")
        return

    from PhlyGreen.Systems.Powertrain.gas_turbine_surrogate import GasTurbineResponseSurface
    from PhlyGreen.Systems.Powertrain.EM import ElectricMotor

    fig, axes = plt.subplots(1, 3, figsize=(16, 4.5))

    # --- Gas turbine: efficiency vs required power & altitude (design 2750 hp) ---
    gt = GasTurbineResponseSurface()
    powers = np.linspace(400, 2750, 40)        # required shaft power [hp]
    alts_ft = np.linspace(0, 25000, 40)
    Zgt = np.array([[gt.predict(2750, a, 0.4, p)[0] for p in powers] for a in alts_ft])
    c0 = axes[0].contourf(powers, alts_ft, Zgt, levels=20, cmap="viridis")
    fig.colorbar(c0, ax=axes[0], label="efficiency")
    axes[0].set_xlabel("required power [hp]"); axes[0].set_ylabel("altitude [ft]")
    axes[0].set_title("Gas turbine (response surface)")

    # --- Electric motor: efficiency vs rpm & torque (d-q model) ---
    motor = ElectricMotor(design_kw=2000, design_v=800, design_rpm=11000)
    rpms = np.linspace(1000, 11000, 40)
    torques = np.linspace(50, 1700, 40)
    Zem = np.array([[motor.solve_efficiency(r, t) for r in rpms] for t in torques])
    c1 = axes[1].contourf(rpms, torques, Zem, levels=20, cmap="viridis")
    fig.colorbar(c1, ax=axes[1], label="efficiency")
    axes[1].set_xlabel("rpm"); axes[1].set_ylabel("torque [N·m]")
    axes[1].set_title("Electric motor (d-q model)")

    # --- Propeller: efficiency vs airspeed & power (RBF surrogate, needs pandas) ---
    try:
        from PhlyGreen.Systems.Powertrain import propeller_surrogate as _prbf
        csv = os.path.join(os.path.dirname(_prbf.__file__), "data", "propeller_data_rbf.csv")
        prop = _prbf.PropellerSurrogate(csv)
        speeds = np.linspace(40, 170, 35)
        powers_kw = np.linspace(200, 2200, 35)
        rpm = 1200.0
        Zpp = np.empty((len(powers_kw), len(speeds)))
        for i, pk in enumerate(powers_kw):
            for j, v in enumerate(speeds):
                pitch = prop.solve_pitch(pk, 3000.0, v, rpm)
                Zpp[i, j] = prop.get_efficiency(pk, 3000.0, v, pitch, rpm)
        c2 = axes[2].contourf(speeds, powers_kw, Zpp, levels=20, cmap="viridis")
        fig.colorbar(c2, ax=axes[2], label="efficiency")
        axes[2].set_xlabel("airspeed [m/s]"); axes[2].set_ylabel("power [kW]")
        axes[2].set_title("Propeller (RBF surrogate)")
    except Exception as exc:
        axes[2].text(0.5, 0.5, f"propeller surrogate\nunavailable\n({type(exc).__name__})",
                     ha="center", va="center")
        axes[2].set_title("Propeller")

    fig.tight_layout()
    # Use the shared helper so the figure always lands in trunk/examples/_output, regardless
    # of the current working directory.
    print()
    savefig(fig, "component_performance_maps.png")


if __name__ == "__main__":
    builtin_architecture()
    operating_point_dependent_efficiency()
    new_architecture_fuel_cell_battery()
    component_performance_maps()
