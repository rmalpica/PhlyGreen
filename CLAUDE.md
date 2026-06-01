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
- `trunk/Validation/`, `trunk/playground/` — validation sweeps and experimental scripts.
- `docs/` + `mkdocs.yml` — MkDocs site (published via GitHub Pages on push to `main`).
- `to_be_merged/`, `misc/`, `trunk/JofAircraft/` — unmerged forks (e.g. H2, advanced propeller
  models) and legacy code. **Not** part of the main package; do not edit unless asked.

## Setup & commands

```bash
pip install -e ./trunk          # editable install of the PhlyGreen package
pip install -r requirements.txt # numpy, scipy, joblib, scikit-learn, matplotlib, ipykernel
```

Notebooks/scripts under `trunk/tutorial/` import the package with `sys.path.insert(0, '../')`,
so they assume the working directory is `trunk/`. Prefer `pip install -e ./trunk` so imports work
from anywhere.

Docs (run from repo root, uses `mkdocs.yml`):

```bash
mkdocs serve   # live preview
mkdocs build   # build static site
```

There is **no automated test suite** (no pytest/CI for the code). The only CI is `mkdocs build`
in `.github/workflows/deploy.yml`. Validate changes by running the tutorial notebooks or the
scripts in `trunk/Validation/` and comparing the printed design summary.

## Architecture

### Mediator (hub-and-spoke) object graph
`Aircraft` (`trunk/PhlyGreen/Aircraft.py`) is a central mediator. Each subsystem holds a reference
to the `Aircraft`, and the `Aircraft` holds a reference to each subsystem, so any module reads
another module's data/methods via `self.aircraft.<subsystem>`. Subsystems:
`powertrain, structures, aerodynamics, performance, mission, weight, constraint, welltowake,
battery, climateimpact`.

Wiring is done by hand (see `trunk/tutorial/tutorial.ipynb`): each subsystem is constructed with
`None`, the `Aircraft` is built from all of them, then each subsystem's `.aircraft` attribute is
assigned back. When adding a subsystem, replicate this two-way wiring.

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

### Sizing flow (the core algorithm)
`Aircraft.DesignAircraft()` runs: `ReadInput` → `constraint.FindDesignPoint()` (picks the design
point `DesignPW`, `DesignWTOoS` from the constraint diagram) → `weight.WeightEstimation()`.
Because component masses depend on mission performance which depends on takeoff weight (WTO), the
weight estimation is an iterative **WTO convergence loop** solved with **Brent's method**
(`scipy.optimize.brentq`) in `trunk/PhlyGreen/Weight/Weight.py`. `Mission` integrates fuel/battery
energy and peak power over each segment; `Weight` turns those into fuel, battery, powertrain, and
structural masses.

### Configuration flags (set on the Aircraft instance before `ReadInput`)
These switch major code paths — check them when changing subsystem logic:
- `Configuration`: `'Traditional'` (thermal only) or `'Hybrid'` (thermal + battery). Drives the
  powertrain efficiency chain and mission integration.
- `HybridType`: `'Parallel'` or `'Serial'` (only when Hybrid).
- `weight.Class`: `'I'` (regression-based Structures model) or `'II'` (FLOPS component masses,
  `trunk/PhlyGreen/Weight/FLOPS_model.py`).
- `AircraftType`: `'ATR'` or `'DO228'` — selects the Class I structural model.
- Battery `CellInput['Class']`: `'I'` (specific energy/power lookup) or `'II'`
  (cell-level thermal model, `trunk/PhlyGreen/Systems/Battery/Cell_Models.py`).

### Units
Mixed unit conventions (SI internally, but inputs use kg, nautical miles, Mach/KCAS/TAS, °C, W/kg).
Use the helpers in `trunk/PhlyGreen/Utilities/` (`Units.py`, `Speed.py`, `Atmosphere.py` for ISA)
rather than hard-coding conversions.
