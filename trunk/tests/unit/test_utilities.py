"""Unit tests for the standalone Utilities (Atmosphere, Speed, Units).

These functions are pure and dependency-free, which makes them an ideal first stop for
learning how the code works: each test states a physical fact and checks the code agrees.
"""

import numpy as np
import pytest

import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed
import PhlyGreen.Utilities.Units as Units


# --- Atmosphere (International Standard Atmosphere) --------------------------

def test_sea_level_temperature_is_15C():
    assert ISA.atmosphere.Tstd(0) == pytest.approx(288.15)


def test_temperature_lapse_in_troposphere():
    # ISA troposphere lapse rate is 6.5 K per 1000 m.
    assert ISA.atmosphere.Tstd(1000) == pytest.approx(288.15 - 6.5, rel=1e-3)


def test_sea_level_pressure_is_standard():
    assert ISA.atmosphere.Pstd(0) == pytest.approx(101325.0, rel=1e-3)


def test_pressure_decreases_with_altitude():
    assert ISA.atmosphere.Pstd(5000) < ISA.atmosphere.Pstd(0)


def test_speed_of_sound_at_sea_level():
    # a = sqrt(gamma * R * T) ~= 340.3 m/s at 15 C.
    assert Speed.soundspeed(0, 0.0) == pytest.approx(ISA.atmosphere.a_sls)
    assert Speed.soundspeed(0, 0.0) == pytest.approx(340.3, abs=0.5)


# --- Speed conversions ------------------------------------------------------

def test_mach_to_tas_at_sea_level():
    assert Speed.Mach2TAS(0.5, 0) == pytest.approx(0.5 * ISA.atmosphere.a_sls)


def test_cas_equals_tas_at_sea_level():
    # By definition, calibrated airspeed equals true airspeed at standard sea level.
    assert Speed.CAS2TAS(100.0, 0) == pytest.approx(100.0, rel=1e-3)


def test_tas_exceeds_cas_at_altitude():
    # Lower density aloft -> TAS > CAS for the same dynamic pressure.
    assert Speed.CAS2TAS(100.0, 8000) > 100.0


@pytest.mark.parametrize("mach", [0.2, 0.4, 0.6])
@pytest.mark.parametrize("h", [0, 4000, 9000])
def test_mach_tas_roundtrip(mach, h):
    assert Speed.TAS2Mach(Speed.Mach2TAS(mach, h), h) == pytest.approx(mach, rel=1e-9)


@pytest.mark.parametrize("cas", [60.0, 120.0])
@pytest.mark.parametrize("h", [0, 6000])
def test_cas_tas_roundtrip(cas, h):
    assert Speed.TAS2CAS(Speed.CAS2TAS(cas, h), h) == pytest.approx(cas, rel=1e-6)


def test_eas_equals_tas_at_sea_level():
    # EAS == TAS at sea level only to ~1e-4: the ISA model's computed SLS density
    # (Pstd(0)/(R*Tstd(0)) with R=287) is 1.2253, slightly off the stored Rho_sls=1.225.
    assert Speed.EAS2TAS(100.0, 0) == pytest.approx(100.0, rel=2e-3)


@pytest.mark.parametrize("eas", [80.0, 150.0])
@pytest.mark.parametrize("h", [0, 7000])
def test_eas_tas_roundtrip(eas, h):
    assert Speed.TAS2EAS(Speed.EAS2TAS(eas, h), h) == pytest.approx(eas, rel=1e-9)


def test_tas_exceeds_eas_at_altitude():
    assert Speed.EAS2TAS(100.0, 8000) > 100.0


# --- Units ------------------------------------------------------------------

def test_unit_roundtrips():
    # Note: the kg<->lb constants (2.20462, 0.453592) are not exact inverses, so the
    # round-trip is only good to ~1e-6 relative; rel=1e-4 keeps the check meaningful.
    assert Units.lbTokg(Units.kgTolb(1000.0)) == pytest.approx(1000.0, rel=1e-4)
    assert Units.ftTom(Units.mToft(500.0)) == pytest.approx(500.0, rel=1e-4)
    assert Units.hpTow(Units.wTohp(1e6)) == pytest.approx(1e6, rel=1e-4)


def test_unit_directions():
    assert Units.kgTolb(1.0) > 1.0   # a kg is more than 2 lb
    assert Units.mToft(1.0) > 3.0    # a metre is ~3.28 ft
