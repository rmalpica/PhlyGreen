"""Unit tests for the Class-II thermal-management model (Systems/Thermal: hex, ram_air, TMS).

These pin the corrections made when the model was ported from the source thesis code:
consistent sizing/rating, the U area reference, the hydrogen enthalpy sink, robustness at
zero heat, monotone mass in the heat load, and the minimum-mass family choice.
"""

import math
from types import SimpleNamespace

import pytest

from PhlyGreen.Systems.Thermal import (
    FlowArrangement, effectiveness, ntu_required, thermal_solve, ram_air_drag,
    ThermalManagementSystem, coolprop_available,
)
from PhlyGreen.Systems.Thermal.hex import (
    FluidStream, DesignSpec, FinnedTubeBankSizer, PlainTubeBankSizer, PlateFinSizer,
    HeatExchangerSelector, rate_design, crossflow_one_mixed,
)

needs_coolprop = pytest.mark.skipif(not coolprop_available(), reason="CoolProp not installed")

ARRANGEMENTS = list(FlowArrangement)


# ---------------------------------------------------------------------------------------
# epsilon-NTU
# ---------------------------------------------------------------------------------------

@pytest.mark.parametrize("arr", ARRANGEMENTS)
def test_effectiveness_tends_to_single_stream_limit_when_cr_is_zero(arr):
    for ntu in (0.3, 1.0, 3.0):
        assert effectiveness(ntu, 0.0, arr) == pytest.approx(1 - math.exp(-ntu))


def test_effectiveness_textbook_values():
    # Incropera Table 11.3 closed forms, evaluated by hand at NTU = 1, Cr = 0.5
    ntu, cr = 1.0, 0.5
    e = math.exp(-ntu * (1 - cr))
    assert effectiveness(ntu, cr, FlowArrangement.COUNTERFLOW) == pytest.approx((1 - e) / (1 - cr * e))
    assert effectiveness(ntu, cr, FlowArrangement.PARALLEL) == pytest.approx(
        (1 - math.exp(-ntu * 1.5)) / 1.5)
    assert effectiveness(ntu, cr, FlowArrangement.CROSSFLOW_CMAX_MIXED) == pytest.approx(
        2.0 * (1 - math.exp(-0.5 * (1 - math.exp(-1.0)))))
    assert effectiveness(ntu, cr, FlowArrangement.CROSSFLOW_CMIN_MIXED) == pytest.approx(
        1 - math.exp(-2.0 * (1 - math.exp(-0.5))))
    assert effectiveness(2.0, 1.0, FlowArrangement.COUNTERFLOW) == pytest.approx(2.0 / 3.0)


def test_arrangements_rank_as_expected():
    ntu, cr = 2.0, 0.6
    cf = effectiveness(ntu, cr, FlowArrangement.COUNTERFLOW)
    xu = effectiveness(ntu, cr, FlowArrangement.CROSSFLOW_UNMIXED)
    pf = effectiveness(ntu, cr, FlowArrangement.PARALLEL)
    assert cf > xu > pf


@pytest.mark.parametrize("arr", ARRANGEMENTS)
def test_ntu_required_inverts_effectiveness(arr):
    for cr in (0.0, 0.3, 0.8):
        ntu = 1.7
        eps = effectiveness(ntu, cr, arr)
        assert ntu_required(eps, cr, arr) == pytest.approx(ntu, rel=1e-6)


def test_ntu_required_rejects_unreachable_effectiveness():
    with pytest.raises(ValueError):
        ntu_required(0.99, 1.0, FlowArrangement.PARALLEL)       # parallel flow caps at 0.5


def test_crossflow_label_depends_on_which_stream_is_mixed():
    gas = FluidStream("air", 1.0, 1000.0, 1.8e-5, 0.026, 1.2, 300.0)      # C = 1000
    liq = FluidStream("liq", 1.0, 4000.0, 1e-3, 0.6, 1000.0, 350.0)       # C = 4000
    assert crossflow_one_mixed(mixed=gas, other=liq) == FlowArrangement.CROSSFLOW_CMIN_MIXED
    assert crossflow_one_mixed(mixed=liq, other=gas) == FlowArrangement.CROSSFLOW_CMAX_MIXED


