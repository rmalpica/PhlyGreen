# Module Reference

A map of the `PhlyGreen` package (`trunk/PhlyGreen/`) — what lives where and which page
documents it. For per‑symbol API docs (signatures + docstrings) see the **API Reference**
section; for how the pieces fit together, the [Architecture Overview](architecture-overview.md).

---

## Top level

| File | Role |
|------|------|
| `Aircraft.py` | the central **mediator**: holds every subsystem, runs `ReadInput` / `DesignAircraft` / `configure`. |
| `factory.py` | `build_aircraft()` — constructs and cross‑wires all subsystems. |
| `api.py` | outer‑loop API: `run_design(config)`, `evaluate(base, apply, x)` (pure, fresh aircraft per call). |
| `results.py` | `AircraftResults` dataclass returned by `aircraft.results()`. |
| `postprocess.py` | mission time‑series extraction + plots (profile, energy, constraint diagram, mass breakdown, tank). |
| `__init__.py` | public exports (`build_aircraft`, `run_design`, `evaluate`, config classes…). |

## Configuration (`config/`)

Typed, validated input dataclasses (the preferred API; legacy dicts still accepted).

| File | Role |
|------|------|
| `aircraft_config.py` | `AircraftConfig` — bundles the flags + all sections. |
| `sections.py` | `MissionConfig`, `EnergyConfig`, `AerodynamicsConfig`, `ConstraintsConfig`, `CellConfig`, `WellToTankConfig`, `ClimateImpactConfig`, `TankConfig`. |
| `profile.py` | `StagesConfig` / segment configs (the flight profile). |
| `_base.py` | `DictConfig` base (`to_dict`/`from_dict`, validation helpers). |

## Subsystems

| Package | Class | User guide |
|---------|-------|------------|
| `Constraint/` | `Constraint` — P/W vs W/S diagram, design point. | [Constraints](../user-guide/constraints.md) |
| `Mission/` | `Mission` + `Profile` + `segments.py` (registry). | [Mission](../user-guide/mission.md) |
| `Weight/` | `Weight` (WTO loop) + `FLOPS_model.py` + `Components/`. | [Weight](../user-guide/weight.md) |
| `Performance/` | `Performance` — P/W requirements (`PoWTO`, `TakeOff`, …). | [Performance](../user-guide/performance.md) |
| `WellToWake/` | `WellToWake` — upstream energy/CO₂ accounting. | [Well‑To‑Wake](../user-guide/well-to-wake.md) |
| `ClimateImpact/` | `ClimateImpact` — emissions, radiative forcing, ATR. | [Emissions & Climate](../user-guide/emissions.md) |

## Systems (`Systems/`)

| Package | Contents | User guide |
|---------|----------|------------|
| `Powertrain/` | component `graph.py`, `efficiency.py` models, `EM.py`, gas‑turbine / propeller / emission surrogates. | [Powertrain](../user-guide/powertrain.md), [Surrogate Models](../user-guide/surrogate-models.md) |
| `Aerodynamics/` | `Aerodynamics` — the drag polar. | [Aerodynamics](../user-guide/aerodynamics.md) |
| `Structures/` | Class‑I structural / empty‑weight regressions (by `AircraftType`). | [Structures](../user-guide/structures.md) |
| `Battery/` | `Battery`, `Cell_Models.py` (Class‑II), `degradation.py` (ageing/TMS). | [Battery](../user-guide/battery.md) |
| `FuelCell/` | `FuelCell` — Kulikovsky polarization, stack sizing. | [Hydrogen](../user-guide/hydrogen.md) |
| `Tank/` | cryogenic LH2 tank (structural + MLI + transient state). | [Hydrogen](../user-guide/hydrogen.md) |
| `Thermal/` | `HeatSource`/`HeatSink`/`HeatExchangerNetwork` scaffold. | — |

## Utilities (`Utilities/`)

`Units.py`, `Speed.py` (Mach/KCAS/TAS), `Atmosphere.py` (ISA). Use these rather than hard‑coding
unit conversions — the codebase mixes SI (internal) with kg / nautical miles / Mach / °C / W·kg⁻¹ at
the input boundary.

## Surrogate generation (offline)

`Systems/Powertrain/emissions_pipeline/` and the `train_*_surrogate.py` scripts regenerate the
shipped response‑surface artifacts (need pycycle/openmdao, Cantera, pandas). The fitted `.pkl`/`.csv`
are loaded at run time with no heavy dependency — see [Surrogate Models](../user-guide/surrogate-models.md).


