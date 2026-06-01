"""Unit tests for the build_aircraft() factory and AircraftResults wiring.

Fast: these do not run a design, only check the object graph is assembled correctly.
"""

import PhlyGreen as pg
from PhlyGreen.results import AircraftResults


SUBSYSTEMS = [
    'powertrain', 'structures', 'aerodynamics', 'performance', 'mission',
    'weight', 'constraint', 'welltowake', 'battery', 'climateimpact',
]


def test_factory_returns_aircraft():
    assert isinstance(pg.build_aircraft(), pg.Aircraft)


def test_all_subsystems_present():
    aircraft = pg.build_aircraft()
    for name in SUBSYSTEMS:
        assert getattr(aircraft, name) is not None, f"missing subsystem {name}"


def test_mediator_wiring_is_bidirectional():
    aircraft = pg.build_aircraft()
    for name in SUBSYSTEMS:
        subsystem = getattr(aircraft, name)
        assert subsystem.aircraft is aircraft, f"{name} not wired back to aircraft"


def test_each_build_is_independent():
    a1 = pg.build_aircraft()
    a2 = pg.build_aircraft()
    assert a1 is not a2
    assert a1.mission is not a2.mission


def test_results_dataclass_on_undesigned_aircraft_is_empty():
    # from_aircraft must be defensive: an undesigned aircraft yields all-None scalars.
    results = AircraftResults.from_aircraft(pg.build_aircraft())
    assert results.WTO is None
    assert isinstance(results.to_dict(), dict)
