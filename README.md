# PhlyGreen
A python tool for the preliminary design of novel aircraft concepts for a more sustainable air mobility.

This code is under development at Sapienza University of Roma (Italy).

Given a mission profile and design constraints, PhlyGreen sizes each aircraft subsystem so the
vehicle can fly the mission within all constraints. It supports **conventional**,
**hybrid-electric**, **hydrogen fuel-cell** and **fuel-cell + battery** configurations.

## What's new in v1.0.0

This is the first stable release, consolidating a large restructuring and several new physics
models:

- **Typed, validated configuration & results.** `pg.build_aircraft()` wires the aircraft;
  `AircraftConfig` (and friends) replace loose input dicts (the dicts still work);
  `aircraft.results()` returns an `AircraftResults` dataclass with `to_dict()`, a new
  **`input_summary()`** that records *exactly what was solved*, and `write_timeseries()` to dump
  every time-evolving mission variable.
- **Stateless outer-loop API** for optimization / UQ / sweeps: `pg.run_design(config)` and
  `pg.evaluate(base, apply, x)` (fresh aircraft per call, input never mutated).
- **Component-graph powertrain** with pluggable **per-component efficiency models** — Class-I
  (constant) or Class-II (altitude/velocity/power/rpm dependent): a universal **gas-turbine**
  response surface with runtime engine-size scaling, a d-q **electric-motor** model, and
  **Hamilton / RBF propeller** models.
- **Hydrogen fuel cell** (Kulikovsky polarization, air compressor, heat management,
  design-voltage stack sizing) with an optional **cryogenic LH2 tank** (self-pressurization,
  venting, heater), and a **fuel-cell + battery** hybrid.
- **Class-II battery** with an opt-in **thermal-management & cycle-life degradation** analysis
  (ground fast-charge cooling load, Wang/Miner cycle life).
- A robust take-off-weight solver, a `postprocess` module (mission/component time series and
  plots), ~20 documented **examples** (incl. a parallel pymoo NSGA-II multi-objective study),
  a pytest suite with golden-master regression tests, and a full MkDocs site.

## Quick start

```bash
pip install -e ./trunk            # editable install of the PhlyGreen package
cd trunk
python examples/01_design_traditional.py
```

See `trunk/examples/` (start at `examples/README.md`) and the
[documentation](https://rmalpica.github.io/PhlyGreen/).

**Learning the engineering, not just the API?** The pedagogical course in
`trunk/tutorials/` (start at `tutorials/README.md`) is a set of guided experiments for
Master's students — Breguet vs PhlyGreen, design constraints, a fair architecture comparison,
why batteries are hard, hydrogen's hidden costs, and the fuel-vs-climate trade-off.

Authors:

- Riccardo Malpica Galassi
- Matteo Blandino

Students who contributed to the code development:

- Joao Delille (Class II Battery model)
- Valeria Falcone (Climate Impact)
- Francesco Ballirano (Class II gas turbine and electric motor models)
- Alan Liss (Fuel cell and cryogenic hydrogen tank models)
- Francesco Campagna (Class II Battery model heat management and degradation)

[![Documentation Status](https://img.shields.io/badge/docs-online-success)](https://rmalpica.github.io/PhlyGreen/)
