"""The FLOPS Class-II component equations reproduce NASA Aviary's FLOPS-based masses.

Reference: Aviary (github.com/OpenMDAO/Aviary), test case ``large_single_aisle_1``
(``aviary/validation_cases/validation_data/test_data/large_single_aisle_1_FLOPS_data.py``),
a FLOPS model of a 181,200 lb single-aisle transport. The inputs and the expected masses [lb]
below are copied from that file. The components are fed the same inputs through a minimal
stand-in for the aircraft (wing area, span, Mach, range and thrust are the quantities
``sizing_inputs`` takes from the sizing).

Two items are not compared: the wing bending material (the Aviary case uses the detailed
wing, PhlyGreen the simple one) and the paint (the Aviary case overrides the wetted areas).
The landing gear is compared at the FLOPS design landing weight, which PhlyGreen computes
from the range and Mach number, while the Aviary case gives it as an input (152,800 lb):
the expected gear masses are rescaled with the FLOPS exponents.
"""

import types

import numpy as np
import pytest

import PhlyGreen.Utilities.Units as Units
from PhlyGreen.Weight.Components import (Wing, Fuselage, Tail, LandingGear, SystemEquipment,
                                         Nacelle, OperatingItems)
from PhlyGreen.Weight.Components.sizing_inputs import G, N_PER_LBF

GROSS_LB = 181200.0
WING_AREA_FT2 = 1370.0
SPAN_FT = 117.83
THRUST_PER_ENGINE_LBF = 28928.1
RANGE_NM = 3500.0
MACH = 0.785

FLOPS_INPUT = {
    'GROSS_WEIGHT': Units.lbTokg(GROSS_LB),
    'MAX_MACH': MACH,
    'WING': {'STRUT_BRACING_FACTOR': 0., 'TAPER_RATIO': 0.278, 'THICKNESS_TO_CHORD': 0.13,
             'AEROELASTIC_TAILORING_FACTOR': 0., 'SWEEP': 25.0, 'COMPOSITE_FRACTION': 0.2,
             'ULTIMATE_LOAD_FACTOR': 3.75, 'VAR_SWEEP_MASS_PENALTY': 0., 'LOAD_FRACTION': 1.0,
             'SCALER': 1.23},
    'VERTICAL_TAIL': {'AREA': 284.0, 'TAPER_RATIO': 0.33, 'N_VERTICAL_TAILS': 1., 'SCALER': 1.0},
    'HORIZONTAL_TAIL': {'AREA': 355.0, 'TAPER_RATIO': 0.22, 'SCALER': 1.2},
    'FUSELAGE': {'LENGTH': 128.0, 'MAX_HEIGHT': 13.17, 'MAX_WIDTH': 12.33, 'NUM_FUSELAGES': 1.,
                 'TOTAL_NUM_FUSELAGE_ENGINES': 0., 'MILITARY_CARGO_FLOOR': False,
                 'SCALER': 1.05},
    'LANDING_GEAR': {'MAIN_GEAR_LENGTH': 102.0, 'NOSE_GEAR_LENGTH': 67.0,
                     'MAIN_SCALER': 1.1, 'NOSE_SCALER': 1.0},
    'NACELLE': {'AVG_DIAM': 7.94, 'AVG_LENGTH': 12.3, 'SCALER': 1.0},
    'SYSTEM_EQUIPMENT': {'PLANFORM_AREA': 128.0 * 12.33, 'N_PAX': 169, 'N_CREW': 2,
                         'N_FIRST_CLASS': 11, 'N_BUSINESS_CLASS': 0, 'N_TOURIST_CLASS': 158,
                         'PASSENGER_COMPARTMENT_LENGTH': 85.5, 'SYSTEM_PRESSURE': 3000.,
                         'CONTROL_SURFACE_AREA_RATIO': 0.1, 'ANTIICING_SCALER': 1.0,
                         'APU_SCALER': 1.1, 'AVIONICS_SCALER': 1.2, 'AC_SCALER': 1.0,
                         'ELECTRICAL_SCALER': 1.25, 'FURNISHING_SCALER': 1.1,
                         'HYDRAULICS_SCALER': 1.0, 'SURFACE_CONTROLS_SCALER': 1.0,
                         'INSTRUMENTS_SCALER': 1.25},
    'ENGINE': {'N_ENGINES': 2., 'N_WING_ENGINES': 2, 'N_FUSELAGE_ENGINES': 0},
    'FUEL': {'MAX_CAPACITY': 45694.0, 'NUM_TANKS': 7, 'DENSITY': 6.7},
}


