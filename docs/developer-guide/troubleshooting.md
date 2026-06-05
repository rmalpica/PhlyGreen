# Troubleshooting

Common failure modes when running or extending PhlyGreen, and how to resolve them. If a design
**raises** rather than returning, the message usually points at the stage below.

---

## Setup & imports

**`ModuleNotFoundError: No module named 'PhlyGreen'`**
The package lives in `trunk/`, not the repo root. Install it editable so imports work from anywhere:

```bash
pip install -e ./trunk
```

Notebooks/scripts under `trunk/tutorial/` instead do `sys.path.insert(0, '../')` and assume the
working directory is `trunk/`.

**`ImportError` for `pandas` / `cantera` / `pycycle` / `CoolProp`.**
These are **optional**, needed only for specific paths:

| Dependency | Needed by |
|------------|-----------|
| `pandas` | the data‑trained propeller surrogate (`'Eta Propulsive Model': 'Surrogate'`) |
| `CoolProp` | the cryogenic LH2 tank physics (falls back to a gravimetric‑index model if absent) |
| `pycycle` + `openmdao`, `cantera` | only to **regenerate** the GT efficiency / emission surrogates; the shipped `.pkl`/`.csv` load without them |

The shipped surrogates and the default install don't need the heavy stack — see
[Surrogate Models](../user-guide/surrogate-models.md).

---

## Configuration errors

**`ConfigError: ConstraintsConfig missing required phases: [...]`**
All eight constraint phases must be present (`Cruise`, `AEO Climb`, `OEI Climb`, `Take Off`,
`Landing`, `Turn`, `Ceiling`, `Acceleration`). Supply an **empty dict** `{}` to disable a phase
rather than omitting it. See [Constraints](../user-guide/constraints.md).

**`ValueError: ... polar model not implemented` / `aerodynamic model unknown`.**
Supply exactly one of `AnalyticPolar` (`{'type': 'Quadratic', 'input': {'AR':…, 'e_osw':…}}`) or
`NumericalPolar` (`{'type': 'ATR42' | 'DO228'}`). See [Aerodynamics](../user-guide/aerodynamics.md).

**`ValueError: Design P/W unset` / `Design W/S unset`.**
The design point wasn't computed before something read it. Run the full
`aircraft.configure(config)` / `DesignAircraft()` (which calls `constraint.FindDesignPoint()`), not
just `weight.WeightEstimation()` on its own.

**`ValueError: Missing '<key>' in the TankInput dictionary`.**
A `'Hydrogen'` design with a `TankConfig` needs the full tank input set; check the
[Hydrogen](../user-guide/hydrogen.md) page for the required keys, or omit `TankConfig` to use the
gravimetric‑index tank model.

---

## The take‑off‑weight loop won't converge

The WTO loop solves a fixed point with Brent's method (`Weight._solve_wto`). It first tries the full
`[lower, upper]` bracket, then falls back to a grid‑scan for the first valid sign‑change interval, so
most designs close. If it still raises (the original Brent error is re‑surfaced):

- **The design is genuinely infeasible** — e.g. a battery so heavy the mass diverges, or a mission
  the powertrain can't fly. Relax the requirement (range, battery share φ, specific energy) and
  re‑run. In a sweep, wrap the call so an infeasible point is *flagged* rather than crashing the
  loop (see `tutorials/_learning_utils.safe_design`).
- **The bracket is wrong** — override it with the `MissionInput` keys `Brenth Lower Limit` /
  `Brenth Upper Limit` to span the expected \(W_{TO}\).
- **A sub‑model errors mid‑range** — run a single design (not a sweep) and read the traceback; the
  failing subsystem is named in it.

---

## Class‑II propulsion sizing warnings

**"power‑limited at altitude" / oversized engine.**
The Class‑II gas turbine and electric motor work as a *percentage of a fixed nominal power* that
must be chosen **before** the mission. After sizing, `powertrain.report_class_ii_sizing()` flags an
undersized (`power_limited`) or oversized component. Re‑run with an adjusted `GT Design Power` /
`EM Design Power` (a good first guess is `DesignPW * WTO`); example
`16_class_ii_propulsion_sizing.py` walks the pre‑pass → size → re‑size loop.

---

## Emissions / climate surrogate

**`predict_op expects a direct (alt, Mach, power) map ...`**
You called `predict_op` on a combustor‑state artifact. Use the packaged operating‑point map
(`EmissionSurrogate()` with no argument) for `(alt_ft, Mach, PC)` queries.

**Idle/taxi emission indices look clipped.**
The PW127 emission surrogate is valid over power fraction \(PC \in [0.3, 1.0]\); idle (\(PC \approx
0.07\)) is **below** the modelled range and is clipped to the edge. NOₓ is certification‑anchored,
CO/UHC come from the CRN, soot is not yet modelled — see
[Surrogate Models](../user-guide/surrogate-models.md#4-gasturbine-emissions-surrogate).

---

## Results changed unexpectedly

If a refactor moved the design outputs, the **golden‑master** regression tests will catch it:

```bash
cd trunk && pytest                 # full suite, incl. tests/regression/golden/*.json
```

A green suite means results are bit‑for‑bit unchanged. If a change is *meant* to alter results,
regenerate the baselines deliberately and review the diff:

```bash
python tests/regression/_generate_golden.py
```

See [Extending the Model](extending-the-model.md) for the workflow.

---

## Still stuck?

- Reproduce with a **single** `pg.run_design(config)` to get a clean traceback.
- Compare against a known‑good baseline in `examples/common.py`.
- Check the [Architecture Overview](architecture-overview.md) / [Flowcharts](flowcharts.md) to locate
  the failing stage, and the [Module Reference](module-reference.md) for where it lives.
