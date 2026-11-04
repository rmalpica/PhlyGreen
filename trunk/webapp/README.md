# Virtual Aircraft Design Lab (Streamlit GUI)

A browser-based teaching front-end over **PhlyGreen** for the *Sustainable Propulsion* course.
Students pick a propulsion architecture, tune a few inputs, size the aircraft, and inspect the
results — then compare architectures or sweep a parameter for a trade study.

It is a **thin wrapper**: it builds typed `AircraftConfig`s and calls the public `PhlyGreen`
design + `postprocess` API. The package itself is unchanged.

## Install & run (local, per student)

From the repository root:

```bash
pip install -e ./trunk                          # the PhlyGreen package (+ CoolProp, numpy, scipy, matplotlib)
pip install -r trunk/webapp/requirements.txt    # streamlit
streamlit run trunk/webapp/app.py
```

Streamlit opens the lab in your browser at `http://localhost:8501`.

## Inputs

The sidebar has three layers:

- **Main inputs** — the handful of parameters you tune most (range, payload, cruise Mach/altitude,
  Cd0, aspect ratio, efficiencies, and — for the battery architectures — the **take-off, climb and
  cruise battery shares φ** separately, plus battery specific energy / fuel-cell voltage). For the
  fuel-cell + battery design a **Battery model** selector chooses Class I (specific energy/power) or
  Class II (the cell-level electro-thermal model with P-number sizing + thermal cooling; slower).
  For the two fuel-cell designs a **Thermal management (TMS)** selector chooses Class I (heat-exchanger
  mass from a specific power) or Class II (geometric coolant→LH₂ and coolant→ram-air heat exchangers,
  coolant pump and ram-air duct drag, sized over the mission; ~1 min per design).
- **⚙️ Advanced inputs** — *every* parameter and **model choice**: the gas-turbine / propeller /
  electric-motor efficiency models, the NOₓ model, the battery class, the weight model (Class I/II),
  the aircraft type, the powertrain double-count flag and structure calibration, optional fixed
  wing loading, the ground segments (taxi-out/in time, taxi power, take-off time), the fuel-cell
  product-water phase, every TMS input, and all the per-section scalars.
- **📐 Constraint analysis** — the editable sizing requirements (DISA + the eight constraint
  points). Change a point and re-run to watch the design point move on the constraint diagram.

Nothing is sized until you press a tab's run button — changing an input does **not** re-run the
design automatically.

## What's in it

- **Design** — choose an architecture (conventional turboprop, hybrid GT + battery, serial range
  extender, hydrogen fuel cell, hybrid fuel cell + battery, or the A320-class turbofan jet), tune the
  inputs, press **▶ Run design**, and
  read off the sized aircraft: take-off weight, fuel/hydrogen, masses, the flight profile, the
  constraint diagram and the take-off mass breakdown. The hydrogen architectures also size a
  physics LH2 tank and show its **thermodynamic evolution** (pressure, stored H2, vent flow,
  heater). An opt-in **well-to-wake emissions** panel reports WTW energy, CO₂ and CO₂-equivalent,
  split into well-to-tank (upstream) and tank-to-wake (onboard), with **editable lifecycle factors**
  (well-to-tank energy efficiency and CO₂ intensities per carrier) that update the result live. Download the config, the results
  (JSON) and the mission time series (CSV). The battery architectures default to the *power
  hybridization* of tutorial 03 (battery on take-off/climb, primary source sized for cruise).
  With the Class-II TMS, the Design tab also shows the sized heat exchangers (units, family, mass,
  volume, heat), the pump, the ram-air drag, and the chosen hardware rated at every mission point.
- **Compare** — size several of the regional architectures on the *same* mission, **using the
  inputs set in the sidebar** (the turbofan flies a different mission and is not offered here), and get a tutorial-style trade study: a wide summary table (masses, energy, CO₂), a
  stacked take-off mass breakdown (summing to WTO), onboard-vs-well-to-wake energy and CO₂ (with
  illustrative lifecycle factors in `sustainability.py`), a **CO₂ vs CO₂-equivalent** chart that
  adds the gas-turbine non-CO₂ from the PW127 emission surrogate, and overlaid mission profiles.
  Use this tab's **Run comparison** button (the Design tab's Run button sizes only the single
  current design).
- **Sweep** — vary one input over a range and plot how an output responds.

Each design solves the take-off-weight convergence loop (a few seconds; up to ~1 min with the
Class-II battery or the Class-II TMS). Inputs that push a design too hard
simply report *"did not close"* — relax the range, payload, or battery/fuel-cell assumptions.

## Files

| File | Role |
|------|------|
| `app.py` | Streamlit entry: sidebar + Design / Compare / Sweep / About tabs. |
| `templates.py` | The "starting designs" (from `examples/common.py`, whose reference ATR is calibrated to the ATR 42-600 factsheet) + config⇄dict serializer. |
| `controls.py` | The curated **main inputs** (knobs); one source of truth for Design + Sweep. |
| `advanced.py` | The **advanced** forms (every parameter + model choice) and the editable constraint diagram. |
| `runner.py` | Crash-safe, memoized wrappers around `pg.run_design` / `pg.evaluate`. |
| `render.py` | Dashboard figures, headline metrics, comparison/sweep charts, CSV export. |
| `sustainability.py` | Illustrative well-to-wake CO₂/energy factors + the gas-turbine CO₂-equivalent (emission surrogate + ATR). |

`runner.py`, `render.py`, `controls.py` and `templates.py` have no Streamlit dependency, so they
can be imported and tested without launching the app.