def _aircraft():
    """Stand-in exposing what the components read from a sized aircraft."""
    area_m2 = Units.ft2tom2(WING_AREA_FT2)
    return types.SimpleNamespace(
        Configuration='Turbofan',
        DesignWTOoS=FLOPS_INPUT['GROSS_WEIGHT'] * G / area_m2,
        aerodynamics=types.SimpleNamespace(AR=SPAN_FT**2 / WING_AREA_FT2),
        constraint=types.SimpleNamespace(
            CruiseConstraints={'Speed': MACH, 'Speed Type': 'Mach', 'Altitude': 10000.},
            DISA=0.0),
        mission=types.SimpleNamespace(profile=types.SimpleNamespace(
            MissionRange=Units.NMtoM(RANGE_NM))),
        powertrain=types.SimpleNamespace(engineRating=2 * THRUST_PER_ENGINE_LBF * N_PER_LBF),
    )


def _component(cls):
    return cls(_aircraft(), FLOPS_INPUT)


def test_span_and_area_follow_the_sizing():
    wing = _component(Wing)
    from PhlyGreen.Weight.Components.sizing_inputs import wing_area_ft2, wing_span_ft
    assert wing_area_ft2(wing.aircraft, FLOPS_INPUT) == pytest.approx(WING_AREA_FT2, rel=1e-5)
    assert wing_span_ft(wing.aircraft, FLOPS_INPUT) == pytest.approx(SPAN_FT, rel=1e-5)


def test_wing_shear_and_misc_terms():
    wing = _component(Wing)
    assert wing.calcW2() == pytest.approx(4998.8, rel=1e-3)       # SHEAR_CONTROL_MASS
    assert wing.calcW3() == pytest.approx(1668.3, rel=1e-3)       # MISC_MASS


@pytest.mark.parametrize("method, attr, expected", [
    (lambda c: c.FuselageMass(), 'fuselagemass', 18357.0),
    (lambda c: c.HorizontalTailMass(), 'HTailmass', 1831.0),
    (lambda c: c.VerticalTailMass(), 'VTailmass', 1221.8),
], ids=["fuselage", "horizontal tail", "vertical tail"])
def test_fuselage_and_tails(method, attr, expected):
    cls = Fuselage if attr == 'fuselagemass' else Tail
    comp = _component(cls)
    method(comp)
    assert getattr(comp, attr) == pytest.approx(expected, rel=1e-3)


def test_nacelles_are_counted_per_engine():
    nacelle = _component(Nacelle)
    nacelle.NacelleMass()
    assert nacelle.nacellemass == pytest.approx(2 * 985.691, rel=1e-3)   # 985.691 per engine


def test_landing_gear_at_the_flops_design_landing_weight():
    gear = _component(LandingGear)
    landing = gear.design_landing_weight_lb()
    cruise_factor = 5e-5 / (1.0 + np.exp(-1000.0 * (MACH - 1.0))) + 4e-5
    assert landing == pytest.approx(GROSS_LB * (1 - cruise_factor * RANGE_NM), rel=1e-5)
    gear.LandingGearMass()
    expected = (7910.32 * (landing / 152800.0)**0.95       # MAIN_GEAR_MASS at 152,800 lb
                + 870.59 * (landing / 152800.0)**0.67)     # NOSE_GEAR_MASS
    assert gear.Landing_gearmass == pytest.approx(expected, rel=1e-3)


@pytest.mark.parametrize("method, expected", [
    ("AirConditioningMass", 1602.0),
    ("AntiIcingMass", 208.85),
    ("APUMass", 1142.0),
    ("AvionicsMass", 1652.6),
    ("ElectricalMass", 2464.0),
    ("FurnishingMass", 15517.0),
    ("HydraulicsMass", 1086.7),
    ("InstrumentsMass", 601.0),
    ("SurfaceControlsMass", 894.0),
])
def test_systems_and_equipment(method, expected):
    systems = _component(SystemEquipment)
    assert getattr(systems, method)() == pytest.approx(expected, rel=2e-3)


@pytest.mark.parametrize("method, expected", [
    ("FuelSystemMass", 669.58),
    ("UnusableFuelMass", 501.3),
    ("EngineOilMass", 130.23),
    ("StarterMass", 560.39),
    ("EngineControlsMass", 648.83 - 560.39),     # TOTAL_MISC_MASS = starter + controls
    ("PassengerServiceMass", 3022.74805809),
    ("ThrustReverserMass", 0.0),                 # the Aviary case has no reversers
])
def test_operating_items(method, expected):
    items = _component(OperatingItems)
    assert getattr(items, method)() == pytest.approx(expected, rel=2e-3)


def test_thrust_reversers_follow_the_flops_equation():
    import copy
    flops = copy.deepcopy(FLOPS_INPUT)
    flops['ENGINE']['THRUST_REVERSERS'] = True
    items = OperatingItems(_aircraft(), flops)
    assert items.ThrustReverserMass() == pytest.approx(0.034 * THRUST_PER_ENGINE_LBF * 2, rel=1e-6)
