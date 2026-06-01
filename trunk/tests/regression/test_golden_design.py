"""Golden-master regression tests.

Run the full design for the canonical configurations and assert the key scalar outputs
match the frozen baselines in ``golden/``. This is the safety net for later refactors
(profile, powertrain, typed I/O): any unintended change to the numerics fails here.

Regenerate the baselines with ``python tests/regression/_generate_golden.py`` only when
a change is *meant* to alter results, and review the diff.
"""

import json
import os

import pytest

import _sample_configs as sc
from conftest import design_from_config

GOLDEN_DIR = os.path.join(os.path.dirname(__file__), "golden")

# Quantities checked against the baseline, with relative tolerance. Deterministic solvers
# (scipy brentq / solve_ivp) make these reproducible; tolerance absorbs harmless op-reordering.
KEY_FIELDS = [
    "WTO", "Wf", "block_fuel", "WStructure", "WPT", "WingSurface",
    "empty_weight", "zero_fuel_weight", "TO_PP", "Max_PEng", "engineRating",
]
HYBRID_FIELDS = ["WBat", "SourceEnergy", "Psi", "pack_energy", "pack_power_max"]

REL_TOL = 1e-4


def _load_golden(name):
    with open(os.path.join(GOLDEN_DIR, f"{name}.json")) as f:
        return json.load(f)


def _compare(results, golden, fields):
    mismatches = []
    for key in fields:
        expected = golden.get(key)
        actual = results.get(key)
        if expected is None:
            continue
        if actual != pytest.approx(expected, rel=REL_TOL):
            mismatches.append(f"{key}: got {actual!r}, expected {expected!r}")
    assert not mismatches, "regression vs golden master:\n  " + "\n  ".join(mismatches)


@pytest.mark.slow
def test_traditional_matches_golden():
    aircraft = design_from_config(*sc.traditional_config())
    results = aircraft.results().to_dict()
    golden = _load_golden("traditional_atr")
    _compare(results, golden, KEY_FIELDS)


@pytest.mark.slow
def test_hybrid_parallel_matches_golden():
    aircraft = design_from_config(*sc.hybrid_parallel_config())
    results = aircraft.results().to_dict()
    golden = _load_golden("hybrid_parallel_atr")
    _compare(results, golden, KEY_FIELDS + HYBRID_FIELDS)