# ---------------------------------------------------------------------------------------
# Exchanger families
# ---------------------------------------------------------------------------------------

def _coolant(mdot=10.0, T=353.15):
    return FluidStream("coolant", mdot, 3700.0, 6e-4, 0.5, 1030.0, T)


def _air(mdot=10.0, T=300.0):
    return FluidStream("air", mdot, 1007.0, 1.85e-5, 0.0263, 1.16, T)


@pytest.mark.parametrize("sizer_cls", [PlainTubeBankSizer, FinnedTubeBankSizer])
def test_tube_bank_rating_at_design_point_returns_design_duty(sizer_cls):
    """Sizing and rating use the same layout and correlations: no hidden mismatch."""
    hot, cold = _coolant(), _air()
    spec = DesignSpec(hot=hot, cold=cold, q_target=200e3)
    d = sizer_cls(spec).best_candidate()
    assert d is not None and d.feasible
    assert rate_design(d, hot, cold) == pytest.approx(200e3, rel=1e-6)


def test_plate_fin_rating_at_design_point_returns_design_duty():
    hot = _coolant(mdot=2.0)
    cold = FluidStream("h2", 0.02, 14000.0, 7e-6, 0.12, 0.25, 22.0)
    spec = DesignSpec(hot=hot, cold=cold, q_target=50e3)
    d = PlateFinSizer(spec).best_candidate()
    assert d is not None
    assert rate_design(d, hot, cold) == pytest.approx(50e3, rel=1e-6)


def test_finned_bank_U_is_referred_to_the_gas_side_area():
    """1/U = A_o/(A_i h_i) + A_o R_wall + 1/(eta_o h_o): the inner and wall resistances are
    scaled by the outer (finned) area, not by d_o/d_i as in the source."""
    hot, cold = _coolant(), _air()
    sizer = FinnedTubeBankSizer(DesignSpec(hot=hot, cold=cold, q_target=200e3))
    d = sizer.best_candidate()
    g = d.geometry
    r = sizer.compute_U(g, hot, cold)
    h_in, _, _ = sizer._tube_side(g, hot)
    A_fin, A_bare = sizer._fin_areas(g)
    A_o, A_i = A_fin + A_bare, math.pi * g["d_i"]
    inner_and_wall = A_o / (A_i * h_in) + A_o * math.log(g["d_o"] / g["d_i"]) / (2 * math.pi * sizer.K_WALL)
    gas_side = 1.0 / r["U"] - inner_and_wall
    assert gas_side > 0
    # the finned area is ~10x the inner area: the d_o/d_i form would overstate U a lot
    assert A_o / A_i > 5
    wrong_U = 1.0 / (g["d_o"] / (g["d_i"] * h_in) + g["d_o"] * math.log(g["d_o"] / g["d_i"]) / (2 * sizer.K_WALL) + gas_side)
    assert wrong_U > 1.1 * r["U"]


def test_selector_picks_the_lightest_family():
    spec = DesignSpec(hot=_coolant(), cold=_air(), q_target=200e3)
    sel = HeatExchangerSelector(spec)
    best = sel.select_best()
    assert best.weight == min(c.weight for c in sel.candidates())


def test_per_unit_caps_are_enforced_inside_the_sizers():
    spec = DesignSpec(hot=_coolant(), cold=_air(), q_target=200e3, max_weight=5.0)
    for d in HeatExchangerSelector(spec).candidates():
        assert d.weight <= 5.0


def test_thermal_solve_is_zero_without_driving_temperature_difference():
    assert thermal_solve(_coolant(T=300.0), _air(T=300.0), 1e4, FlowArrangement.COUNTERFLOW) == 0.0


