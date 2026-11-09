"""Each Class-II efficiency model is evaluated at the power through its own component.

Pins the power every model of the powertrain graph receives (``Powertrain.eta`` lists the
conventions): gas turbine at its shaft output, propeller at its shaft input, motor at its
shaft output, serial generator at its electrical output, gearbox and PMAD at their input,
fuel cell at its electrical output. Also pins the fixed-point iteration (self-consistent
result, bit-identical with constant models), the serial motor model, the propulsive-share
phi of the fuel-cell graph, the engine count and the input fixes of the fuel-cell
configurations.
"""

import warnings

import numpy as np
import pytest

import PhlyGreen as pg
import _sample_configs as sc
from PhlyGreen.Systems.Powertrain.efficiency import (
    CallableEfficiency, ConstantEfficiency, HamiltonPropellerEfficiency, MotorEfficiencyModel)
from PhlyGreen.Systems.Powertrain.graph import (
    traditional_graph, parallel_hybrid_graph, serial_hybrid_graph, fuelcell_battery_graph)

ALT, VEL, PP = 6000.0, 130.0, 2.0e6


def _powertrain(configuration, hybrid_type=None, energy_update=None, propeller_input=None):
    """A powertrain after SetInput, built on the sample hybrid (or hydrogen) inputs."""
    if configuration in ('Hydrogen', 'FuelCellBattery'):
        _, kwargs = sc.hydrogen_config()
    else:
        _, kwargs = sc.hybrid_parallel_config()
    energy = dict(kwargs['EnergyInput'])
    if energy_update:
        energy.update(energy_update)
    ac = pg.build_aircraft()
    ac.Configuration = configuration
    ac.HybridType = hybrid_type
    ac.AircraftType = 'ATR'
    ac.weight.Class = 'I'
    ac.ReadInput(
        kwargs['AerodynamicsInput'], kwargs['ConstraintsInput'], kwargs['MissionInput'],
        energy, kwargs['MissionStages'], kwargs['DiversionStages'],
        WellToTankInput=kwargs.get('WellToTankInput'), CellInput=kwargs.get('CellInput'),
        ClimateImpactInput=kwargs.get('ClimateImpactInput'), PropellerInput=propeller_input,
    )
    return ac.powertrain


def _recording(pt, components):
    """Replace each component model by a constant-valued model that records the power it
    is evaluated at (not a ConstantEfficiency, so the iteration runs)."""
    seen = {}
    for c in components:
        value = pt.eta(c)
        seen[c] = []

        def fn(op, c=c, value=value):
            seen[c].append(op.power)
            return value
        if c == 'fuel_cell':
            pt.fc_model = CallableEfficiency(fn)
        else:
            pt.efficiency[c] = CallableEfficiency(fn)
    return seen


# --- the power each model receives ------------------------------------------------------

def test_traditional_component_powers():
    pt = _powertrain('Traditional')
    seen = _recording(pt, ('gas_turbine', 'gearbox', 'propeller'))
    x = pt.Traditional(ALT, VEL, PP)        # [Pf, Pgt, Pgb, Pp]
    assert seen['gas_turbine'][-1] == pytest.approx(x[1] * PP, rel=1e-12)   # shaft output
    assert seen['gearbox'][-1] == pytest.approx(x[1] * PP, rel=1e-12)       # input
    assert seen['propeller'][-1] == pytest.approx(x[2] * PP, rel=1e-12)     # shaft input
    assert seen['propeller'][-1] == pytest.approx(PP / pt.EtaPP, rel=1e-12)
    # the first pass is at the propulsive power (the first guess), the last at the component
    assert seen['gas_turbine'][0] == PP


def test_parallel_component_powers():
    pt = _powertrain('Hybrid', 'Parallel')
    comps = ('gas_turbine', 'gearbox', 'pmad', 'electric_motor', 'propeller')
    seen = _recording(pt, comps)
    x = pt.Hybrid(0.3, ALT, VEL, PP)        # [Pf, Pgt, Pgb, Ps1, Pe1, Pbat, Pp1]
    assert seen['gas_turbine'][-1] == pytest.approx(x[1] * PP, rel=1e-12)
    assert seen['gearbox'][-1] == pytest.approx((x[1] + x[2]) * PP, rel=1e-12)
    assert seen['pmad'][-1] == pytest.approx(x[5] * PP, rel=1e-12)
    assert seen['electric_motor'][-1] == pytest.approx(x[2] * PP, rel=1e-12)
    assert seen['propeller'][-1] == pytest.approx(x[3] * PP, rel=1e-12)


