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
from common import hybrid_config


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


if __name__ == "__main__":
    builtin_architecture()
    operating_point_dependent_efficiency()
    new_architecture_fuel_cell_battery()
