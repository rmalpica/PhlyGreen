"""Unit tests for the powertrain component-graph engine.

Teaches how an architecture is composed from primitives, and shows that a brand-new
topology (fuel cell + battery) needs only a new composition — no new matrix algebra.
"""

import numpy as np
import pytest

from PhlyGreen.Systems.Powertrain.graph import (
    PowertrainGraph, traditional_graph, parallel_hybrid_graph,
    serial_hybrid_graph, fuelcell_battery_graph,
)


# --- primitives -------------------------------------------------------------

def test_converter_chain_lossless():
    g = traditional_graph(eta_gt=1.0, eta_gb=1.0, eta_pp=1.0)
    sol = g.solution()
    assert all(v == pytest.approx(1.0) for v in sol.values())


def test_traditional_inverts_efficiency_product():
    g = traditional_graph(eta_gt=0.3, eta_gb=0.96, eta_pp=0.85)
    sol = g.solution()
    # Fuel power must cover all chain losses: Pf = 1 / (eta_gt*eta_gb*eta_pp).
    assert sol["Pf"] == pytest.approx(1.0 / (0.3 * 0.96 * 0.85))
    assert sol["Pp"] == pytest.approx(1.0)


def test_non_square_system_raises():
    g = PowertrainGraph(["a", "b"])
    g.sink("a", 1.0)  # only one equation for two variables
    with pytest.raises(ValueError):
        g.solve()


def test_unknown_variable_raises():
    g = PowertrainGraph(["a"])
    with pytest.raises(KeyError):
        g.converter("ghost", "a", 0.9)


# --- split semantics --------------------------------------------------------

@pytest.mark.parametrize("phi", [0.0, 0.1, 0.3, 0.5])
def test_split_allocates_between_sources(phi):
    g = parallel_hybrid_graph(eta_gt=0.3, eta_gb=0.96, eta_pm=0.99,
                              eta_em=0.98, eta_pp=0.85, phi=phi)
    sol = g.solution()
    # split equation: Pbat = phi/(1-phi) * Pf
    assert sol["Pbat"] == pytest.approx(phi / (1 - phi) * sol["Pf"])
    assert sol["Pp1"] == pytest.approx(1.0)
    if phi == 0.0:
        assert sol["Pbat"] == pytest.approx(0.0)


# --- new topology: fuel cell + battery (arbitrary hybridization) ------------

def test_fuelcell_battery_topology_solves_and_conserves():
    g = fuelcell_battery_graph(eta_fc=0.55, eta_pm=0.99, eta_em=0.98,
                               eta_gb=0.96, eta_pp=0.85, phi=0.0)
    sol = g.solution()
    # phi=0 -> no battery, all power from hydrogen through the electric chain.
    assert sol["Pbat"] == pytest.approx(0.0)
    assert sol["PfH2"] == pytest.approx(1.0 / (0.55 * 0.99 * 0.98 * 0.96 * 0.85))
    assert sol["Pp1"] == pytest.approx(1.0)


def test_fuelcell_battery_uses_battery_when_phi_positive():
    no_bat = fuelcell_battery_graph(0.55, 0.99, 0.98, 0.96, 0.85, phi=0.0).solution()
    with_bat = fuelcell_battery_graph(0.55, 0.99, 0.98, 0.96, 0.85, phi=0.3).solution()
    assert with_bat["Pbat"] > 0
    # Drawing on the battery reduces the hydrogen demand.
    assert with_bat["PfH2"] < no_bat["PfH2"]


def test_serial_graph_is_square_and_solvable():
    sol = serial_hybrid_graph(0.3, 0.96, 0.99, 0.98, 0.96, 0.85, phi=0.2).solution()
    assert sol["Pp1"] == pytest.approx(1.0)
    assert set(sol) == {"Pf", "Pgt", "Pgb", "Ps1", "Pe1", "Pbat", "Pgen", "Pp1"}
