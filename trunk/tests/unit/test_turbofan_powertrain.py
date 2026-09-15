"""Unit tests for the turbofan powertrain.

Three things are worth pinning, because each is a place the design could go quietly wrong:

* the turbofan graph is `traditional_graph` with unit gearbox and fan nodes, so `PRatio[0]`
  really is `1/eta_o` and the existing fuel closure needs no special case;
* `eta_o` and TSFC are the same statement -- `TSFC = V/(eta_o*LHV)` -- which is the identity
  the whole "keep the efficiency-chain powertrain" decision rests on;
* the thrust lapse depends on Mach as well as altitude, which is exactly what the turboshaft
  power lapse cannot express.
"""

import numpy as np
import pytest

from PhlyGreen.Systems.Powertrain.graph import traditional_graph
from PhlyGreen.Systems.Powertrain.efficiency import OperatingPoint, TurbofanEfficiencyModel

LHV = 43.0e6


class _FakeMap:
    """Stands in for the fitted surface so these tests need no pyCycle artifact."""
    def __init__(self, eta=0.35, lapse=0.25):
        self._eta, self._lapse = eta, lapse
        self.tag = "fake"

    def thrust_lapse(self, altitude_ft, mach):
        return self._lapse

    def predict(self, design_thrust_N, altitude_ft, mach, required_thrust_N):
        avail = design_thrust_N * self._lapse
        limited = required_thrust_N > avail
        v_over_eta = None
        return self._eta, self._eta and 0.0, avail, limited


def test_turbofan_graph_is_the_traditional_chain_with_unit_gearbox_and_fan():
    """A turbofan carries its whole chain in one node, so PRatio[0] must be 1/eta_o."""
    eta_o = 0.34
    pr = traditional_graph(eta_gt=eta_o, eta_gb=1.0, eta_pp=1.0).solve()
    assert pr[0] == pytest.approx(1.0 / eta_o)
    assert pr[1] == pytest.approx(1.0)   # nothing is removed downstream of the eta_o node
    assert pr[3] == pytest.approx(1.0)   # propulsive power is the normalisation


def test_eta_o_and_tsfc_are_the_same_statement():
    """eta_o = F*V/(mdot_f*LHV) and TSFC = mdot_f/F imply TSFC = V/(eta_o*LHV) exactly."""
    for v, eta_o in [(231.0, 0.34), (150.0, 0.28), (77.0, 0.18)]:
        tsfc = v / (eta_o * LHV)
        # ...and back again, which is how the mission recovers fuel flow from the graph.
        assert v / (tsfc * LHV) == pytest.approx(eta_o)
        mdot_over_thrust = tsfc
        assert (v / (mdot_over_thrust * LHV)) == pytest.approx(eta_o)


def test_fuel_flow_from_the_graph_matches_the_tsfc_closure():
    """The point of the single-node design: the existing dE/dt = PP*PRatio[0] is a TSFC law."""
    eta_o, v, thrust = 0.34, 231.0, 26_000.0
    pp = thrust * v                                  # propulsive power [W]
    pr0 = traditional_graph(eta_gt=eta_o, eta_gb=1.0, eta_pp=1.0).solve()[0]
    mdot_from_graph = pp * pr0 / LHV                 # what Mission integrates
    mdot_from_tsfc = (v / (eta_o * LHV)) * thrust    # TSFC * F
    assert mdot_from_graph == pytest.approx(mdot_from_tsfc)


def test_efficiency_model_converts_propulsive_power_to_thrust():
    m = TurbofanEfficiencyModel(design_thrust=240e3, surrogate=_FakeMap(eta=0.33))
    op = OperatingPoint(altitude=10668.0, velocity=231.0, power=26_000.0 * 231.0)
    assert m.eta(op) == pytest.approx(0.33)


def test_efficiency_model_rejects_a_standstill():
    """F = P/V is singular at rest, and so is overall efficiency itself -- say so loudly."""
    m = TurbofanEfficiencyModel(design_thrust=240e3, surrogate=_FakeMap())
    with pytest.raises(ValueError, match="positive velocity"):
        m.eta(OperatingPoint(altitude=0.0, velocity=0.0, power=1e6))


def test_efficiency_model_requires_a_nominal_thrust():
    with pytest.raises(ValueError, match="positive nominal"):
        TurbofanEfficiencyModel(design_thrust=0.0, surrogate=_FakeMap())
