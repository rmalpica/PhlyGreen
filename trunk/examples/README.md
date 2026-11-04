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
| `02b_serial_hybrid.py` | Serial vs parallel hybrid topology: the serial chain's generator+motor double conversion costs fuel and battery mass | dashboard |
| `03_typed_config_and_results.py` | Typed config, validation, config↔dict, results as a dict | mass groups |
| `04_flight_profile_and_custom_segment.py` | Query altitude/speed/phi(t); register a new segment type | profile timeline |
| `05_powertrain_graph_and_efficiency_models.py` | Power-balance graph; operating-point efficiencies; GT/EM/propeller performance maps | component maps |
| `06_utilities_atmosphere_and_speeds.py` | ISA atmosphere and Mach/TAS/CAS/EAS conversions vs altitude | ISA + speeds |
| `14_welltowake_and_climate.py` | Well-to-wake source energy, mission emissions, climate impact (ATR) | emissions + dashboard |
| `15_class_i_vs_class_ii.py` | Class-I vs Class-II structures (FLOPS) and battery models | comparison bars |
| `16_class_ii_propulsion_sizing.py` | Size the Class-II gas turbine / electric motor with over/under-size check; throttle vs time | component time-series |
| `17_battery_thermal_and_degradation.py` | Class-II battery: in-flight temperature history, ground fast-charge cooling load (TMS) and cycle-life vs charge C-rate | temperature vs time + sweep panels |
| `18_serial_range_extender_gt.py` | Serial range-extender (constant-power turbine + recharging battery buffer) vs parallel turboprop, with the Class-II operating-point-dependent gas turbine; honest take: the serial turbine runs a bit more efficiently but conversion+mass penalties make it burn more fuel at efficient cruise | GT part-load map, serial power split |
| `20_hydrogen_fuel_cell.py` | Size a hydrogen fuel-cell aircraft and fly the full mission | polarization + dashboard |
| `21_hydrogen_design_voltage_sweep.py` | Sweep the fuel-cell design voltage; find the take-off-weight optimum | sweep panels |
| `22_hydrogen_tank.py` | Size the cryogenic LH2 tank and track its pressure/mass/venting/heat over the mission (needs CoolProp) | tank state + dashboard |
| `23_fuelcell_battery_hybrid.py` | When does a battery pay on a fuel-cell aircraft? Take-off-only vs take-off+climb vs cruise battery, on the baseline 1,107 m field and an 800 m short field (ATR 42-600S); predicted vs swept optimum share | sweep panels |
| `24_gt_emissions_surrogate.py` | State-dependent GT pollutant emissions (NOx/CO/UHC) from the PW127 EI response surface; `einox_model='Surrogate'` vs Filippone | EI vs power & altitude |
| `25_fuelcell_battery_class_ii_models.py` | Fuel-cell + battery sized with the Class-II battery (P-number + thermal), the d-q ("Smart") electric motor and the Hamilton propeller; plots SOC/temperature, power split and component efficiencies (compute-heavy) | profile, power split, SOC/T, efficiencies |
| `26_turbofan_design.py` | Size an A320-class **turbofan** jet: the constraint diagram in T/W, the pyCycle overall-efficiency / TSFC map, and the compressible (wave-drag) polar | engine map table + design summary |
| `27_hydrogen_tms_class_ii.py` | Thermal management of the hydrogen aircraft: Class-I (specific power) vs Class-II (geometric coolant→LH2 and coolant→ram-air heat exchangers, pump, ram-air drag) TMS; design-point selection and rating over the mission (needs CoolProp, ~1.5 min) | rating bar chart |
| `28_reference_atr42.py` | The ATR 42-600 reference aircraft: every input with its origin, sizing at the default and at the real wing loading, comparison with the ATR factsheet (MTOW, OEW, wing area, installed power) | constraint diagram, profile, mass breakdown, model vs factsheet |
| `29_reference_a320.py` | The A320-200 reference (turbofan): inputs, minimum-thrust vs landing-limited design point, comparison with Airbus ACAP / EASA TCDS data (needs the turbofan map) | constraint diagram, profile |
| `30_off_design_mission.py` | Off-design missions: freeze a sized aircraft (OEW, powertrain, battery, tank) and fly it on another range / payload / phi schedule, closing the off-design take-off mass and checking tank, MTOW, battery energy/power and engine limits. `fly_off_design` and `max_battery_phi` are the inner-loop building blocks of a multi-point (design + typical mission) study; works for FC+battery and GT hybrids, Class-I or Class-II batteries (~3.5 min) | trip fuel per nm vs range |

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
