# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

PhlyGreen is a Python toolkit for preliminary design / sizing of novel (hybrid-electric) aircraft
concepts, developed at Sapienza University of Rome. Given a mission profile and design constraints,
it sizes each aircraft subsystem so the vehicle can fly the mission within all constraints.

## Repository layout

The installable package lives in `trunk/PhlyGreen/`, **not** the repo root. Key paths:

- `trunk/PhlyGreen/` — the `PhlyGreen` package (the actual code).
- `trunk/tutorial/` — Jupyter notebooks + scripts showing real usage (`tutorial.ipynb`,
  `ATR42.ipynb`, `DO228.ipynb`, `battery-demo.ipynb`, `tutorial_WtW.ipynb`).
- `trunk/examples/` — student-facing, well-commented scripts (capability tour + outer-loop
  apps). Start at `examples/README.md`; `examples/common.py` holds baseline configs.
- `trunk/Validation/`, `trunk/playground/` — validation sweeps and experimental scripts.
- `docs/` + `mkdocs.yml` — MkDocs site (published via GitHub Pages on push to `main`).
- `to_be_merged/`, `misc/`, `trunk/JofAircraft/` — unmerged forks (e.g. H2, advanced propeller
  models) and legacy code. **Not** part of the main package; do not edit unless asked.

## Setup & commands

```bash
pip install -e ./trunk          # editable install of the PhlyGreen package
pip install -r requirements.txt # numpy, scipy, joblib, scikit-learn, matplotlib, ipykernel
pip install -r requirements-dev.txt  # pytest, pytest-cov (for the test suite)
```

There is a dedicated conda env `phlygreen` (Python 3.12) with the package installed
editable. Run tests from `trunk/`:

```bash
cd trunk
pytest                 # full suite (unit + slow regression)
pytest -m "not slow"   # fast unit tests only
```

Notebooks/scripts under `trunk/tutorial/` import the package with `sys.path.insert(0, '../')`,
so they assume the working directory is `trunk/`. Prefer `pip install -e ./trunk` so imports work
from anywhere.

Docs (run from repo root, uses `mkdocs.yml`):

```bash
mkdocs serve   # live preview
mkdocs build   # build static site
```

The test suite lives in `trunk/tests/` (`unit/` + `regression/`, pytest). The
**golden-master** regression tests (`tests/regression/golden/*.json`) pin the design
outputs of canonical configs and are the safety net for refactors — regenerate them with
`python tests/regression/_generate_golden.py` only when a change is *meant* to alter
results. CI (`.github/workflows/deploy.yml`) currently only runs `mkdocs build`.

## Architecture

### Mediator (hub-and-spoke) object graph
`Aircraft` (`trunk/PhlyGreen/Aircraft.py`) is a central mediator. Each subsystem holds a reference
to the `Aircraft`, and the `Aircraft` holds a reference to each subsystem, so any module reads
another module's data/methods via `self.aircraft.<subsystem>`. Subsystems:
`powertrain, structures, aerodynamics, performance, mission, weight, constraint, welltowake,
battery, climateimpact`.

Wiring is done by hand (see `trunk/tutorial/tutorial.ipynb`): each subsystem is constructed with
`None`, the `Aircraft` is built from all of them, then each subsystem's `.aircraft` attribute is
assigned back. When adding a subsystem, replicate this two-way wiring — or just call
**`pg.build_aircraft()`** (`PhlyGreen/factory.py`), which does all of it and returns a ready
aircraft.

**Typed config & results (preferred new API).** `PhlyGreen/config/` provides typed, validated
dataclasses (`AircraftConfig` bundling `MissionConfig`, `EnergyConfig`, `CellConfig`,
`AerodynamicsConfig`, `ConstraintsConfig`, `StagesConfig`, …) that replace the loose input dicts.
`aircraft.configure(AircraftConfig)` runs the design; `aircraft.results()` returns an
`AircraftResults` dataclass (`PhlyGreen/results.py`) instead of only printing. The legacy dict API
still works: `ReadInput` accepts either dicts or config objects (each config has
`to_dict`/`from_dict`), so existing notebooks are unaffected.

**Outer-loop API (optimization / UQ / sweeps).** `PhlyGreen/api.py` exposes
`pg.run_design(config) -> AircraftResults` (a pure function: fresh aircraft per call, input
never mutated) and `pg.evaluate(base_config, apply, x)` (apply parameters `x` to a copy of
the baseline, then design). These are the building blocks for the `examples/` outer-loop
scripts and are safe to call in a loop or in parallel.

### Input model
The model is configured entirely through nested dictionaries passed to
`Aircraft.ReadInput(...)` / `Aircraft.DesignAircraft(...)`:
`AerodynamicsInput, ConstraintsInput, MissionInput, EnergyInput, MissionStages, DiversionStages`
(required) and `LoiterStages, WellToTankInput, CellInput, ClimateImpactInput, PropellerInput`
(optional). `MissionStages`/`DiversionStages` are ordered dicts of flight segments, each with a
`type` (e.g. `ConstantRateClimb`, `ConstantMachCruise`, `ConstantRateDescent`), an `input` block,
and a `Supplied Power Ratio` (`phi`) block. `ReadInput` stores each dict on the `Aircraft` and
calls `SetInput()` on every subsystem — so every subsystem follows a `SetInput()` convention that
pulls its parameters from `self.aircraft.<...>Input`.

