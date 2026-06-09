# PhlyGreen learning tutorials

A short, **pedagogical** course of Jupyter notebooks for Master's students in Sustainable
Aircraft Propulsion / Aeronautical Engineering. These are **guided experiments**, not a
black-box design tool: each notebook uses PhlyGreen to build intuition about the *assumptions,
trade-offs and limitations* behind sustainable propulsion — why it is hard, not just how to run
the code.

> **Educational scope.** The notebooks lean on PhlyGreen's **real** models — sizing, gas-turbine
> emissions, and the climate Average Temperature Response (ATR). The single deliberate
> simplification is the hand-drawn constraint-feasibility map in notebook 02, which is clearly
> labelled (PhlyGreen's real constraint diagram is shown alongside it). The heavy lifting always
> goes through the public API (`pg.run_design` / `pg.evaluate`), the `ClimateImpact` module, and
> the baseline configs in [`examples/common.py`](../examples/common.py).

## Setup

From a fresh clone:

```bash
pip install -e ./trunk            # editable install of the PhlyGreen package
pip install -r requirements.txt   # numpy, scipy, matplotlib, ...
pip install jupyter
cd trunk
jupyter lab tutorials/            # open the notebooks in order
```

The notebooks add `examples/` to `sys.path` automatically (via `_learning_utils.add_examples_to_path`)
and use **no absolute paths**, so they run from anywhere under the repo.

## Recommended order

| # | Notebook | Learning objective | Main variables | Expected output |
|---|----------|--------------------|----------------|-----------------|
| 00 | `00_README_learning_path.ipynb` | Orientation & how to use the course | — | environment check |
| 01 | `01_breguet_vs_phlygreen.ipynb` | Bridge a hand calculation to a full sizing loop | fuel fraction, L/D, efficiency | Breguet curve + PhlyGreen point |
| 02 | `02_design_variables_and_constraints.ipynb` | Why design is *constrained*, not just minimised | wing loading W/S, power/weight P/W | WTO vs W/S, constraint & feasibility maps |
| 03 | `03_compare_propulsion_architectures_same_mission.ipynb` | Compare 5 architectures *fairly* | architecture, mass, energy, CO₂ | comparison table + bar charts |
| 04 | `04_why_batteries_are_hard_for_aviation.ipynb` | The battery specific-energy wall | battery Wh/kg | mass fraction & feasibility vs Wh/kg |
| 05 | `05_hydrogen_is_not_free.ipynb` | Hydrogen's mass *and volume* and storage penalty | H₂ mass, tank gravimetric index | fuel/volume/mass comparisons |
| 06 | `06_climate_vs_fuel_tradeoff.ipynb` | Does minimum fuel mean minimum climate? (real CO₂ + non-CO₂ ATR) | cruise altitude | fuel & ATR vs altitude, non-CO₂ share, Pareto |
| 07 | `07_fuel_cell_deep_dive.ipynb` | Open the fuel-cell box: cell physics, auxiliaries, and how they size the aircraft | design cell voltage V_cell, cathode pressure, BoP mass | polarization & system-efficiency curves, weight breakdown, WTO-vs-V_cell optimum, compressor & BoP impact, cell operating point / stack heat / LH₂ tank along the mission |

## Helper module

[`_learning_utils.py`](_learning_utils.py) holds the few shared helpers (path setup, a
crash-safe `safe_design`, a couple of config mutators, the closed-form Breguet equation, and thin
wrappers around PhlyGreen's real `ClimateImpact` model — `attach_climate_model` / `climate_atr`).
It exists only to remove repetition across notebooks.

## Tone

Educational, critical, engineering-oriented. The notebooks deliberately **avoid overselling**
any technology and emphasise trade-offs, assumptions, uncertainty and feasibility. The intended
takeaway is *why* sustainable propulsion is difficult.

For the capability-tour material (scripts that show off the API surface), see
[`../examples/`](../examples/); for the narrative workflow notebooks, see [`../notebooks/`](../notebooks/).
