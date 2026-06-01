"""Unit tests for the pluggable efficiency-model framework."""

import pytest

from PhlyGreen.Systems.Powertrain.efficiency import (
    OperatingPoint, EfficiencyModel, ConstantEfficiency, CallableEfficiency,
    ResponseSurfaceEfficiency, MotorEfficiencyModel, make_efficiency_model,
)


def test_constant_efficiency_ignores_operating_point():
    m = ConstantEfficiency(0.95)
    assert m.eta(OperatingPoint(altitude=0)) == 0.95
    assert m.eta(OperatingPoint(altitude=9000, power=1e6)) == 0.95
    assert m(OperatingPoint()) == 0.95  # __call__ shortcut


def test_callable_efficiency_depends_on_operating_point():
    m = CallableEfficiency(lambda op: 0.9 - 1e-8 * op.power)
    assert m.eta(OperatingPoint(power=0)) == pytest.approx(0.9)
    assert m.eta(OperatingPoint(power=1e6)) < 0.9


def test_response_surface_with_callable_predictor_and_clip():
    # predictor receives the extracted features as positional args
    m = ResponseSurfaceEfficiency(lambda alt, v, p: 0.5 + 1e-5 * v,
                                  features=["altitude", "velocity", "power"])
    assert m.eta(OperatingPoint(velocity=100)) == pytest.approx(0.501)
    # clip keeps the value in [0, 1]
    hot = ResponseSurfaceEfficiency(lambda v: 5.0, features=["velocity"], clip=(0.0, 1.0))
    assert hot.eta(OperatingPoint(velocity=1)) == 1.0


def test_response_surface_with_sklearn_like_predictor():
    class FakeModel:
        def predict(self, X):
            return [0.8 for _ in X]
    m = ResponseSurfaceEfficiency(FakeModel(), features=["altitude", "power"])
    assert m.eta(OperatingPoint(altitude=8000, power=1e6)) == pytest.approx(0.8)


@pytest.mark.parametrize("spec,expected", [
    (0.92, 0.92),
    ({"type": "constant", "value": 0.88}, 0.88),
])
def test_make_efficiency_model_constant_specs(spec, expected):
    assert make_efficiency_model(spec).eta(OperatingPoint()) == expected


def test_make_efficiency_model_passthrough_and_callable():
    existing = ConstantEfficiency(0.5)
    assert make_efficiency_model(existing) is existing
    m = make_efficiency_model(lambda op: 0.7)
    assert isinstance(m, CallableEfficiency)
    assert m.eta(OperatingPoint()) == 0.7


def test_make_efficiency_model_rejects_garbage():
    with pytest.raises(TypeError):
        make_efficiency_model("not a spec")


# --- Class-II electric motor (d-q model) ------------------------------------

def test_motor_efficiency_in_range_and_power_dependent():
    m = MotorEfficiencyModel(design_kw=1000, design_v=800, design_rpm=3000)
    eta_low = m.eta(OperatingPoint(power=200e3, rpm=3000))
    eta_high = m.eta(OperatingPoint(power=1000e3, rpm=3000))
    for e in (eta_low, eta_high):
        assert 0.0 < e <= 1.0
    # efficiency varies with load -> genuinely operating-point dependent
    assert eta_low != pytest.approx(eta_high)


def test_motor_weight_positive():
    m = MotorEfficiencyModel(design_kw=1000, design_v=800, design_rpm=3000)
    assert m.weight() > 0
