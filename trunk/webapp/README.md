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

## What's in it

- **Design** — choose one of four architectures (conventional turboprop, parallel hybrid,
  hydrogen fuel cell, fuel cell + battery), tune the sidebar inputs, and read off the sized
  aircraft: take-off weight, fuel/hydrogen, masses, the flight profile, the constraint diagram and
  the take-off mass breakdown. Download the config, the results (JSON) and the mission time series
  (CSV).
- **Compare** — size several architectures on the *same* mission (shared range & payload) and
  compare their masses side by side.
- **Sweep** — vary one input over a range and plot how an output responds.

Each design solves the take-off-weight convergence loop (~1 s). Inputs that push a design too hard
simply report *"did not close"* — relax the range, payload, or battery/fuel-cell assumptions.

## Files

| File | Role |
|------|------|
| `app.py` | Streamlit entry: sidebar + Design / Compare / Sweep / About tabs. |
| `templates.py` | The four "starting designs" (from `examples/common.py`) + config⇄dict serializer. |
| `controls.py` | The curated set of tunable inputs (knobs); one source of truth for Design + Sweep. |
| `runner.py` | Crash-safe, memoized wrappers around `pg.run_design` / `pg.evaluate`. |
| `render.py` | Dashboard figures, headline metrics, comparison/sweep charts, CSV export. |

`runner.py`, `render.py`, `controls.py` and `templates.py` have no Streamlit dependency, so they
can be imported and tested without launching the app.
