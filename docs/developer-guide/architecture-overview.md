# Architecture Overview

This page describes how PhlyGreen is put together, so you can find your way around and
extend it. It reflects the current (restructured) code.

## The mediator object graph

`Aircraft` (`PhlyGreen/Aircraft.py`) is a central **mediator**: it holds every subsystem
(`powertrain`, `structures`, `aerodynamics`, `performance`, `mission`, `weight`,
`constraint`, `welltowake`, `battery`, `climateimpact`, and the optional `fuelcell` /
`tank`), and each subsystem holds a back-reference to the aircraft. Any subsystem reaches
another through `self.aircraft.<subsystem>`.

You rarely wire this by hand: **`pg.build_aircraft()`** (`PhlyGreen/factory.py`) constructs
all subsystems and cross-links them, returning a ready aircraft.

```python
import PhlyGreen as pg
aircraft = pg.build_aircraft()
```

## Typed configuration and structured results

Inputs are typed, validated dataclasses in **`PhlyGreen/config/`** rather than loose dicts:
`AircraftConfig` bundles the flags (`configuration`, `hybrid_type`, `aircraft_type`,
`weight_class`) with the sections `MissionConfig`, `EnergyConfig`, `AerodynamicsConfig`,
`ConstraintsConfig`, `StagesConfig` (flight profile), and the optional `CellConfig`,
`WellToTankConfig`, `ClimateImpactConfig`, `TankConfig`. Every section has
`to_dict`/`from_dict`, and `Aircraft.ReadInput` accepts either config objects or the legacy
dicts, so old notebooks keep working.

```python
from examples.common import traditional_config      # a baseline AircraftConfig
aircraft.configure(traditional_config())             # validate + size
results = aircraft.results()                          # AircraftResults dataclass
```

`aircraft.results()` returns an **`AircraftResults`** dataclass (`PhlyGreen/results.py`)
instead of only printing — convenient for tests, serialization and outer loops.

## Sizing flow

`Aircraft.configure` / `DesignAircraft` run: `ReadInput` → `constraint.FindDesignPoint()`
(picks `DesignPW`, `DesignWTOoS` from the constraint diagram) → `weight.WeightEstimation()`.
Because component masses depend on the mission, which depends on take-off weight, the weight
estimate is an iterative **WTO convergence loop** solved with Brent's method
(`PhlyGreen/Weight/Weight.py`). `Mission` integrates the energy use over the profile and
`Weight` turns it into masses. The configuration selects the path:

| `Configuration`   | Mission method                       | Weight method        |
|-------------------|--------------------------------------|----------------------|
| `Traditional`     | `TraditionalConfiguration`           | `Traditional`        |
| `Hybrid`          | `HybridConfigurationClassI/II`       | `Hybrid`             |
| `Hydrogen`        | `HydrogenConfiguration`              | `Hydrogen`           |
| `FuelCellBattery` | `FuelCellBatteryConfiguration`       | `FuelCellBattery`    |

## Mission profile (segment registry)

`Mission/Profile.py` builds the altitude/velocity/vertical-rate/φ(t) timeline from a
sequence of **segments**. Segment types live in a registry in `Mission/segments.py`; add a
new flight-segment kind by subclassing `FlightSegment` and decorating it with
`@register_segment("Name")` — nothing else changes. (The legacy monolithic profile is retained
only as the numerical reference for the equivalence tests, at
`tests/_reference/Profile_legacy.py`, outside the shipped package.)

## Powertrain: component graph + efficiency models

The powertrain power balance is assembled as a **component graph**
(`Systems/Powertrain/graph.py`): architectures are composed from `converter`/`combiner`/
`split`/`sink` primitives and solved as one linear system, instead of hand-coded matrices.
Each component's efficiency is an **`EfficiencyModel`** (`Systems/Powertrain/efficiency.py`)
— Class-I (`ConstantEfficiency`) or Class-II (operating-point dependent), e.g.
`GasTurbineEfficiencyModel` (RBF response surface), `HamiltonPropellerEfficiency` /
`PropellerSurrogateEfficiency`, and `MotorEfficiencyModel` (d-q model). `Powertrain.eta(component, alt, vel, pwr)`
evaluates them; `Powertrain.Traditional/Hybrid/PowerRatioFuelCellBattery` feed the results
to the graph. See the [Powertrain user guide](../user-guide/powertrain.md).

## Hydrogen, tank and thermal

- `Systems/FuelCell/FuelCell.py` — physics fuel-cell model (Kulikovsky polarization, stack
  sizing, `ComputePRatio`).
- `Systems/Tank/` — cryogenic LH2 tank: structural + MLI sizing and a transient `time_step`
  state model (self-pressurization, venting, heater). Optional (needs CoolProp).
- `Systems/Thermal/` — a scaffold for a future heat-exchanger-network module
  (`HeatSource`/`HeatSink`/`HeatExchangerNetwork`).

## Outer-loop API and post-processing

`PhlyGreen/api.py` exposes `run_design(config) -> AircraftResults` (a pure function, fresh
aircraft per call) and `evaluate(base_config, apply, x)` for optimization / UQ / sweeps.
`PhlyGreen/postprocess.py` extracts mission time-series and plots the flight profile, energy
traces, constraint diagram, mass breakdown and tank state.

## Where to look

- Worked scripts: `trunk/examples/` (capability tour + outer-loop apps).
- Narrative notebooks: `trunk/notebooks/` (traditional/hybrid/fuel-cell/FC+battery).
- Tests: `trunk/tests/` (`unit/` + `regression/`, with golden-master design baselines).
