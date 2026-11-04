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
    "02b_serial_hybrid.py",
    "03_typed_config_and_results.py",
    "04_flight_profile_and_custom_segment.py",
    "05_powertrain_graph_and_efficiency_models.py",
    "06_utilities_atmosphere_and_speeds.py",
    "14_welltowake_and_climate.py",
    "15_class_i_vs_class_ii.py",
    "18_serial_range_extender_gt.py",
    "20_hydrogen_fuel_cell.py",
    "28_reference_atr42.py",
]


# The turbofan example needs the fitted engine map, which is generated offline by
# Systems/Powertrain/data/HBTF_turbofan.py (pyCycle). Run it only when that artifact exists.
_TURBOFAN_MAP = os.path.join(TRUNK, "PhlyGreen", "Systems", "Powertrain", "data",
                             "Turbofan_Engine_Model.pkl")


@pytest.mark.slow
@pytest.mark.skipif(not os.path.isfile(_TURBOFAN_MAP),
                    reason="turbofan engine map not built (see HBTF_turbofan.py)")
def test_turbofan_example_runs():
    proc = subprocess.run([sys.executable, os.path.join("examples", "26_turbofan_design.py")],
                          cwd=TRUNK, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, f"26_turbofan_design.py failed:\n{proc.stderr[-2000:]}"


@pytest.mark.slow
@pytest.mark.skipif(not os.path.isfile(_TURBOFAN_MAP),
                    reason="turbofan engine map not built (see HBTF_turbofan.py)")
def test_a320_reference_example_runs():
    proc = subprocess.run([sys.executable, os.path.join("examples", "29_reference_a320.py")],
                          cwd=TRUNK, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, f"29_reference_a320.py failed:\n{proc.stderr[-2000:]}"


@pytest.mark.slow
@pytest.mark.skipif(not __import__("PhlyGreen").Systems.Thermal.coolprop_available(),
                    reason="CoolProp not installed")
def test_tms_class_ii_example_runs():
    # two full designs, one with the geometric Class-II TMS (~1.5 min)
    proc = subprocess.run([sys.executable, os.path.join("examples", "27_hydrogen_tms_class_ii.py")],
                          cwd=TRUNK, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, f"27_hydrogen_tms_class_ii.py failed:\n{proc.stderr[-2000:]}"


@pytest.mark.slow
def test_off_design_example_runs():
    # two designs and ~80 off-design missions (~3.5 min)
    proc = subprocess.run([sys.executable, os.path.join("examples", "30_off_design_mission.py")],
                          cwd=TRUNK, capture_output=True, text=True, timeout=600)
    assert proc.returncode == 0, f"30_off_design_mission.py failed:\n{proc.stderr[-2000:]}"


@pytest.mark.slow
@pytest.mark.parametrize("script", FAST_EXAMPLES)
def test_example_runs(script):
    path = os.path.join("examples", script)
    proc = subprocess.run([sys.executable, path], cwd=TRUNK,
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, f"{script} failed:\n{proc.stderr[-2000:]}"
