"""End-to-end equivalence: designing via the typed config path equals the dict path.

Proves the adapter shim is behavior-preserving: an AircraftConfig fed through
``aircraft.configure(...)`` produces the same results as the legacy dict-based
``DesignAircraft`` (which the golden-master tests pin), within numerical tolerance.
"""

import pytest

import PhlyGreen as pg
import _sample_configs as sc

REL_TOL = 1e-9
FIELDS = ["WTO", "Wf", "WStructure", "WPT", "WBat", "WingSurface", "SourceEnergy"]


def _compare(a, b):
    da, db = a.to_dict(), b.to_dict()
    for key in FIELDS:
        va, vb = da.get(key), db.get(key)
        if va is None and vb is None:
            continue
        assert va == pytest.approx(vb, rel=REL_TOL), f"{key}: config={va!r} dict={vb!r}"


@pytest.mark.slow
def test_hybrid_config_path_matches_dict_path():
    config = sc.hybrid_parallel_aircraft_config()
    via_config = pg.build_aircraft().configure(config).results()

    from conftest import design_from_config
    via_dict = design_from_config(*sc.hybrid_parallel_config()).results()

    _compare(via_config, via_dict)


@pytest.mark.slow
def test_traditional_config_path_matches_dict_path():
    config = sc.traditional_aircraft_config()
    via_config = pg.build_aircraft().configure(config).results()

    from conftest import design_from_config
    via_dict = design_from_config(*sc.traditional_config()).results()

    _compare(via_config, via_dict)