def test_serial_component_powers():
    pt = _powertrain('Hybrid', 'Serial')
    comps = ('gas_turbine', 'generator', 'pmad', 'electric_motor', 'gearbox', 'propeller')
    seen = _recording(pt, comps)
    x = pt.Hybrid(0.3, ALT, VEL, PP)        # [Pf, Pgt, Pgb, Ps1, Pe1, Pbat, Pgen, Pp1]
    assert seen['gas_turbine'][-1] == pytest.approx(x[1] * PP, rel=1e-12)
    assert seen['generator'][-1] == pytest.approx(x[3] * PP, rel=1e-12)
    assert seen['pmad'][-1] == pytest.approx((x[3] + x[5]) * PP, rel=1e-12)
    assert seen['electric_motor'][-1] == pytest.approx(x[2] * PP, rel=1e-12)
    assert seen['gearbox'][-1] == pytest.approx(x[2] * PP, rel=1e-12)
    assert seen['propeller'][-1] == pytest.approx(x[6] * PP, rel=1e-12)


def test_fuelcell_battery_component_powers():
    pt = _powertrain('FuelCellBattery', energy_update={'Eta Fuel Cell': 0.5})
    comps = ('fuel_cell', 'pmad', 'electric_motor', 'gearbox', 'propeller')
    seen = _recording(pt, comps)
    x = pt.PowerRatioFuelCellBattery(0.3, ALT, VEL, PP)   # [PfH2, Pfc, Pbat, Pe1, Pem, Pgb, Pp1]
    assert seen['fuel_cell'][-1] == pytest.approx(x[1] * PP, rel=1e-12)
    assert seen['pmad'][-1] == pytest.approx((x[1] + x[2]) * PP, rel=1e-12)
    assert seen['electric_motor'][-1] == pytest.approx(x[4] * PP, rel=1e-12)
    assert seen['gearbox'][-1] == pytest.approx(x[4] * PP, rel=1e-12)
    assert seen['propeller'][-1] == pytest.approx(x[5] * PP, rel=1e-12)


def test_class_ii_gas_turbine_reads_its_map_at_the_shaft_power():
    """The packaged response surface compares the power with a shaft rating."""
    from PhlyGreen.Systems.Powertrain.efficiency import OperatingPoint
    alt = 3000.0                             # below the altitude where 4 MW is power-limited
    pt = _powertrain('Traditional', energy_update={
        'Eta Gas Turbine Model': 'ResponseSurface', 'GT Design Power': 4.0e6})
    x = pt.Traditional(alt, VEL, PP)
    eta_at_shaft = pt.eta('gas_turbine', alt, VEL, x[1] * PP)
    assert x[0] == pytest.approx(x[1] / eta_at_shaft, rel=1e-8)
    # the map is part-load dependent, so reading it at Pp (before the fix) differs
    eta_at_pp = pt.efficiency['gas_turbine'].eta(OperatingPoint(alt, VEL, PP))
    assert eta_at_pp < eta_at_shaft


# --- fixed point ------------------------------------------------------------------------

def test_power_dependent_model_gives_a_self_consistent_solution():
    pt = _powertrain('Hybrid', 'Parallel')
    pt.em_model = MotorEfficiencyModel(design_kw=1000, design_v=800, design_rpm=11000,
                                       n_engines=2)
    x = pt.Hybrid(0.3, ALT, VEL, PP)
    # Re-solving with every efficiency frozen at its own component power reproduces x.
    eta_em = pt.eta('electric_motor', ALT, VEL, x[2] * PP)
    frozen = np.abs(parallel_hybrid_graph(pt.EtaGT, pt.EtaGB, pt.EtaPM, eta_em, pt.EtaPP,
                                          0.3).solve())
    assert np.allclose(x, frozen, rtol=1e-8, atol=0.0)


