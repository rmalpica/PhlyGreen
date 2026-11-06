# PhlyGreen
A python tool for the preliminary design of novel aircraft concepts for a more sustainable air mobility.

This code is under development at Sapienza University of Roma (Italy).

Given a mission profile and design constraints, PhlyGreen sizes each aircraft subsystem so the
vehicle can fly the mission within all constraints. It supports **conventional**,
**hybrid-electric**, **hydrogen fuel-cell** and **fuel-cell + battery** configurations.

## What's new in v1.1.0

- **Turbofan configuration.** Jets are sized on thrust instead of shaft power
  (`Configuration='Turbofan'`). It uses a thrust-lapse engine map fitted to a pyCycle
  high-bypass turbofan deck, a compressible drag polar (Korn drag divergence and Lock wave
  drag) and a CFM56-class emission-index surrogate. An **A320-200 validation**
  (`trunk/validation/`) compares MTOW, OEW, wing area and thrust with Airbus and EASA data.
- **Class-II thermal management for fuel cells.** `TMSConfig(tms_class='II')` sizes the
  cooling system from geometry: a coolant-to-LH2 exchanger plus ram-air exchangers (tube
  banks or plate-fin, ε-NTU), the coolant pump and the ram-air duct drag. The design point is
  chosen over the whole mission. The pump power is fed back to the fuel cell as an electrical
  load and the duct drag to the polar. Class I (specific power) remains the default and now
  includes the take-off heat. See the new *Thermal management* page and example 27.
- **Fuel-cell heat basis.** The heat sent to the coolant accounts for the product water that
  leaves as vapour. By default the vapour fraction is computed from the cathode-exhaust
  saturation (`EnergyConfig.fc_product_water_vapour_fraction`, `fc_cathode_inlet_rh`).
- **Ground segments.** Taxi-out, take-off run and taxi-in are now flown with each
  configuration's own powertrain (ICAO LTO times and power settings, `MissionConfig.taxi_*`,
  `takeoff_time`). The start-of-climb mass fraction follows from them, so `Beta start` is
  deprecated and ignored.
- **Hydrogen mass bookkeeping.** The LH2 tank now holds the reserve as well as the mission
  load. The load carries an explicit margin, `EnergyConfig.h2_fuel_margin` (default 0.05).
- **Reference aircraft.** The example requirements are calibrated on the ATR 42-600
  factsheet: take-off field 1,107 m, climb at 160 KCAS, 1,851 ft/min. The kerosene baseline
  lands within about 4 % of the real aircraft. A new *Reference aircraft* docs page, with
  examples 28 (ATR 42-600) and 29 (A320-200), lists every input with its source.
- **Fuel cell + battery.** Example 23 shows when a take-off battery makes a fuel-cell aircraft
  lighter: on a short (800 m) field, at the share predicted by the power balance. On the
  baseline field it never does.
- **Off-design missions.** Example 30 (`fly_off_design`) flies a sized aircraft, frozen, on
  another range, payload or φ schedule. It closes the take-off mass and checks the tank, MTOW,
  battery and engine limits. It is the inner loop of multi-point studies.
- **Climate accounting for hydrogen.** `ClimateImpact` now treats fuel-cell designs correctly:
  no tank-to-wake CO₂, SO₄, soot or NOₓ, and 8.94 kg of water per kg of H₂. It also counts the
  grid CO₂ of the battery energy for every battery configuration.
- **Other additions:**
  - a clear error when a mission range is shorter than its climbs and descents (previously a
    negative-length cruise was flown silently);
  - a serial (range-extender) hybrid;
  - Class-II gas-turbine emission surrogates (PW127);
  - a constant-throttle climb segment;
  - fixes to the landing constraint, the FLOPS masses, the PMAD and electric-motor masses, and
  - battery energy in hybrid/all-electric taxi-in/out and take-off is now accounted for
    the fuel-cell sizing and propeller chain.
- **Learning material:**
  - learning tutorials 00–08, including a fuel-cell deep dive (07) and thermal management (08);
  - an interactive Streamlit webapp, with TMS selection and an A320 template;
  - new documentation figures (HEX geometries, TMS rating, reference-aircraft comparisons).
- **Results change.** Because of the ground segments and the calibrated requirements, design
  results differ from v1.0.0. The golden-master tests were regenerated (traditional baseline
  MTOW 18,327 → 18,742 kg).

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

**Note**: This project was developed over several years through contributions, experiments, and iterative improvements. During a later maintenance phase, Claude Code was used to assist with code refactoring, simplification, and cleanup. The architecture, algorithms, and scientific implementation remain the work of the project contributors.

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

**Virtual Aircraft Design Lab (Streamlit GUI)** A browser-based teaching front-end. 
From the repository root:

```bash
streamlit run trunk/webapp/app.py
```

Streamlit opens the lab in your browser at `http://localhost:8501`.

Authors:

- Riccardo Malpica Galassi
- Matteo Blandino

Students who contributed to the code development:

- Valeria Falcone (Climate Impact model)
- Joao Delille (Class II Battery model)
- Manuel Barata Marques (Optimization and multi-mission)
- Francesco Ballirano (Class II gas turbine and electric motor models)
- Alan Liss (Fuel cell and cryogenic hydrogen tank models)
- Francesco Campagna (Class II Battery model heat management and degradation)
- Andrea Pietrosanto (GT Pollutant emissions model)
- Fabrizio Bassis (GT Soot emissions model)
- Diego Marconi (Class II Thermal Management System)

[![Documentation Status](https://img.shields.io/badge/docs-online-success)](https://rmalpica.github.io/PhlyGreen/)
