"""Component-graph model of the powertrain power balance.

The steady-state power flow through a propulsion architecture is a set of linear
relations between component powers (all normalized by the propulsive power ``Pp``):

* a **converter** turns one power into another with an efficiency: ``out = eta * in``;
* a **combiner** sums several inputs through one efficiency: ``out = eta * sum(in)``
  (e.g. a gearbox fed by both a turbine and an electric motor);
* a **split** allocates demand between two sources via the hybridization ratio ``phi``:
  ``phi * source_a + (phi - 1) * source_b = 0``;
* a **sink** normalizes the propulsive output: ``Pp = 1``.

:class:`PowertrainGraph` collects these as equations and solves the resulting linear
system. Because the system is square and non-singular, the solution is unique — so a
graph assembled from the same relations as the legacy hand-coded matrices yields
identical power ratios (verified in tests), while *new* architectures (e.g. fuel cell +
battery) are expressed simply by composing the same primitives. This replaces the
hard-coded 4x4 / 7x7 / 8x8 matrices in ``Powertrain.Traditional``/``Hybrid``.
"""

import numpy as np


class PowertrainGraph:
    """A square linear system of normalized component-power relations.

    Args:
        variables: ordered list of power-variable names. The order defines the order of
            the solution vector returned by :meth:`solve`.
    """

    def __init__(self, variables):
        self.variables = list(variables)
        self._index = {v: i for i, v in enumerate(self.variables)}
        self._rows = []  # list of (coeffs: dict[str, float], rhs: float)

    # --- primitives ---------------------------------------------------------

    def add_equation(self, coeffs, rhs=0.0):
        """Add a raw linear equation ``sum(coeffs[v] * v) = rhs``."""
        unknown = set(coeffs) - set(self._index)
        if unknown:
            raise KeyError(f"equation references unknown variables: {sorted(unknown)}")
        self._rows.append((coeffs, rhs))
        return self

    def converter(self, in_var, out_var, eta):
        """``out = eta * in``."""
        return self.add_equation({out_var: 1.0, in_var: -eta})

    def combiner(self, out_var, in_vars, eta):
        """``out = eta * sum(in_vars)`` (e.g. a gearbox or a power-management bus)."""
        coeffs = {out_var: 1.0}
        for v in in_vars:
            coeffs[v] = coeffs.get(v, 0.0) - eta
        return self.add_equation(coeffs)

    def split(self, source_a, source_b, phi):
        """Hybridization split ``phi * source_a + (phi - 1) * source_b = 0``."""
        return self.add_equation({source_a: phi, source_b: phi - 1.0})

    def sink(self, var, value=1.0):
        """Normalization ``var = value`` (propulsive output)."""
        return self.add_equation({var: 1.0}, value)

    # --- solve --------------------------------------------------------------

    def solve(self):
        """Solve the system and return the solution vector in ``variables`` order."""
        n = len(self.variables)
        if len(self._rows) != n:
            raise ValueError(
                f"powertrain graph is not square: {len(self._rows)} equations for "
                f"{n} variables ({self.variables})")
        A = np.zeros((n, n))
        b = np.zeros(n)
        for i, (coeffs, rhs) in enumerate(self._rows):
            for var, c in coeffs.items():
                A[i, self._index[var]] += c
            b[i] = rhs
        return np.linalg.solve(A, b)

    def solution(self):
        """Solve and return a ``{variable: power_ratio}`` dict."""
        x = self.solve()
        return {v: x[i] for i, v in enumerate(self.variables)}


# ---------------------------------------------------------------------------
# Architecture builders — each reproduces the corresponding legacy power system.
# The variable order matches the legacy output vector so downstream index access
# (PRatio[0]=fuel, PRatio[1]=gas-turbine shaft, PRatio[5]=battery) is preserved.
# ---------------------------------------------------------------------------

def traditional_graph(eta_gt, eta_gb, eta_pp):
    """Thermal-only chain: fuel -> gas turbine -> gearbox -> propeller."""
    g = PowertrainGraph(["Pf", "Pgt", "Pgb", "Pp"])
    g.converter("Pf", "Pgt", eta_gt)
    g.converter("Pgt", "Pgb", eta_gb)
    g.converter("Pgb", "Pp", eta_pp)
    g.sink("Pp", 1.0)
    return g


def parallel_hybrid_graph(eta_gt, eta_gb, eta_pm, eta_em, eta_pp, phi):
    """Parallel hybrid: turbine and battery-fed motor both drive the propeller gearbox."""
    g = PowertrainGraph(["Pf", "Pgt", "Pgb", "Ps1", "Pe1", "Pbat", "Pp1"])
    g.converter("Pf", "Pgt", eta_gt)            # gas turbine
    g.combiner("Ps1", ["Pgt", "Pgb"], eta_gb)   # gearbox sums thermal + electric shafts
    g.converter("Pbat", "Pe1", eta_pm)          # power management / distribution
    g.converter("Pe1", "Pgb", eta_em)           # electric motor
    g.converter("Ps1", "Pp1", eta_pp)           # propeller
    g.split("Pf", "Pbat", phi)                  # hybridization split
    g.sink("Pp1", 1.0)
    return g


def serial_hybrid_graph(eta_gt, eta_em1, eta_pm, eta_em2, eta_gb, eta_pp, phi):
    """Serial hybrid: turbine -> generator -> (bus + battery) -> motor -> gearbox -> prop."""
    g = PowertrainGraph(["Pf", "Pgt", "Pgb", "Ps1", "Pe1", "Pbat", "Pgen", "Pp1"])
    g.converter("Pf", "Pgt", eta_gt)            # gas turbine
    g.converter("Pgt", "Ps1", eta_em1)          # generator
    g.combiner("Pe1", ["Ps1", "Pbat"], eta_pm)  # power bus sums generator + battery
    g.converter("Pe1", "Pgb", eta_em2)          # electric motor
    g.converter("Pgb", "Pgen", eta_gb)          # gearbox
    g.converter("Pgen", "Pp1", eta_pp)          # propeller
    g.split("Pf", "Pbat", phi)                  # hybridization split
    g.sink("Pp1", 1.0)
    return g


def fuelcell_battery_graph(eta_fc, eta_pm, eta_em, eta_gb, eta_pp, phi):
    """Fuel-cell + battery hybrid (no gas turbine) — example of an arbitrary topology.

    Hydrogen feeds a fuel cell; the fuel cell and battery feed a common electrical bus,
    then a motor, gearbox and propeller. ``phi`` splits demand between hydrogen and
    battery. Demonstrates that a new architecture needs only a new composition of the
    same primitives — no new matrix algebra.
    """
    g = PowertrainGraph(["PfH2", "Pfc", "Pbat", "Pe1", "Pem", "Pgb", "Pp1"])
    g.converter("PfH2", "Pfc", eta_fc)          # fuel cell: H2 power -> electrical
    g.combiner("Pe1", ["Pfc", "Pbat"], eta_pm)  # power bus sums fuel cell + battery
    g.converter("Pe1", "Pem", eta_em)           # electric motor
    g.converter("Pem", "Pgb", eta_gb)           # gearbox
    g.converter("Pgb", "Pp1", eta_pp)           # propeller
    g.split("PfH2", "Pbat", phi)                # hydrogen/battery split
    g.sink("Pp1", 1.0)
    return g
