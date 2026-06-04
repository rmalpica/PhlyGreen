# PhlyGreen examples

Small, self-contained scripts for learning the code. Each is heavily commented and meant to
be **read, run, and tweaked**. Every example prints a verbose summary and, where it designs an
aircraft, saves one or more figures (a dashboard, sweeps, performance maps, time histories) to
`examples/_output/`.

## Setup

Install the package (editable) and run the examples from the `trunk/` directory:

```bash
pip install -e .          # from trunk/  (or: pip install -e ./trunk from the repo root)
cd trunk
python examples/01_design_traditional.py
```

`common.py` holds the baseline aircraft configurations the examples build on — start there,
change a number, and re-run an example to see the effect. It also provides the shared helpers
`print_results`, `design_dashboard` and `savefig` used across the examples.

Figures land in `examples/_output/` (created on first run). A few examples need optional
dependencies: `22` needs CoolProp (LH2 tank); `11b` needs pymoo; the propeller map in `05`
needs pandas — each degrades gracefully if the dependency is missing.

## Capability tour

| Script | What it shows | Figures |
|--------|---------------|---------|
| `01_design_traditional.py` | Build → configure → size a fuel-only aircraft; full results + input snapshot + CSV dump | dashboard, power time-series |
| `02_hybrid_with_battery.py` | A parallel hybrid-electric design with a battery pack (energy + SOC) | dashboard, power time-series |
| `03_typed_config_and_results.py` | Typed config, validation, config↔dict, results as a dict | mass groups |
| `04_flight_profile_and_custom_segment.py` | Query altitude/speed/phi(t); register a new segment type | profile timeline |
| `05_powertrain_graph_and_efficiency_models.py` | Power-balance graph; operating-point efficiencies; GT/EM/propeller performance maps | component maps |
| `06_utilities_atmosphere_and_speeds.py` | ISA atmosphere and Mach/TAS/CAS/EAS conversions vs altitude | ISA + speeds |
| `14_welltowake_and_climate.py` | Well-to-wake source energy, mission emissions, climate impact (ATR) | emissions + dashboard |
| `15_class_i_vs_class_ii.py` | Class-I vs Class-II structures (FLOPS) and battery models | comparison bars |
| `16_class_ii_propulsion_sizing.py` | Size the Class-II gas turbine / electric motor with over/under-size check; throttle vs time | component time-series |
| `17_battery_thermal_and_degradation.py` | Class-II battery: in-flight temperature history, ground fast-charge cooling load (TMS) and cycle-life vs charge C-rate | temperature vs time + sweep panels |
| `20_hydrogen_fuel_cell.py` | Size a hydrogen fuel-cell aircraft and fly the full mission | polarization + dashboard |
| `21_hydrogen_design_voltage_sweep.py` | Sweep the fuel-cell design voltage; find the take-off-weight optimum | sweep panels |
| `22_hydrogen_tank.py` | Size the cryogenic LH2 tank and track its pressure/mass/venting/heat over the mission (needs CoolProp) | tank state + dashboard |
| `23_fuelcell_battery_hybrid.py` | Hybridize a fuel cell with a battery; sweep the battery power share | sweep panels |

## Outer-loop applications

These use the stateless API `pg.run_design(config)` and `pg.evaluate(base, apply, x)`, which
run one independent design per call (safe to loop or parallelize).

| Script | What it shows | Figures |
|--------|---------------|---------|
| `10_parameter_sweep.py` | Sweep design range; weights and block fuel | line plots |
| `11_optimization.py` | Minimize block fuel over cruise Mach (SciPy) | objective curve |
| `11b_multiobjective_optimization.py` | Multi-objective NSGA-II (pymoo), in parallel: power split + Class-II GT/EM nominal powers + wing loading (ranges from a Class-I pre-pass) → WTO-vs-fuel Pareto front | Pareto front coloured by W/S |
| `12_uncertainty_quantification.py` | Monte-Carlo propagation of input uncertainty (NumPy; `chaospy` note inside) | histogram + sensitivity |
| `13_payload_range.py` | A 2-D payload×range sweep | block-fuel & WTO contours |

The single-objective outer-loop examples deliberately use only SciPy/NumPy so they run
anywhere; `11b` shows the production multi-objective path with pymoo. Figures are written to
`examples/_output/`.

## Learning tutorials

These examples are a **capability tour** (what the code can do). For a **pedagogical course**
that teaches the underlying engineering through guided experiments — Breguet vs PhlyGreen,
design constraints, a fair architecture comparison, the battery specific-energy wall, hydrogen's
hidden costs, and the fuel-vs-climate trade-off — see [`../tutorials/`](../tutorials/) (start at
`tutorials/README.md`). Those notebooks reuse the baselines in `common.py`.
