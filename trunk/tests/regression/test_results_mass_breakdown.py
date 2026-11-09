"""``results().empty_weight`` holds every mass that is neither payload nor fuel.

For each configuration, empty weight + payload + mission fuel + final reserve must give back
the converged take-off weight, and the tank and heat-exchanger masses must be reported in
their own fields.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "examples"))

import PhlyGreen as pg                                   # noqa: E402
from common import (traditional_config, hybrid_config, hydrogen_config,   # noqa: E402
                    fuelcell_battery_config, turbofan_config)


def _results(cfg):
    a = pg.build_aircraft()
    a.configure(cfg)
    return a, a.results()


def _check_closure(a, r):
    total = r.empty_weight + r.WPayload + r.Wf + r.final_reserve
    # WTO is the root abscissa of the closure (xtol 0.1 kg), so the residual is a few kg at most.
    assert total == pytest.approx(r.WTO, abs=5.0)
    assert r.zero_fuel_weight == pytest.approx(r.empty_weight + r.WPayload)


@pytest.mark.slow
@pytest.mark.parametrize("make_cfg", [traditional_config, turbofan_config],
                         ids=["traditional", "turbofan"])
def test_gas_turbine_empty_weight_closes(make_cfg):
    a, r = _results(make_cfg())
    _check_closure(a, r)
    assert r.tank_mass is None and r.hex_mass is None


@pytest.mark.slow
def test_hybrid_empty_weight_contains_the_battery_and_its_heat_exchanger():
    a, r = _results(hybrid_config(battery_class='II'))
    _check_closure(a, r)
    assert r.hex_mass == pytest.approx(a.weight.WHeat_Exchanger)
    assert r.hex_mass > 0.0                      # Class-II pack: cooling mass in the closure
    assert r.tank_mass is None


@pytest.mark.slow
@pytest.mark.parametrize("make_cfg", [lambda: hydrogen_config(tank=True),
                                      lambda: fuelcell_battery_config(tank=True)],
                         ids=["hydrogen", "fuelcell_battery"])
def test_fuel_cell_empty_weight_contains_tank_and_heat_exchangers(make_cfg):
    a, r = _results(make_cfg())
    _check_closure(a, r)
    assert r.tank_mass == pytest.approx(a.weight.WTank) and r.tank_mass > 0.0
    assert r.hex_mass == pytest.approx(a.weight.WHeat_Exchanger) and r.hex_mass > 0.0
    assert r.tms_mass == pytest.approx(r.hex_mass)
