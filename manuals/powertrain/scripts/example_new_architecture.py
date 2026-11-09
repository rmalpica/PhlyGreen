"""Worked example: a new powertrain architecture composed from the graph primitives.

Architecture (partial turbo-electric): one gas turbine drives a gearbox and a main
propeller, and also a generator. The generator feeds a power-management bus and an
electric motor that drives a second propulsor (an electric fan). The share of the total
propulsive power produced by the electric propulsor is ``xi``.

Nothing outside this file is changed: the architecture is a new composition of the four
primitives of ``PhlyGreen.Systems.Powertrain.graph``.

Run it (from trunk/, phlygreen environment):
    python ../manuals/powertrain/scripts/example_new_architecture.py
"""

from PhlyGreen.Systems.Powertrain.graph import PowertrainGraph


def partial_turboelectric_graph(eta_gt, eta_gb, eta_pp, eta_gen, eta_pm, eta_em, eta_fan, xi):
    """Power balance of the partial turbo-electric architecture (all powers / Pp)."""
    g = PowertrainGraph(["Pf", "Pgt", "Pa", "Pb", "Ps1", "Pp1",
                         "Pgen", "Pe1", "Pem", "Pp2", "Pp"])
    g.converter("Pf", "Pgt", eta_gt)           # gas turbine: fuel -> shaft
    g.combiner("Pgt", ["Pa", "Pb"], 1.0)       # lossless shaft junction: Pgt = Pa + Pb
    g.converter("Pa", "Ps1", eta_gb)           # gearbox of the main propeller
    g.converter("Ps1", "Pp1", eta_pp)          # main propeller
    g.converter("Pb", "Pgen", eta_gen)         # generator
    g.converter("Pgen", "Pe1", eta_pm)         # power management and distribution
    g.converter("Pe1", "Pem", eta_em)          # electric motor
    g.converter("Pem", "Pp2", eta_fan)         # electric fan (second propulsor)
    g.combiner("Pp", ["Pp1", "Pp2"], 1.0)      # total propulsive power: Pp = Pp1 + Pp2
    g.split("Pp1", "Pp2", xi)                  # xi = Pp2 / (Pp1 + Pp2)
    g.sink("Pp", 1.0)                          # normalization
    return g


def fuel_ratio_closed_form(eta_gt, eta_gb, eta_pp, eta_gen, eta_pm, eta_em, eta_fan, xi):
    """Pf/Pp written out by hand, to check the graph solution."""
    mechanical_branch = (1.0 - xi) / (eta_gb * eta_pp)
    electric_branch = xi / (eta_gen * eta_pm * eta_em * eta_fan)
    return (mechanical_branch + electric_branch) / eta_gt


if __name__ == "__main__":
    # Efficiencies of trunk/examples/common.py:_energy() (gas turbine, gearbox, propeller,
    # generator = eta_electric_motor_1, PMAD, motor = eta_electric_motor_2). The fan
    # efficiency is set equal to the propeller one for this illustration.
    eta = dict(eta_gt=0.22, eta_gb=0.96, eta_pp=0.9, eta_gen=0.96, eta_pm=0.99,
               eta_em=0.96, eta_fan=0.9)
    for xi in (0.0, 0.2, 0.5):
        sol = partial_turboelectric_graph(xi=xi, **eta).solution()
        check = fuel_ratio_closed_form(xi=xi, **eta)
        print(f"xi = {xi:.1f}:  Pf/Pp = {sol['Pf']:.4f} (closed form {check:.4f}),  "
              f"Pgt/Pp = {sol['Pgt']:.4f},  generator input Pb/Pp = {sol['Pb'] + 0.0:.4f}")
