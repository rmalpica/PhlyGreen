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
- **⚙️ Advanced inputs** — *every* parameter and **model choice**: the gas-turbine / propeller /
  electric-motor efficiency models, the NOₓ model, the battery class, the weight model (Class I/II),
  the aircraft type, optional fixed wing loading, and all the per-section scalars.
- **📐 Constraint analysis** — the editable sizing requirements (DISA + the eight constraint
  points). Change a point and re-run to watch the design point move on the constraint diagram.

Nothing is sized until you press a tab's run button — changing an input does **not** re-run the
design automatically.

## What's in it

- **Design** — choose one of four architectures (conventional turboprop, parallel hybrid,
  hydrogen fuel cell, fuel cell + battery), tune the inputs, press **▶ Run design**, and read off
  the sized aircraft: take-off weight, fuel/hydrogen, masses, the flight profile, the constraint
  diagram and the take-off mass breakdown. Download the config, the results (JSON) and the mission
  time series (CSV).
- **Compare** — size several architectures on the *same* mission, **using the inputs set in the
  sidebar**, and get a tutorial-style trade study: a wide summary table (masses, energy, CO₂), a
  stacked take-off mass breakdown (summing to WTO), onboard-vs-well-to-wake energy and CO₂ (with
  illustrative lifecycle factors in `sustainability.py`), a **CO₂ vs CO₂-equivalent** chart that
  adds the gas-turbine non-CO₂ from the PW127 emission surrogate, and overlaid mission profiles.
  Use this tab's **Run comparison** button (the Design tab's Run button sizes only the single
  current design).
- **Sweep** — vary one input over a range and plot how an output responds.

Each design solves the take-off-weight convergence loop (~1 s). Inputs that push a design too hard
simply report *"did not close"* — relax the range, payload, or battery/fuel-cell assumptions.

## Files

| File | Role |
|------|------|
| `app.py` | Streamlit entry: sidebar + Design / Compare / Sweep / About tabs. |
| `templates.py` | The four "starting designs" (from `examples/common.py`) + config⇄dict serializer. |
| `controls.py` | The curated **main inputs** (knobs); one source of truth for Design + Sweep. |
| `advanced.py` | The **advanced** forms (every parameter + model choice) and the editable constraint diagram. |
| `runner.py` | Crash-safe, memoized wrappers around `pg.run_design` / `pg.evaluate`. |
| `render.py` | Dashboard figures, headline metrics, comparison/sweep charts, CSV export. |
| `sustainability.py` | Illustrative well-to-wake CO₂/energy factors + the gas-turbine CO₂-equivalent (emission surrogate + ATR). |

`runner.py`, `render.py`, `controls.py` and `templates.py` have no Streamlit dependency, so they
can be imported and tested without launching the app.