def test_constant_models_are_bit_identical_to_the_plain_graph():
    pt = _powertrain('Hybrid', 'Parallel')
    x = pt.Hybrid(0.3, ALT, VEL, PP)
    ref = np.abs(parallel_hybrid_graph(pt.EtaGT, pt.EtaGB, pt.EtaPM, pt.EtaEM, pt.EtaPP,
                                       0.3).solve())
    assert np.array_equal(x, ref)
    pt = _powertrain('Traditional')
    assert np.array_equal(pt.Traditional(ALT, VEL, PP),
                          traditional_graph(pt.EtaGT, pt.EtaGB, pt.EtaPP).solve())


# --- serial motor model -----------------------------------------------------------------

def test_serial_hybrid_uses_the_motor_model():
    pt = _powertrain('Hybrid', 'Serial')
    assert pt.eta('electric_motor') == pt.EtaEM2
    assert pt.eta('generator') == pt.EtaEM1
    base = pt.Hybrid(0.3, ALT, VEL, PP)
    ref = np.abs(serial_hybrid_graph(pt.EtaGT, pt.EtaEM1, pt.EtaPM, pt.EtaEM2, pt.EtaGB,
                                     pt.EtaPP, 0.3).solve())
    assert np.array_equal(base, ref)
    pt.em_model = ConstantEfficiency(0.80)
    lossy = pt.Hybrid(0.3, ALT, VEL, PP)
    assert lossy[0] > base[0]                # a worse motor needs more fuel


def test_smart_motor_acts_on_the_serial_motor():
    pt = _powertrain('Hybrid', 'Serial', energy_update={
        'Eta Electric Motor Model': 'Smart', 'EM Design Power': 3.0e6})
    assert isinstance(pt.efficiency['electric_motor'], MotorEfficiencyModel)
    x = pt.Hybrid(0.3, ALT, VEL, PP)
    assert x[4] * pt.eta('electric_motor', ALT, VEL, x[2] * PP) == pytest.approx(x[2], rel=1e-8)


# --- fuel-cell graph: phi and inputs ----------------------------------------------------

@pytest.mark.parametrize("phi", [0.0, 0.2, 0.5])
def test_fuelcell_graph_phi_is_the_propulsive_share(phi):
    eta = dict(eta_fc=0.5, eta_pm=0.99, eta_em=0.96, eta_gb=0.96, eta_pp=0.9)
    x = fuelcell_battery_graph(phi=phi, **eta).solve()
    chain = eta['eta_pm'] * eta['eta_em'] * eta['eta_gb'] * eta['eta_pp']
    # battery delivers phi * Pp, as in Mission.FuelCellBatteryConfiguration
    assert x[2] * chain == pytest.approx(phi, abs=1e-12)
    assert x[1] * chain == pytest.approx(1.0 - phi, abs=1e-12)


def test_fuelcell_configurations_read_pmad_and_motor_efficiencies():
    for cfg in ('Hydrogen', 'FuelCellBattery'):
        pt = _powertrain(cfg)
        assert pt.eta('pmad') == 0.99
        assert pt.eta('electric_motor') == 0.96


def test_fuelcell_graph_needs_a_fuel_cell_efficiency():
    pt = _powertrain('FuelCellBattery')
    with pytest.raises(ValueError, match="Eta Fuel Cell"):
        pt.PowerRatioFuelCellBattery(0.2, ALT, VEL, PP)
    pt.EtaFC = 0.5
    assert pt.PowerRatioFuelCellBattery(0.2, ALT, VEL, PP)[6] == pytest.approx(1.0)


# --- engine count -----------------------------------------------------------------------

@pytest.mark.parametrize("configuration,hybrid_type", [
    ('Traditional', None), ('Hybrid', 'Parallel'), ('Hybrid', 'Serial'),
    ('Hydrogen', None), ('FuelCellBattery', None)])
def test_engine_count_defaults_to_two(configuration, hybrid_type):
    assert _powertrain(configuration, hybrid_type).n_engines == 2


def test_engine_count_from_propeller_input():
    pt = _powertrain('Traditional', propeller_input={'Number of Engines': 4})
    assert pt.n_engines == 4
    with pytest.warns(DeprecationWarning):
        pt = _powertrain('Traditional', propeller_input={'N_ENGINES': 3})
    assert pt.n_engines == 3


