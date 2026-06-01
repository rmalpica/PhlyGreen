"""Factory helpers for assembling a fully wired :class:`~PhlyGreen.Aircraft.Aircraft`.

The :class:`Aircraft` uses a mediator ("hub and spoke") pattern: every subsystem
holds a reference back to the aircraft, and the aircraft holds a reference to every
subsystem. Historically this two-way wiring was copy-pasted (~30 lines) into every
script and notebook::

    powertrain = pg.Systems.Powertrain.Powertrain(None)
    ...                                   # 9 more subsystems
    myaircraft = pg.Aircraft(powertrain, ...)
    powertrain.aircraft = myaircraft
    ...                                   # 9 more re-wirings

:func:`build_aircraft` does exactly that, once, in a single call.
"""

from .Aircraft import Aircraft
from . import Systems, Performance, Mission, Weight, Constraint, WellToWake, ClimateImpact


def build_aircraft():
    """Instantiate all subsystems and return a fully wired :class:`Aircraft`.

    Returns:
        Aircraft: an aircraft whose subsystems all reference it (and vice-versa),
        ready for ``ReadInput`` / ``DesignAircraft``.
    """
    powertrain = Systems.Powertrain.Powertrain(None)
    structures = Systems.Structures.Structures(None)
    aerodynamics = Systems.Aerodynamics.Aerodynamics(None)
    performance = Performance.Performance(None)
    mission = Mission.Mission(None)
    weight = Weight.Weight(None)
    constraint = Constraint.Constraint(None)
    welltowake = WellToWake.WellToWake(None)
    battery = Systems.Battery.Battery(None)
    climateimpact = ClimateImpact.ClimateImpact(None)

    aircraft = Aircraft(
        powertrain, structures, aerodynamics, performance, mission,
        weight, constraint, welltowake, battery, climateimpact,
    )

    # Wire each subsystem back to the mediator.
    for subsystem in (
        powertrain, structures, aerodynamics, performance, mission,
        weight, constraint, welltowake, battery, climateimpact,
    ):
        subsystem.aircraft = aircraft

    return aircraft
