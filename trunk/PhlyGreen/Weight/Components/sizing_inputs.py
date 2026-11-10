"""Quantities the FLOPS component equations take from the sizing, in FLOPS units.

The FLOPS equations (as transcribed in NASA's Aviary, ``aviary/subsystems/mass/flops_based``)
are written in imperial units: lb, lbf, ft, ft^2 and nautical miles. These functions return
the sizing quantities in those units, so every component reads them the same way:

* the wing area from the gross weight and the design wing loading;
* the span from the wing area and the aspect ratio of the aerodynamic model, so that the
  structural and the aerodynamic wing are the same wing;
* the design (cruise) and the maximum operating Mach number, and the design range;
* the sea-level static thrust per engine.
"""

import warnings

import numpy as np

import PhlyGreen.Utilities.Speed as Speed
import PhlyGreen.Utilities.Units as Units

G = 9.81                  # [m/s^2], the value the weight loop uses to turn W/S into a wing area
N_PER_LBF = 4.4482216152605


def wing_area_ft2(aircraft, flops_input):
    """Wing reference area [ft^2]: gross weight [kg] * g / design wing loading [N/m^2]."""
    area_m2 = flops_input['GROSS_WEIGHT'] * G / aircraft.DesignWTOoS
    return Units.m2toft2(area_m2)


def wing_span_ft(aircraft, flops_input):
    """Wing span [ft] = sqrt(AR * S), with AR the aspect ratio of the aerodynamic model.

    A ``'SPAN'`` entry in ``FLOPSInput['WING']`` is not used: a fixed span would not follow
    the wing area of the sizing, and the wing of the structural model would then have a
    different aspect ratio from the wing of the aerodynamic model.
    """
    if 'SPAN' in flops_input['WING']:
        warnings.warn(
            "FLOPSInput['WING']['SPAN'] is ignored: the span is sqrt(AR * S), with AR the "
            "aspect ratio of the aerodynamic model and S the sized wing area.",
            UserWarning, stacklevel=3)
    return float(np.sqrt(aircraft.aerodynamics.AR * wing_area_ft2(aircraft, flops_input)))


def design_mach(aircraft):
    """Design (cruise) Mach number, from the cruise constraint, converted if the constraint
    speed is not given as a Mach number."""
    cruise = aircraft.constraint.CruiseConstraints
    speed, speed_type = cruise['Speed'], cruise.get('Speed Type', 'Mach')
    altitude, disa = cruise['Altitude'], aircraft.constraint.DISA
    if speed_type == 'Mach':
        return float(speed)
    if speed_type == 'TAS':
        return float(Speed.TAS2Mach(speed, altitude, disa))
    if speed_type == 'KCAS':
        return float(Speed.CAS2Mach(Units.KNtoM(speed), altitude, disa))
    raise ValueError(f"FLOPS: unknown cruise 'Speed Type' {speed_type!r} "
                     "(expected 'Mach', 'TAS' or 'KCAS').")


def max_mach(aircraft, flops_input):
    """Maximum operating Mach number (FLOPS ``VMMO``), used by the systems, fuel-system,
    starter and passenger-service equations: ``FLOPSInput['MAX_MACH']`` if given, otherwise
    the design (cruise) Mach number."""
    if 'MAX_MACH' in flops_input:
        return float(flops_input['MAX_MACH'])
    return design_mach(aircraft)


def design_range_nm(aircraft):
    """Design range [nm]: the mission range of the profile."""
    return Units.MtoNM(aircraft.mission.profile.MissionRange)


def sls_thrust_per_engine_lbf(aircraft, flops_input):
    """Sea-level static thrust per engine [lbf].

    A 'Turbofan' is sized on thrust, so the sized rating is used (``engineRating`` is the
    total SLS thrust [N]). The power-rated configurations have no sized thrust: the value is
    the input ``FLOPSInput['ENGINE']['MAX_SLS_THRUST']``, per engine, in lbf.
    """
    n_engines = flops_input['ENGINE']['N_ENGINES']
    if aircraft.Configuration == 'Turbofan':
        return aircraft.powertrain.engineRating / n_engines / N_PER_LBF
    return flops_input['ENGINE']['MAX_SLS_THRUST']


def engine_count_factor(n_engines):
    """FLOPS distributed-propulsion engine count factor (Aviary
    ``distributed_engine_count_factor``): the engine count up to four engines."""
    if n_engines > 4:
        return 4.0 + 2.0 * np.arctan((n_engines - 4.0) / 3.0)
    return float(n_engines)
