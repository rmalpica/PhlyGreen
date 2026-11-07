"""Full-design tests of the thermal-management system (Class I and Class II) for the
fuel-cell configurations."""

import copy

import pytest

import PhlyGreen as pg
from PhlyGreen.config import TMSConfig
from PhlyGreen.Systems.Thermal import coolprop_available

from test_hydrogen import _hydrogen_config
from test_fuelcell_battery import _fcb_config

needs_coolprop = pytest.mark.skipif(not coolprop_available(), reason="CoolProp not installed")


def _with_tms(cfg, tms_class):
    cfg.tms = TMSConfig(tms_class=tms_class)
    return cfg


def _mass_sum(w):
    return (w.WStructure + w.WPT + getattr(w, "WBat", 0.0) + w.WH2_Fuel + w.WTank + w.WHeat_Exchanger
            + w.WPayload + w.WCrew + w.final_reserve)


def test_factory_wires_the_tms():
    a = pg.build_aircraft()
    assert a.tms is not None and a.tms.aircraft is a
    a.configure(_hydrogen_config(), design=False)
    assert a.tms.Class == 'I'                      # no TMSInput -> Class I


@pytest.fixture(scope="module")
def h2_class_i():
    a = pg.build_aircraft()
    a.configure(_with_tms(_hydrogen_config(), 'I'))
    return a


@pytest.fixture(scope="module")
def h2_class_ii():
    a = pg.build_aircraft()
    a.configure(_with_tms(_hydrogen_config(), 'II'))
    return a


@pytest.mark.slow
def test_class_i_sizes_on_the_larger_of_mission_and_takeoff_heat(h2_class_i):
    a = h2_class_i
    m = a.mission
    Q = max(m.Max_FC_Thermal_Pwr, m.TO_FC_Thermal_Pwr)
    assert m.TO_FC_Thermal_Pwr > 0
    assert a.weight.WHeat_Exchanger == pytest.approx(Q / 5000.0)
    assert a.weight.tms_result is None
    assert a.aerodynamics.extra_Cd == 0.0 and a.fuelcell.P_aux_tms == 0.0
    # the thermal profile has the take-off point and one peak per flown segment
    names = [p['name'] for p in m.thermal_profile]
    assert names[0] == 'Takeoff' and any(n.startswith('Diversion/') for n in names)


@needs_coolprop
@pytest.mark.slow
def test_class_ii_hydrogen_design_closes(h2_class_ii):
    a = h2_class_ii
    w = a.weight
    assert _mass_sum(w) == pytest.approx(w.WTO, rel=1e-3)
    r = w.tms_result
    assert r is not None and w.WHeat_Exchanger == pytest.approx(r.total_mass)
    assert r.pump_power > 0 and a.fuelcell.P_aux_tms == pytest.approx(r.pump_power)
    assert r.heat_shortfall == pytest.approx(0.0, abs=1.0)
    res = a.results()
    assert res.tms_class == 'II' and res.tms_mass == pytest.approx(w.WHeat_Exchanger)
    assert res.tms_design_point == r.design_point['name']


@needs_coolprop
@pytest.mark.slow
def test_class_ii_geometry_rejects_the_heat_at_every_mission_point(h2_class_ii):
    a = h2_class_ii
    tms, r = a.tms, a.weight.tms_result
    for p in a.mission.thermal_profile:
        q_rej, q_req = tms.RateAtPoint(r, p)
        assert q_rej >= (1 - tms.FEASIBILITY_TOLERANCE) * q_req


@needs_coolprop
@pytest.mark.slow
def test_ram_drag_feeds_back_as_a_drag_increment():
    cfg = _hydrogen_config()
    cfg.tms = TMSConfig(tms_class='II', ram_recovery=0.8)
    a = pg.build_aircraft()
    a.configure(cfg)
    r = a.weight.tms_result
    assert r.ram_drag > 0
    assert a.aerodynamics.extra_Cd == pytest.approx(
        a.tms.RamDragCoefficient(r, a.weight.WTO * 9.81 / a.DesignWTOoS), rel=1e-3)


@needs_coolprop
@pytest.mark.slow
def test_fuelcell_battery_class_ii_at_phi_zero_matches_hydrogen(h2_class_ii):
    """Same fuel-cell + TMS closure for both configurations: a battery-free fuel-cell +
    battery design is the hydrogen design, TMS included."""
    a = pg.build_aircraft()
    a.configure(_with_tms(_fcb_config(cruise_phi=0.0), 'II'))
    assert a.weight.WBat == pytest.approx(0.0)
    assert a.weight.WTO == pytest.approx(h2_class_ii.weight.WTO, rel=1e-9)
    assert a.weight.WHeat_Exchanger == pytest.approx(h2_class_ii.weight.WHeat_Exchanger, rel=1e-9)


@needs_coolprop
@pytest.mark.slow
def test_class_ii_hardware_is_checked_along_the_continuous_mission(h2_class_ii):
    """The converged design is checked at every profile point and every accepted
    integration point: heat, pressure budgets and choking are limits, coolant freezing a
    risk; the duct drag is compared over the mission as a drag work."""
    a = h2_class_ii
    m, tms, r = a.mission, a.tms, a.weight.tms_result
    assert len(m.thermal_history) > 10 * len(m.thermal_profile)
    assert len(r.checks) == len(m.thermal_profile) + len(m.thermal_history)
    # the continuous mission adds no candidate on the reference design
    assert [c['point'] for c in r.candidates] == [
        p['name'] for p in m.thermal_profile if p['Q_fc'] >= 0.5 * max(q['Q_fc'] for q in m.thermal_profile)]
    for c in r.checks:
        assert c['shortfall'] <= tms.FEASIBILITY_TOLERANCE
        assert c['T_wall_min'] > c['T_freeze']
        assert not c['choked']
    assert r.violations() == [] and r.risks() == []
    # the constant drag increment charges at least the duct drag work of the momentum balance
    assert r.ram_drag_work_accounted >= r.ram_drag_work >= 0.0


@needs_coolprop
@pytest.mark.slow
def test_offdesign_check_reports_tms_limits(h2_class_ii):
    """Example 30 reports the limits of CheckAtPoint as off-design violations."""
    import importlib.util, os
    path = os.path.join(os.path.dirname(__file__), '..', '..', 'examples', '30_off_design_mission.py')
    spec = importlib.util.spec_from_file_location('ex30_tms', path)
    ex30 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ex30)
    a = h2_class_ii
    assert ex30._tms_violation(a, None) == ([], [])
    worse = copy.deepcopy(a)
    worse.tms.ram_recovery = 0.02         # an intake far worse than the one sized for
    violations, risks = ex30._tms_violation(worse, None)
    assert any('ram-air core pressure drop' in v for v in violations)
    assert not any('drag' in v for v in violations)