# ---------------------------------------------------------------------------------------
# Ram-air drag
# ---------------------------------------------------------------------------------------

def test_ram_drag_grows_as_intake_recovery_drops_and_with_core_loss():
    base = dict(Q=2e6, mdot_air=40.0, T_amb=280.0, P_amb=90e3, V_inf=110.0, V_core=15.0)
    d = [ram_air_drag(dP_core=500.0, eta_ram=e, **base) for e in (1.0, 0.9, 0.8, 0.7)]
    assert all(math.isfinite(x) for x in d)
    assert d == sorted(d)
    assert ram_air_drag(dP_core=2000.0, eta_ram=0.8, **base) > d[2]
    # cannot exceed the full inlet momentum (air leaving at rest)
    assert ram_air_drag(dP_core=1e9, eta_ram=0.8, **base) == pytest.approx(40.0 * 110.0)


def test_heating_reduces_ram_drag_meredith_effect():
    base = dict(mdot_air=40.0, T_amb=280.0, P_amb=90e3, V_inf=110.0, V_core=15.0,
                dP_core=800.0, eta_ram=0.85)
    assert ram_air_drag(Q=3e6, **base) < ram_air_drag(Q=0.1e6, **base)


# ---------------------------------------------------------------------------------------
# TMS subsystem (Class II), with a minimal aircraft stub
# ---------------------------------------------------------------------------------------

def _tms(**tms_input):
    fc = SimpleNamespace(T_op=353.15, Target_Press=1.5e5, comp_eta=0.75, stoich=2.0)
    aircraft = SimpleNamespace(fuelcell=fc, mission=SimpleNamespace(DISA=0.0),
                               EnergyInput={'HEX Specific Power H2': 5000.0},
                               TMSInput={'TMS Class': 'II', **tms_input})
    t = ThermalManagementSystem(aircraft)
    t.SetInput()
    return t


def _point(Q=2e6, alt=3000.0, V=110.0, name='p'):
    return {'name': name, 'Q_fc': Q, 'altitude': alt, 'V_inf': V, 'mdot_h2': Q / 8e7}


def test_class_defaults_to_I_and_rejects_unknown():
    aircraft = SimpleNamespace(TMSInput=None, EnergyInput={'HEX Specific Power H2': 4000.0})
    t = ThermalManagementSystem(aircraft)
    t.SetInput()
    assert t.Class == 'I'
    assert t.ClassI_Mass(2e6) == pytest.approx(500.0)
    aircraft.TMSInput = {'TMS Class': 'III'}
    with pytest.raises(ValueError):
        t.SetInput()


@needs_coolprop
def test_zero_heat_point_gives_an_empty_tms_without_raising():
    r = _tms().SizeAtPoint(_point(Q=0.0))
    assert r.total_mass == 0.0 and r.units == [] and r.heat_shortfall == 0.0


@needs_coolprop
def test_hydrogen_sink_is_the_coolprop_enthalpy_rise_with_latent_heat():
    from CoolProp.CoolProp import PropsSI
    t = _tms()
    p = _point(Q=2e6)
    c = t._conditions(p)
    P = t.h2_supply_pressure
    dh = (PropsSI('H', 'T', 353.15 - t.h2_approach_delta_T, 'P', P, 'ParaHydrogen')
          - PropsSI('H', 'P', P, 'Q', 0, 'ParaHydrogen'))
    assert c['q_h2_target'] == pytest.approx(p['mdot_h2'] * dh, rel=1e-9)
    latent = PropsSI('H', 'P', P, 'Q', 1, 'ParaHydrogen') - PropsSI('H', 'P', P, 'Q', 0, 'ParaHydrogen')
    assert dh > latent > 0


