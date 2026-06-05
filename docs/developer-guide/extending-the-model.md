# Extending the Model

PhlyGreen is built around a few **extension points** so the common additions — a new flight
segment, a new powertrain architecture, a new efficiency model, a new input — are local changes that
the rest of the code picks up automatically. This page shows the idiomatic pattern for each, and the
golden‑master safety net that protects you while you do it.

---

## 1. Add a flight segment

Segments live in a registry (`Mission/segments.py`). Subclass `FlightSegment`, implement
`compute(...)`, and decorate with `@register_segment("Name")` — the profile builder, the config layer
and the mission integrator all find it by name, so **nothing else changes**.

```python
from PhlyGreen.Mission.segments import FlightSegment, SegmentResult, register_segment, CLIMB

@register_segment("ConstantRateClimbToMach")
class ConstantRateClimbToMachSegment(FlightSegment):
    category = CLIMB                                   # CLIMB / CRUISE / DESCENT (segment ordering)

    def compute(self, phase_range, distance_so_far):
        start = self.inputs["StartAltitude"]           # self.inputs is the stage 'input' dict
        end   = self.inputs["EndAltitude"]
        v     = self.inputs["Speed"]
        rate  = self.inputs["CB"] * v
        dt    = abs((end - start) / rate)
        return SegmentResult(start_altitude=start, vertical_rate=rate, velocity=v,
                             duration=dt, distance=v * dt, category=self.category)
```

Use it by setting `'type': 'ConstantRateClimbToMach'` on a stage. `Profile_legacy.py` is **not** an
extension point — it's frozen as the numerical reference for the equivalence tests.

---

## 2. Add a powertrain architecture

Architectures are assembled by the **component graph** (`Systems/Powertrain/graph.py`) from four
primitives — `converter` (one efficiency edge), `combiner` (sum inputs through one efficiency),
`split` (hybridisation fraction φ) and `sink` (the unit propulsive load) — and solved as a single
linear system. Write a builder that composes them; no matrix algebra:

```python
from PhlyGreen.Systems.Powertrain.graph import PowertrainGraph

def my_architecture_graph(eta_a, eta_b, eta_pp, phi):
    g = PowertrainGraph(["Pf", "Pa", "Pp", "Pbat"])
    g.converter("Pf", "Pa", eta_a)     # source -> stage A
    g.converter("Pa", "Pp", eta_pp)    # stage A -> propulsive
    g.split("Pf", "Pbat", phi)         # battery takes a fraction phi of the load
    g.sink("Pp", 1.0)                  # normalise to unit propulsive power
    return g

sol = my_architecture_graph(0.40, 0.98, 0.85, phi=0.3).solution()  # {'Pf':…, 'Pbat':…}
```

Then expose it from `Powertrain` (a `PowerRatio…` method that maps the solution onto the
`PRatio` indices Mission/Weight consume: `[0]`=fuel, `[1]`=gas‑turbine shaft, `[5]`=battery) and add
the matching `Mission.*Configuration` / `Weight.*` methods, wired to a new `Configuration` flag value.
See `fuelcell_battery_graph` + `PowerRatioFuelCellBattery` as the worked example. The
`_traditional_legacy`/`_hybrid_legacy` solvers are reference‑only.

---

## 3. Add / swap a component efficiency model

Every component efficiency is an `EfficiencyModel` (`Systems/Powertrain/efficiency.py`) evaluated at
an `OperatingPoint(altitude, velocity, power, rpm)`. To inject custom physics, implement `eta`:

```python
from PhlyGreen.Systems.Powertrain.efficiency import EfficiencyModel, OperatingPoint

class MyMotorEfficiency(EfficiencyModel):
    def eta(self, op: OperatingPoint) -> float:
        return 0.97 - 2e-9 * op.power            # any law of the operating point
```

You usually don't even need a class: `make_efficiency_model(spec)` builds the right model from a
**float** (`ConstantEfficiency`, the Class‑I default), a **callable** `fn(op) -> eta`
(`CallableEfficiency` — wrap an external code), or a **dict** describing a fitted response surface
(`ResponseSurfaceEfficiency`, via `.predict` / `from_file`). The packaged Class‑II examples
(`GasTurbineEfficiencyModel`, `MotorEfficiencyModel`, propeller models) are wired into the graph
through `Powertrain.eta(component, alt, vel, pwr)`, so a Class‑I → Class‑II swap never touches the
solver. See [Surrogate Models](../user-guide/surrogate-models.md) for the response‑surface format and
its offline trainers.

---

## 4. Add an input field

Inputs are typed dataclasses in `config/sections.py` (each subclasses `DictConfig`). Add the Python
field and its legacy‑dict key to the section's `_KEY_MAP`, so `to_dict`/`from_dict` round‑trip it and
both the typed and legacy APIs see it:

```python
@dataclass
class EnergyConfig(DictConfig):
    my_new_knob: Optional[float] = None
    _KEY_MAP = { ..., "my_new_knob": "My New Knob" }   # -> EnergyInput['My New Knob']
```

Then read it in the consuming subsystem's `SetInput()` (`self.aircraft.<...>Input.get("My New Knob")`).
Keep new fields **optional with a `None`/legacy default** so existing configs and the golden masters
are unaffected.

---

## 5. Don't break the golden masters

The regression suite pins the design outputs of the canonical configs
(`tests/regression/golden/*.json`). Run it before and after your change:

```bash
cd trunk && pytest -m "not slow"      # fast unit tests
cd trunk && pytest                    # full suite incl. golden-master regression
```

If your change is **not** meant to alter results, the golden masters must stay green. If it *is*
(e.g. a new default model), regenerate them deliberately and review the diff:

```bash
python tests/regression/_generate_golden.py
```

Add a unit test for the new behaviour and, where it makes sense, an **equivalence test** against the
reference implementation (as the segment registry and the component graph do against their
`*_legacy` counterparts).

---

## Checklist

| Adding… | Touch | Pattern |
|---------|-------|---------|
| flight segment | `Mission/segments.py` | `@register_segment` subclass |
| architecture | `Systems/Powertrain/graph.py` + `Powertrain` + `Mission`/`Weight` | compose primitives + `Configuration` flag |
| efficiency model | `Systems/Powertrain/efficiency.py` | `EfficiencyModel` / `make_efficiency_model` |
| input field | `config/sections.py` + subsystem `SetInput()` | dataclass field + `_KEY_MAP`, optional default |
