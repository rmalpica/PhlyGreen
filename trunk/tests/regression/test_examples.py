"""Smoke tests: the example scripts run without error.

Keeps the student-facing examples honest as the code evolves. Only the fast examples are
run here (each is a full design or two); the heavier outer-loop examples are exercised
manually.
"""

import os
import subprocess
import sys

import pytest

TRUNK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FAST_EXAMPLES = [
    "01_design_traditional.py",
    "03_typed_config_and_results.py",
    "04_flight_profile_and_custom_segment.py",
    "05_powertrain_graph_and_efficiency_models.py",
    "06_utilities_atmosphere_and_speeds.py",
    "14_welltowake_and_climate.py",
    "15_class_i_vs_class_ii.py",
    "20_hydrogen_fuel_cell.py",
]


@pytest.mark.slow
@pytest.mark.parametrize("script", FAST_EXAMPLES)
def test_example_runs(script):
    path = os.path.join("examples", script)
    proc = subprocess.run([sys.executable, path], cwd=TRUNK,
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, f"{script} failed:\n{proc.stderr[-2000:]}"
