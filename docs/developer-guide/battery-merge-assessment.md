# `works_on_batt` merge assessment

The `works_on_batt/` folder is a student fork (Class-II battery work) that diverged
substantially (~6 200 lines) from the restructured codebase. Rather than merging it wholesale,
the differences were assessed file-by-file and only the genuinely new, self-contained and
clearly-beneficial physics was ported into the current architecture. This page records what was
taken and what was rejected, and why.

## Merged

### Robust take-off-weight solver (`Weight.py`)
The fork replaced the fixed Brent bracket `brenth(func, 1000, 300000)` — which fails when the
endpoints do not bracket a sign change or the residual errors mid-range — with a grid-scan that
finds the first valid bracket before calling Brent. This was the fix that made the student's
parametric sweeps converge smoothly.

**Ported** as `Weight._solve_wto`, used by every weight loop (Traditional/Hybrid, Hydrogen,
Fuel-cell+battery). It first tries the original full-range Brent (so any design that already
converged returns the *exact* same root — golden masters unchanged) and only falls back to the
grid-scan when that fails. Optional `MissionInput` keys `Brenth Lower/Upper Limit` override the
bracket. Covered by `tests/unit/test_weight_solver.py`.

### Class-II battery heat management + degradation (`Battery.py`)
The fork added a ground fast-charge thermal model (Joule heating vs active cold-plate cooling),
the peak cooling power a thermal-management system (TMS) must reject, and a Wang et al.
capacity-fade / Miner damage cycle-life model.

**Ported** as an *opt-in, post-design* analysis in
`Systems/Battery/degradation.py` (`BatteryAgeingModel`) plus the convenience method
`Battery.thermal_degradation_analysis()`, parametrized by new optional `CellConfig` fields
(`charge_c_rate`, `discharge_c_rate`, `maximum_soc`, `eol_capacity`, `coolant_temperature`,
`ground_cooling_coefficient`). It runs on an already-sized pack and is never part of the WTO
loop, so it cannot change a baseline design. Results are cached on `battery.ageing` and exposed
via `AircraftResults.extras['battery_ageing']`. See example
`17_battery_thermal_and_degradation.py` and `tests/unit/test_battery_degradation.py`. The
in-flight electro-thermal model (`Battery.heatLoss`) already existed and was unchanged.

## Assessed and not merged

| Fork file | Reason for rejection |
|---|---|
| `Mission.py` | The numerical-integration changes (`solve_ivp`, BDF, `rtol≈1e-5`) are already present in the restructured `Mission/Mission.py` (which also adds `max_step`); no net improvement, and the fork predates the segment-registry / configuration refactor. |
| `Powertrain.py` | Superseded by the restructured component-graph powertrain and the universal gas-turbine surrogate (`gas_turbine_surrogate.py`) with runtime size scaling. The fork's `GTEngineModel` is the earlier, monolithic version of the same idea. |
| `Aircraft.py` | The added print-outs for cooling power / cycles are superseded by the typed `AircraftResults` and `postprocess` helpers. |
| `Weight.py` (FLOPS parts), `Structures.py`, `FLOPS_input.py`, `Components/` | Refined FLOPS component-mass models. Out of scope for this round (battery-focused) and divergent from the current `Weight/FLOPS_model.py`; revisit separately if a FLOPS refresh is wanted. |
| `Aerodynamics.py`, `Cell_Models.py`, `Units.py` | Minor / overlapping with current modules; nothing new worth importing. |
| `parametric_analysis*.py`, `parametric_graphs.py`, `CLASS_II_CONSERVATIVE.ipynb` | Research/plotting scripts (pandas + seaborn studies), not library code. Kept only as a numerical reference for the ported battery physics. |

## Notes
- The student credited for this work is **Francesco Campagna** (Class-II battery heat management
  and degradation); see the README.
- `works_on_batt/` itself is left untracked/unmerged in the repository.