def test_hamilton_propeller_uses_the_powertrain_engine_count():
    prop = {'Number of Engines': 4, 'Propeller Diameter': 3.96, 'RPM': 1063,
            'N_BLADES': 6, 'ACTIVITY_FACTOR': 167, 'INTEGRATED_LIFT_COEFFICIENT': 0.5}
    pt = _powertrain('Traditional', energy_update={'Eta Propulsive Model': 'Hamilton'},
                     propeller_input=prop)
    assert pt.Propeller.n_engines == 4


# --- silent defaults --------------------------------------------------------------------

def test_missing_constant_efficiencies_warn():
    _, kwargs = sc.hybrid_parallel_config()
    energy = {k: v for k, v in kwargs['EnergyInput'].items()
              if k not in ('Eta Gas Turbine', 'Eta Propulsive')}
    with pytest.warns(UserWarning) as record:
        ac = pg.build_aircraft()
        ac.Configuration, ac.HybridType, ac.AircraftType = 'Traditional', None, 'ATR'
        ac.ReadInput(kwargs['AerodynamicsInput'], kwargs['ConstraintsInput'],
                     kwargs['MissionInput'], energy, kwargs['MissionStages'],
                     kwargs['DiversionStages'])
    messages = " ".join(str(w.message) for w in record)
    assert "'Eta Gas Turbine' is not set" in messages
    assert "'Eta Propulsive' is not set" in messages
    assert ac.powertrain.eta('gas_turbine') == 0.30
    assert ac.powertrain.eta('propeller') == 0.85


# --- fuel-cell drive: motor and propeller at their shaft powers --------------------------

def test_fuelcell_drive_constant_efficiencies_are_unchanged():
    fc = _powertrain('Hydrogen').aircraft.fuelcell
    assert fc.drive_efficiencies(ALT, VEL, PP) == (fc.EtaEM, fc.EtaProp)


def test_fuelcell_drive_smart_motor_gets_its_shaft_power():
    pt = _powertrain('FuelCellBattery', energy_update={
        'Eta Electric Motor Model': 'Smart', 'EM Design Power': 3.0e6})
    fc = pt.aircraft.fuelcell
    seen = _recording(pt, ('electric_motor',))
    eta_em, eta_prop = fc.drive_efficiencies(ALT, VEL, PP)
    assert seen['electric_motor'][-1] == pytest.approx(PP / (fc.EtaGB * eta_prop), rel=1e-12)
    # the battery branch of the mission uses the same drive
    m = pt.aircraft.mission
    assert m._fc_battery_eta_elec(ALT, VEL, PP) == eta_em * fc.EtaPM * fc.EtaGB * eta_prop


def test_fuelcell_drive_propeller_is_read_at_its_shaft_input():
    pt = _powertrain('Hydrogen')
    fc = pt.aircraft.fuelcell

    class LoadDependentPropeller:
        def ComputePropEfficiency(self, alt, vel, shaft_power):
            return 0.9 - 1e-8 * shaft_power
    pt.Propeller = LoadDependentPropeller()
    pt.efficiency['propeller'] = HamiltonPropellerEfficiency(pt.Propeller)
    _, eta_prop = fc.drive_efficiencies(ALT, VEL, PP)
    assert eta_prop == pytest.approx(0.9 - 1e-8 * PP / eta_prop, abs=1e-8)


def test_fuelcell_drive_uses_the_powertrain_propeller_model():
    """The fuel-cell drive reads the same bounded propeller model as the gas-turbine graphs,
    so a windmilling Hamilton propeller (efficiency 0 at low power and take-off speed, the
    taxi legs) does not ask the battery for infinite power."""
    pt = _powertrain('FuelCellBattery')
    fc = pt.aircraft.fuelcell

    class WindmillingPropeller:
        def ComputePropEfficiency(self, alt, vel, shaft_power):
            return 0.0
    pt.Propeller = WindmillingPropeller()
    pt.efficiency['propeller'] = HamiltonPropellerEfficiency(pt.Propeller)
    _, eta_prop = fc.drive_efficiencies(ALT, VEL, PP)
    assert eta_prop == pt.eta('propeller', ALT, VEL, PP) == 0.4
    assert np.isfinite(pt.aircraft.mission._fc_battery_terminal_power(ALT, VEL, 0.07 * PP))