@needs_coolprop
def test_heat_balance_closes_and_hardware_rejects_design_heat():
    t = _tms()
    p = _point(Q=2e6)
    r = t.SizeAtPoint(p)
    hb = r.heat_balance
    assert hb['reactants'] + hb['HEX H2'] + hb['HEX ram air'] + hb['unmet'] == pytest.approx(2e6, rel=1e-9)
    q_rej, q_req = t.RateAtPoint(r, p)
    assert q_rej == pytest.approx(q_req, rel=1e-6)
    assert r.pump_power > 0 and r.pump_mass > 0 and r.total_mass > r.hex_mass


@needs_coolprop
def test_mass_is_monotone_in_the_heat_load():
    """The source had a 2-6 % downward sawtooth at every change of the unit count."""
    t = _tms()
    masses = [t.SizeAtPoint(_point(Q=q * 1e6)).total_mass for q in (1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0)]
    assert masses == sorted(masses)


@needs_coolprop
def test_design_point_selection_is_deterministic_and_feasible_everywhere():
    t = _tms()
    profile = [_point(Q=3e6, alt=100.0, V=80.0, name='Takeoff'),
               _point(Q=2.5e6, alt=2000.0, V=100.0, name='Climb'),
               _point(Q=1.2e6, alt=6000.0, V=130.0, name='Cruise'),
               _point(Q=0.2e6, alt=1000.0, V=90.0, name='Descent')]
    r1 = t.SizeForMission(profile)
    r2 = t.SizeForMission(profile)
    assert r1.total_mass == r2.total_mass
    assert r1.design_point['name'] == r2.design_point['name']
    chosen = [c for c in r1.candidates if c['point'] == r1.design_point['name']][0]
    assert chosen['feasible']
    for p in profile:
        q_rej, q_req = t.RateAtPoint(r1, p)
        assert q_rej >= (1 - t.FEASIBILITY_TOLERANCE) * q_req
    # points below half the peak heat are not tried as design points
    assert 'Descent' not in [c['point'] for c in r1.candidates]


@needs_coolprop
def test_ram_drag_coefficient_uses_the_design_point_dynamic_pressure():
    t = _tms(**{'TMS Ram Recovery': 0.8})
    r = t.SizeAtPoint(_point(Q=2e6, alt=3000.0, V=110.0))
    assert r.ram_drag > 0
    _, _, rho = t._ambient(3000.0)
    assert t.RamDragCoefficient(r, 60.0) == pytest.approx(r.ram_drag / (0.5 * rho * 110.0 ** 2 * 60.0))


@needs_coolprop
def test_takeoff_coolant_overtemperature_lightens_the_takeoff_design():
    p = {**_point(Q=3e6, alt=100.0, V=80.0, name='Takeoff'), 'takeoff': True}
    base = _tms().SizeAtPoint(p).total_mass
    hot = _tms(**{'TMS Takeoff Coolant Overtemperature': 15.0}).SizeAtPoint(p).total_mass
    assert hot < base
    # only the take-off point is affected
    q = _point(Q=3e6, alt=100.0, V=80.0, name='Climb')
    assert _tms(**{'TMS Takeoff Coolant Overtemperature': 15.0}).SizeAtPoint(q).total_mass == \
        pytest.approx(_tms().SizeAtPoint(q).total_mass, rel=1e-12)


@pytest.mark.parametrize("sizer_cls", [PlainTubeBankSizer, FinnedTubeBankSizer, PlateFinSizer])
def test_draw_hex_renders_every_family(sizer_cls):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PhlyGreen.Systems.Thermal.plotting import draw_hex
    if sizer_cls is PlateFinSizer:
        hot, cold, q = _coolant(mdot=2.0), FluidStream("h2", 0.02, 14000.0, 7e-6, 0.12, 0.25, 22.0), 50e3
    else:
        hot, cold, q = _coolant(), _air(), 200e3
    d = sizer_cls(DesignSpec(hot=hot, cold=cold, q_target=q)).best_candidate()
    fig = draw_hex(d, n_parallel=3)
    assert len(fig.axes) == 3
    plt.close(fig)
