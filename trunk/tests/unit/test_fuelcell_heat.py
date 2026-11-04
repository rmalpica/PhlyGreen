"""Heat rejected to the fuel-cell coolant: the phase of the product water."""

import pytest

from PhlyGreen.Systems.FuelCell.FuelCell import FuelCell


def _fc(T_op=353.15, P=1.5e5, stoich=2.0, rh=0.0):
    fc = FuelCell(None)
    fc.T_op, fc.Target_Press, fc.stoich, fc.inlet_rh = T_op, P, stoich, rh
    return fc


def test_water_saturation_pressure_matches_tabulated_values():
    assert FuelCell.water_saturation_pressure(373.15) == pytest.approx(101325.0, rel=2e-3)
    assert FuelCell.water_saturation_pressure(353.15) == pytest.approx(47390.0, rel=5e-3)
    assert FuelCell.water_saturation_pressure(298.15) == pytest.approx(3169.0, rel=5e-3)


def test_dry_air_at_80C_and_1p5_bar_carries_all_product_water_as_vapour():
    assert _fc().product_water_vapour_fraction() == 1.0


def test_saturated_inlet_air_leaves_the_product_water_liquid():
    assert _fc(rh=1.0).product_water_vapour_fraction() == 0.0


def test_vapour_fraction_falls_with_inlet_humidity_and_pressure():
    rh = [_fc(rh=r).product_water_vapour_fraction() for r in (0.6, 0.7, 0.8, 0.9)]
    assert rh == sorted(rh, reverse=True)
    assert _fc(P=3.0e5, rh=0.5).product_water_vapour_fraction() < 1.0


def test_above_the_boiling_point_all_product_water_is_vapour():
    assert _fc(T_op=443.15, P=1.5e5, rh=1.0).product_water_vapour_fraction() == 1.0


def test_thermoneutral_voltages():
    F = FuelCell.FARADAY_CONST
    assert FuelCell.DELTA_H_REACT / (2 * F) == pytest.approx(1.482, abs=1e-3)
    assert FuelCell.DELTA_H_REACT_LHV / (2 * F) == pytest.approx(1.253, abs=1e-3)
