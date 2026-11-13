"""Off-design mission helper (examples/30_off_design_mission.py).

Flying the design mission off-design, with the design phi schedule, must reproduce the design:
same take-off mass, same fuel load, and (energy-sized Class-I pack) the whole usable battery.
"""
import importlib.util
import os
import sys

import pytest

TRUNK = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXAMPLES = os.path.join(TRUNK, "examples")


@pytest.fixture(scope="module")
def ex30():
    sys.path.insert(0, EXAMPLES)
    spec = importlib.util.spec_from_file_location("ex30", os.path.join(EXAMPLES, "30_off_design_mission.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def gt_hybrid(ex30):
    return ex30.gt_hybrid_design()


@pytest.mark.slow
def test_design_mission_reproduces_design(ex30, gt_hybrid):
    w = gt_hybrid.weight
    r = ex30.fly_off_design(gt_hybrid, gt_hybrid.MissionInput["Range Mission"])
    assert r.feasible, r.violations
    assert r.WTO == pytest.approx(w.WTO, abs=1.0)
    assert r.fuel_load == pytest.approx(w.Wf, rel=1e-6)
    assert r.battery_soc_used == pytest.approx(1.0, rel=1e-6)     # energy-sized pack
    assert 0.0 < r.trip_fuel < r.fuel_load                         # diversion carried, not flown


@pytest.mark.slow
def test_shorter_mission_and_limits(ex30, gt_hybrid):
    w = gt_hybrid.weight
    short = ex30.fly_off_design(gt_hybrid, 300.0)
    assert short.feasible and short.WTO < w.WTO and short.fuel_load < w.Wf
    assert gt_hybrid.MissionInput["Range Mission"] == 750                # input not mutated
    # all-electric cruise at the design range empties the pack beyond its capacity
    over = ex30.fly_off_design(gt_hybrid, 750.0, phi={"Cruise": 1.0})
    assert not over.feasible and any("battery energy" in v for v in over.violations)
    with pytest.raises(ValueError, match="shorter than its climbs and descents"):
        ex30.fly_off_design(gt_hybrid, 150.0)


@pytest.mark.slow
def test_wing_area_and_empty_mass_frozen(ex30, gt_hybrid):
    """Off-design, the wing area and the empty mass are the design ones (not the wing loading):
    re-flying the converged take-off mass on the design wing reproduces the fuel load."""
    import copy
    w = gt_hybrid.weight
    r = ex30.fly_off_design(gt_hybrid, 300.0)
    oew = w.WTO - w.Wf - w.final_reserve - w.WPayload - w.WCrew
    assert oew + w.WCrew == pytest.approx(gt_hybrid.results().empty_weight, abs=0.1)
    assert r.WTO == pytest.approx(oew + w.WPayload + w.WCrew + r.fuel_load + w.final_reserve,
                                  abs=1e-6)

    def fuel_at(wing_loading):
        a = copy.deepcopy(gt_hybrid)
        a.MissionInput["Range Mission"] = 300.0
        a.mission.InitializeProfile()
        a.DesignWTOoS = wing_loading
        out = a.mission.EvaluateMission(r.WTO)
        return (out[0] if isinstance(out, tuple) else out) / a.mission.ef

    S = gt_hybrid.WingSurface
    assert r.WTO * 9.81 / S < gt_hybrid.DesignWTOoS               # lighter aircraft, same wing
    assert r.fuel_load == pytest.approx(fuel_at(r.WTO * 9.81 / S), abs=1.0)
    # the design wing loading (a wing shrunk with WTO) gives a different fuel load
    assert abs(fuel_at(gt_hybrid.DesignWTOoS) - r.fuel_load) > 2.0
