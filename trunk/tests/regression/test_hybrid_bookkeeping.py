"""Battery-model and hybrid bookkeeping checks: phi at segment boundaries, optional cell
inputs, cell rescaling, the cell heat balance, and the sizing of the serial electric drive."""

import os
import sys

import numpy as np
import pytest

import PhlyGreen as pg
from PhlyGreen.config import CellConfig
from PhlyGreen.Systems.Battery.Cell_Models import Cell_Models

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "examples"))
from common import hybrid_config                                   # noqa: E402


def test_phi_at_a_segment_start_is_that_segments_phi():
    a = pg.build_aircraft()
    a.configure(hybrid_config('I'), design=False)
    p = a.mission.profile
    for i in range(len(p.times) - 1):
        # SPW row i+1 holds (phi_start, phi_end) of segment i (row 0 is the take-off phi)
        assert float(p.SuppliedPowerRatio(p.times[i])) == pytest.approx(p.SPW[i + 1][0])
        assert float(p.SuppliedPowerRatio(p.times[i + 1] - 1e-6)) == pytest.approx(
            p.SPW[i + 1][1], abs=1e-6)


def test_class_ii_cell_inputs_left_unset_use_the_fallbacks():
    cfg = hybrid_config('II')
    cfg.cell = CellConfig(cell_class='II', minimum_soc=0.2, initial_temperature=25,
                          max_operative_temperature=50)       # no model, energy, power, voltage
    a = pg.build_aircraft()
    a.configure(cfg, design=False)
    cell = Cell_Models['Finger-Cell-Thermal']
    assert a.battery.cell_capacity == cell['Cell Capacity']
    assert a.battery.pack_Vmax == 740


def test_rescaling_keeps_the_arrhenius_activation_temperatures():
    a = pg.build_aircraft()
    a.configure(hybrid_config('II'), design=False)      # specific energy and power rescale the cell
    cell = Cell_Models['Finger-Cell-Thermal']
    b = a.battery
    assert b.cell_capacity != cell['Cell Capacity']
    assert b.R_arrhenius == cell['Resistance Arrhenius Constant']
    assert b.K_arrhenius == cell['Polarization Arrhenius Constant']


def test_cell_heat_has_the_bernardi_sign():
    a = pg.build_aircraft()
    a.configure(hybrid_config('II'), design=False)
    b = a.battery
    b.Configure(100)
    b.T, b.it, b.phi = b.Tref + 10.0, 0.0, 0.0
    b.i = b.Power_2_current(2.0e5)
    i, V, Voc = b.cell_i, b.cell_Vout, b.cell_Voc
    _, q = b.heatLoss(288.15, 1.2)
    assert q == pytest.approx((Voc - V) * i - b.E_slope * i * b.T, rel=1e-12)


@pytest.mark.slow
def test_serial_electric_drive_is_sized_on_the_shaft_and_bus_power():
    a = pg.build_aircraft()
    a.configure(hybrid_config('I', hybrid_type='Serial'))
    pt, m = a.powertrain, a.mission
    motor = max(m.Max_PMotor, m.TO_PMotor)
    bus = max(m.Max_PBus, m.TO_PBus)
    # the motor carries the shaft power, more than the battery share
    assert motor > max(m.Max_PBat, m.TO_PBat)
    assert pt.WMotor == pytest.approx((motor + pt.engineRating) / pt.SPowerPT[1], rel=1e-12)
    assert pt.WPMAD == pytest.approx(bus / pt.pmad_specific_power(), rel=1e-12)


def test_endothermic_cell_gives_a_finite_temperature_rate():
    # at low current the reversible term can make the cell heat negative: no cooling flow,
    # and no NaN from the convection correlation
    a = pg.build_aircraft()
    a.configure(hybrid_config('II'), design=False)
    b = a.battery
    b.Configure(100)
    b.T, b.it, b.phi = b.Tref + 30.0, 0.0, 0.0
    b.i = b.Power_2_current(1.0)                 # a tiny load
    dTdt, q = b.heatLoss(288.15, 1.2)
    assert np.isfinite(dTdt) and b.mdot >= 0.0