# --- serial range extender ---------------------------------------------------------------

def _range_extender_mission(energy_update=None):
    update = {'GT Rated Power': 2.0e6}
    update.update(energy_update or {})
    pt = _powertrain('Hybrid', 'Serial', energy_update=update)
    return pt, pt.aircraft.mission


def test_range_extender_constant_flows_are_unchanged():
    pt, m = _range_extender_mission()
    P_gt = m._range_extender_gt_power(ALT)
    Pe1 = PP / (pt.EtaPP * pt.EtaGB * pt.EtaEM2)
    expected = (P_gt / pt.EtaGT, Pe1 / pt.EtaPM - P_gt * pt.EtaEM1)
    assert m._range_extender_flows(PP, ALT, VEL) == expected
    assert m._serial_motor_shaft_power(PP, ALT, VEL) == PP / (pt.EtaPP * pt.EtaGB)
    assert m._serial_bus_power(PP, ALT, VEL) == PP / (pt.EtaPP * pt.EtaGB) / pt.EtaEM2


def test_range_extender_uses_the_motor_and_generator_models():
    pt, m = _range_extender_mission()
    base = m._range_extender_flows(PP, ALT, VEL)
    seen = _recording(pt, ('electric_motor', 'generator', 'propeller'))
    assert m._range_extender_flows(PP, ALT, VEL) == pytest.approx(base, rel=1e-12)
    P_gt = m._range_extender_gt_power(ALT)
    assert seen['electric_motor'][-1] == pytest.approx(PP / (pt.EtaPP * pt.EtaGB), rel=1e-12)
    assert seen['propeller'][-1] == pytest.approx(PP / pt.EtaPP, rel=1e-12)
    assert seen['generator'][-1] == pytest.approx(P_gt * pt.EtaEM1, rel=1e-12)
    pt.em_model = ConstantEfficiency(0.80)
    assert m._range_extender_flows(PP, ALT, VEL)[1] > base[1]   # worse motor, more battery


# --- OEI engine count --------------------------------------------------------------------

def test_oei_factor_follows_the_powertrain_engine_count():
    two = _powertrain('Traditional').aircraft.performance
    four = _powertrain('Traditional', propeller_input={'Number of Engines': 4}).aircraft.performance
    assert two.n_engines == 2 and four.n_engines == 4


# --- damping of the fixed point -------------------------------------------------------------

def _steep_propeller(op):
    """A propeller whose efficiency rises steeply with shaft power (a Hamilton propeller at
    descent power): the undamped iteration P <- PP / eta(P) oscillates around the solution."""
    return float(np.clip(0.2 + 0.6 * (op.power / PP - 1.0), 0.4, 0.85))


def test_component_powers_converge_where_the_plain_iteration_oscillates():
    pt = _powertrain('Traditional')
    pt.efficiency['propeller'] = CallableEfficiency(_steep_propeller)
    with warnings.catch_warnings():
        warnings.simplefilter('error')                    # no "did not converge" warning
        x = pt.Traditional(ALT, VEL, PP)
    P_shaft = x[2] * PP
    eta = pt.eta('propeller', ALT, VEL, P_shaft)
    assert P_shaft == pytest.approx(PP / eta, rel=1e-5)   # self-consistent shaft power


def test_fuelcell_drive_propeller_converges_where_the_plain_iteration_oscillates():
    pt = _powertrain('Hydrogen')
    fc = pt.aircraft.fuelcell

    class SteepPropeller:
        def ComputePropEfficiency(self, alt, vel, shaft_power):
            return 0.2 + 0.6 * (shaft_power / PP - 1.0)
    pt.Propeller = SteepPropeller()
    pt.efficiency['propeller'] = HamiltonPropellerEfficiency(pt.Propeller)
    _, eta_prop = fc.drive_efficiencies(ALT, VEL, PP)
    assert eta_prop == pytest.approx(pt.eta('propeller', ALT, VEL, PP / eta_prop), abs=1e-6)
