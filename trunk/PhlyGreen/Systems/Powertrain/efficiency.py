"""Pluggable component-efficiency models.

Class-II powertrain models are, and will remain, *multiple and replaceable*: a component's
efficiency may be a constant, a response surface fitted to data, or the output of an
external code. They also depend on the operating point — altitude, velocity and power —
which must flow into the efficiencies used to assemble the powertrain
:mod:`~PhlyGreen.Systems.Powertrain.graph`.

This module provides that abstraction:

* :class:`OperatingPoint` — the flight condition a model is evaluated at.
* :class:`EfficiencyModel` — the common interface (``eta(op) -> float``).
* :class:`ConstantEfficiency` — a fixed value (the legacy default).
* :class:`CallableEfficiency` — wraps any ``fn(OperatingPoint) -> eta`` (e.g. an external
  code or a hand-written law).
* :class:`ResponseSurfaceEfficiency` — wraps a fitted surrogate (sklearn/joblib/pickle or
  any object with ``predict``), with a feature extractor mapping the operating point to the
  surrogate's inputs. Swap the model by swapping the artifact.
* :func:`make_efficiency_model` — builds the right model from a compact spec (a float, a
  callable, an :class:`EfficiencyModel`, or a dict).

Replacing a Class-II model is then a one-line config change, and adding a new kind of
surrogate means writing one small :class:`EfficiencyModel` subclass — nothing else changes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Callable, Sequence, Any, Dict


@dataclass
class OperatingPoint:
    """Condition at which a component efficiency is evaluated.

    Attributes:
        altitude: [m]; velocity: true airspeed [m/s]; power: shaft/electrical power [W].
        rpm, voltage: optional, for models that need them (e.g. electric motors).
        extras: any additional named quantities a bespoke model may consume.
    """
    altitude: float = 0.0
    velocity: float = 0.0
    power: float = 0.0
    rpm: Optional[float] = None
    voltage: Optional[float] = None
    extras: Dict[str, Any] = field(default_factory=dict)


class EfficiencyModel(ABC):
    """Common interface for a component efficiency model."""

    @abstractmethod
    def eta(self, op: OperatingPoint) -> float:
        """Return the efficiency (0, 1] at the given operating point."""

    def __call__(self, op: OperatingPoint) -> float:
        return self.eta(op)


class ConstantEfficiency(EfficiencyModel):
    """A fixed efficiency, independent of the operating point (legacy default)."""

    def __init__(self, value: float):
        self.value = value

    def eta(self, op: OperatingPoint) -> float:
        return self.value


class CallableEfficiency(EfficiencyModel):
    """Wrap any ``fn(OperatingPoint) -> eta`` (e.g. an external code or analytic law)."""

    def __init__(self, fn: Callable[[OperatingPoint], float]):
        self._fn = fn

    def eta(self, op: OperatingPoint) -> float:
        return float(self._fn(op))


class ResponseSurfaceEfficiency(EfficiencyModel):
    """Efficiency from a fitted surrogate (response surface) built from data/external codes.

    Args:
        predictor: anything with ``predict(X)`` returning an array (e.g. an sklearn model),
            or a plain callable ``predictor(*features) -> eta``.
        features: how to turn an :class:`OperatingPoint` into the surrogate's inputs —
            either a sequence of ``OperatingPoint`` attribute names (e.g.
            ``["altitude", "velocity", "power"]``) or a callable ``op -> list``.
        clip: optional ``(low, high)`` bounds applied to the prediction.
    """

    def __init__(self, predictor, features, clip=(0.0, 1.0)):
        self._predictor = predictor
        self._features = features
        self._clip = clip

    def _extract(self, op: OperatingPoint):
        if callable(self._features):
            return list(self._features(op))
        return [getattr(op, name) for name in self._features]

    def eta(self, op: OperatingPoint) -> float:
        x = self._extract(op)
        if hasattr(self._predictor, "predict"):
            value = float(self._predictor.predict([x])[0])
        else:
            value = float(self._predictor(*x))
        if self._clip is not None:
            lo, hi = self._clip
            value = min(max(value, lo), hi)
        return value

    @classmethod
    def from_file(cls, path, features, clip=(0.0, 1.0)):
        """Load a serialized surrogate (joblib first, then pickle) and wrap it."""
        try:
            import joblib
            predictor = joblib.load(path)
        except Exception:
            import pickle
            with open(path, "rb") as f:
                predictor = pickle.load(f)
        return cls(predictor, features, clip=clip)


class MotorEfficiencyModel(EfficiencyModel):
    """Class-II electric-motor efficiency from the d-q machine model in :mod:`.EM`.

    Wraps :class:`PhlyGreen.Systems.Powertrain.EM.ElectricMotor`, distributing the
    requested power over ``n_engines`` motors, converting power to torque at the operating
    rpm, and returning the solved efficiency. This is the canonical example of an
    operating-point-dependent Class-II efficiency feeding the powertrain graph.
    """

    def __init__(self, design_kw, design_v, design_rpm, n_engines=1):
        from .EM import ElectricMotor
        self.motor = ElectricMotor(design_kw, design_v, design_rpm)
        self.n_engines = n_engines

    def eta(self, op: OperatingPoint) -> float:
        import numpy as np
        rpm = op.rpm if op.rpm is not None else self.motor.design_specs["rpm"]
        safe_rpm = max(rpm, 100.0)
        omega = safe_rpm * 2 * np.pi / 60.0
        power_single = op.power / self.n_engines
        torque = power_single / omega
        return max(self.motor.solve_efficiency(safe_rpm, torque, op.voltage), 0.05)

    def weight(self):
        """Estimated mass of one motor [kg] (see ElectricMotor.get_weight)."""
        return self.motor.get_weight()


class GasTurbineEfficiencyModel(EfficiencyModel):
    """Class-II gas-turbine efficiency from the RBF response surface (:mod:`.gas_turbine_surrogate`).

    The gas turbine has a **fixed nominal (design) power** — it must be sized *before* the
    mission, not per operating point (an engine cannot resize itself instant by instant).
    ``eta`` then evaluates the (universal) response surface at the current load, i.e. the
    ratio of required to nominal power, accounting for the altitude power lapse.

    Args:
        design_power: nominal (rated) shaft power of the whole installation [W] — typically
            ``DesignPW * WTO``. Required.
        surrogate: a :class:`GasTurbineResponseSurface` (loaded by default).
        n_engines: number of engines the installation is split over.
    """

    def __init__(self, design_power, surrogate=None, n_engines=1):
        if design_power is None or design_power <= 0:
            raise ValueError(
                "GasTurbineEfficiencyModel needs a positive nominal 'design_power' [W] "
                "(size the engine before the mission, e.g. DesignPW * WTO).")
        if surrogate is None:
            from .gas_turbine_surrogate import GasTurbineResponseSurface
            surrogate = GasTurbineResponseSurface()
        self.surrogate = surrogate
        self.design_power = design_power
        self.n_engines = max(int(n_engines), 1)

    def eta(self, op: OperatingPoint) -> float:
        import PhlyGreen.Utilities.Units as Units
        import PhlyGreen.Utilities.Speed as Speed
        a = Speed.soundspeed(op.altitude, 0.0)
        mach = op.velocity / a if a > 0 else 0.0
        alt_ft = Units.mToft(op.altitude)
        design_hp = Units.wTohp(self.design_power) / self.n_engines   # per engine
        req_hp = Units.wTohp(op.power) / self.n_engines
        efficiency, _, _, _ = self.surrogate.predict(design_hp, alt_ft, mach, req_hp)
        return efficiency


class HamiltonPropellerEfficiency(EfficiencyModel):
    """Class-II propeller efficiency from the Hamilton-Standard model (:class:`.Propeller.Propeller`)."""

    def __init__(self, propeller):
        self.propeller = propeller

    def eta(self, op: OperatingPoint) -> float:
        e = self.propeller.ComputePropEfficiency(op.altitude, op.velocity, op.power)
        return float(min(max(e, 0.4), 1.0))


class PropellerSurrogateEfficiency(EfficiencyModel):
    """Class-II propeller efficiency from the RBF surrogate (:class:`.propeller_surrogate.PropellerSurrogate`).

    Solves the pitch governor for the target rpm, then evaluates the efficiency map.
    """

    def __init__(self, surrogate=None, rpm=1200.0, n_engines=1):
        if surrogate is None:
            import os
            from .propeller_surrogate import PropellerSurrogate
            csv = os.path.join(os.path.dirname(__file__), "data", "propeller_data_rbf.csv")
            surrogate = PropellerSurrogate(csv)
        self.surrogate = surrogate
        self.rpm = rpm
        self.n_engines = max(int(n_engines), 1)

    def eta(self, op: OperatingPoint) -> float:
        power_kw = (op.power / self.n_engines) / 1000.0
        rpm = op.rpm if op.rpm is not None else self.rpm
        pitch = self.surrogate.solve_pitch(power_kw, op.altitude, op.velocity, rpm)
        return float(self.surrogate.get_efficiency(power_kw, op.altitude, op.velocity, pitch, rpm))


def make_efficiency_model(spec) -> EfficiencyModel:
    """Build an :class:`EfficiencyModel` from a compact specification.

    Accepts:
        * an :class:`EfficiencyModel` (returned unchanged),
        * a number -> :class:`ConstantEfficiency`,
        * a callable -> :class:`CallableEfficiency`,
        * a dict ``{"type": "constant"|"response_surface", ...}``.
    """
    if isinstance(spec, EfficiencyModel):
        return spec
    if isinstance(spec, (int, float)):
        return ConstantEfficiency(float(spec))
    if callable(spec):
        return CallableEfficiency(spec)
    if isinstance(spec, dict):
        kind = spec.get("type", "constant")
        if kind == "constant":
            return ConstantEfficiency(float(spec["value"]))
        if kind == "response_surface":
            features = spec["features"]
            clip = tuple(spec.get("clip", (0.0, 1.0)))
            if "path" in spec:
                return ResponseSurfaceEfficiency.from_file(spec["path"], features, clip=clip)
            return ResponseSurfaceEfficiency(spec["predictor"], features, clip=clip)
        raise ValueError(f"Unknown efficiency model type: {kind!r}")
    raise TypeError(f"Cannot build an EfficiencyModel from {spec!r}")


class TurbofanEfficiencyModel(EfficiencyModel):
    """Overall efficiency of a turbofan from the fitted response surface.

    The powertrain graph normalises everything to propulsive power ``Pp = F*V``, so a
    turbofan is one node: ``eta_o = F*V / (mdot_f * LHV)``. That makes the graph's fuel
    ratio ``Pf/Pp = 1/eta_o`` exactly a TSFC closure, since ``TSFC = V/(eta_o * LHV)`` --
    the two carry the same information, and splitting eta_o into thermal x propulsive would
    multiply back to the same number.

    Like :class:`GasTurbineEfficiencyModel`, the engine has a **fixed nominal rating** chosen
    before the mission -- here the sea-level-static thrust, since a turbofan is thrust-rated.
    ``eta`` converts the operating point's propulsive power back to a thrust, ``F = P/V``,
    and reads the map at the resulting thrust fraction.

    Args:
        design_thrust: nominal SLS thrust of the whole installation [N]. Required.
        surrogate: a :class:`TurbofanResponseSurface` (loaded by default).
        n_engines: number of engines the installation is split over.
    """

    def __init__(self, design_thrust, surrogate=None, n_engines=1):
        if design_thrust is None or design_thrust <= 0:
            raise ValueError(
                "TurbofanEfficiencyModel needs a positive nominal 'design_thrust' [N] "
                "(size the engine before the mission, e.g. DesignTW * WTO).")
        if surrogate is None:
            from .turbofan_surrogate import TurbofanResponseSurface
            surrogate = TurbofanResponseSurface()
        self.surrogate = surrogate
        self.design_thrust = design_thrust
        self.n_engines = max(int(n_engines), 1)

    def eta(self, op: OperatingPoint) -> float:
        import PhlyGreen.Utilities.Units as Units
        import PhlyGreen.Utilities.Speed as Speed
        if op.velocity is None or op.velocity <= 0.0:
            # F = P/V is singular at rest, and so is the whole propulsive-power formulation:
            # a static engine produces thrust at zero propulsive power. Every PhlyGreen call
            # site evaluates at a positive flight speed (Performance rejects Mach <= 0), so
            # reaching here means the caller asked for something the model cannot represent.
            raise ValueError(
                "TurbofanEfficiencyModel needs a positive velocity: overall efficiency is "
                "F*V/(mdot_f*LHV), which is identically zero at rest. Evaluate the turbofan "
                "at a flight condition (take-off is evaluated at V2, not at V=0).")
        a = Speed.soundspeed(op.altitude, 0.0)
        mach = op.velocity / a if a > 0 else 0.0
        thrust = op.power / op.velocity                      # total, all engines [N]
        efficiency, _, _, _ = self.surrogate.predict(
            self.design_thrust, Units.mToft(op.altitude), mach, thrust)
        return efficiency

    def tsfc(self, op: OperatingPoint, lhv):
        """Thrust-specific fuel consumption [kg/(N s)] at the operating point.

        Reported rather than solved with: the mission integrates on eta_o. Provided so
        results are comparable with published engine data.
        """
        return op.velocity / (self.eta(op) * lhv)