**Profile / segment types.** `Mission.Profile` (`PhlyGreen/Mission/Profile.py`) builds the
altitude/velocity/vertical-rate/phi(t) timeline from those stage dicts. Segment types live in
`PhlyGreen/Mission/segments.py` as a registry (`SEGMENT_TYPES`); add a new flight-segment kind by
subclassing `FlightSegment` and decorating with `@register_segment("Name")` — no other code
changes. The previous monolithic implementation is kept as `Profile_legacy.py` purely as a
numerical reference for the equivalence tests; don't build on it.

### Sizing flow (the core algorithm)
`Aircraft.DesignAircraft()` runs: `ReadInput` → `constraint.FindDesignPoint()` (picks the design
point `DesignPW`, `DesignWTOoS` from the constraint diagram) → `weight.WeightEstimation()`.
Because component masses depend on mission performance which depends on takeoff weight (WTO), the
weight estimation is an iterative **WTO convergence loop** solved with **Brent's method**
(`scipy.optimize.brentq`) in `trunk/PhlyGreen/Weight/Weight.py`. `Mission` integrates fuel/battery
energy and peak power over each segment; `Weight` turns those into fuel, battery, powertrain, and
structural masses.

**Powertrain power balance.** `Powertrain.Traditional`/`Hybrid` return normalized power
ratios (`PRatio[0]`=fuel, `[1]`=gas-turbine shaft, `[5]`=battery — these indices are
consumed by Mission/Weight). They delegate to a **component graph**
(`PhlyGreen/Systems/Powertrain/graph.py`): architectures are composed from
`converter`/`combiner`/`split`/`sink` primitives and solved as one linear system, instead
of hand-coded 4x4/7x7/8x8 matrices. Add a new architecture (e.g. fuel cell + battery, see
`fuelcell_battery_graph`) by composing primitives — no new matrix algebra. The original
solvers are kept as `_traditional_legacy`/`_hybrid_legacy` purely as the equivalence-test
reference.

### Configuration flags (set on the Aircraft instance before `ReadInput`)
These switch major code paths — check them when changing subsystem logic:
- `Configuration`: `'Traditional'` (thermal only), `'Hybrid'` (thermal + battery), or
  `'Hydrogen'` (fuel-cell electric — no battery, no gas turbine). Drives the powertrain
  efficiency chain and which `Mission.*Configuration` / `Weight.*` path runs.
- `HybridType`: `'Parallel'` or `'Serial'` (only when Hybrid).
- `weight.Class`: `'I'` (regression-based Structures model) or `'II'` (FLOPS component masses,
  `trunk/PhlyGreen/Weight/FLOPS_model.py`).
- `AircraftType`: `'ATR'` or `'DO228'` — selects the Class I structural model.
- Battery `CellInput['Class']`: `'I'` (specific energy/power lookup) or `'II'`
  (cell-level thermal model, `trunk/PhlyGreen/Systems/Battery/Cell_Models.py`).

### Class-II efficiency models (pluggable)
Component efficiencies can be operating-point dependent and are *replaceable*: see
`PhlyGreen/Systems/Powertrain/efficiency.py`. An `EfficiencyModel` maps an
`OperatingPoint(altitude, velocity, power, ...)` to an efficiency; implementations are
`ConstantEfficiency` (default — preserves legacy behavior), `CallableEfficiency` (wrap an
external code/law), and `ResponseSurfaceEfficiency` (wrap a fitted surrogate via
`.predict` or load one with `from_file`). `make_efficiency_model(spec)` builds one from a
float/callable/dict. `Powertrain.em_model`/`fc_model` (default `None`) inject these into the
graph: when set, the electric-motor / fuel-cell efficiency varies with the operating point.
`MotorEfficiencyModel` wraps the d-q `ElectricMotor` (`Systems/Powertrain/EM.py`) as a worked
Class-II example. The fuel-cell + battery architecture is available via
`Powertrain.PowerRatioFuelCellBattery` and `graph.fuelcell_battery_graph`.

### Hydrogen fuel cell
The `'Hydrogen'` configuration is a full fuel-cell electric path. `Systems/FuelCell/FuelCell.py`
is a physics model (Kulikovsky polarization curve, stack sizing, air-system power,
`ComputePRatio` returning 1/system-efficiency). `Mission.HydrogenConfiguration` integrates the
mission on hydrogen chemical energy (set `Ef` to the H2 LHV ≈120 MJ/kg); `Weight.Hydrogen`
closes the take-off weight over structure + fuel-cell system + H2 + tank + cooling. The
cryogenic LH2 tank (`Systems/Tank/`, **CoolProp** para-hydrogen) is sized when a `TankConfig`
is supplied and CoolProp is installed; otherwise a gravimetric-index model is used
(`EnergyConfig.h2_gravimetric_index`). The tank also has a transient `time_step` model
(self-pressurization, venting at P_max, heater at P_min); set `mission.track_tank = True` and
re-run `EvaluateMission` to populate `aircraft.tank.history` (see example `22`). Fuel-cell
inputs live in `EnergyConfig`
(`fc_model`, `i_rated`, `v_cell_design`, `stack_power_density`, `bop_mass_ratio`); examples
`20`/`21` size a fuel cell, fly the mission, and sweep the design voltage.

Heavy Class-II models from the source forks — the pycycle/openmdao gas turbine, the
pandas/CSV propeller RBF surrogate, and the CoolProp LH2 tank — integrate through this same
`EfficiencyModel`/response-surface interface but require their optional dependencies and
fitted artifacts; they are gated and not part of the default install.

### Units
Mixed unit conventions (SI internally, but inputs use kg, nautical miles, Mach/KCAS/TAS, °C, W/kg).
Use the helpers in `trunk/PhlyGreen/Utilities/` (`Units.py`, `Speed.py`, `Atmosphere.py` for ISA)
rather than hard-coding conversions.
