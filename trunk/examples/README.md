# PhlyGreen examples

Small, self-contained scripts for learning the code. Each is heavily commented and meant to
be **read, run, and tweaked**.

## Setup

Install the package (editable) and run the examples from the `trunk/` directory:

```bash
pip install -e .          # from trunk/  (or: pip install -e ./trunk from the repo root)
cd trunk
python examples/01_design_traditional.py
```

`common.py` holds the baseline aircraft configurations the examples build on — start there,
change a number, and re-run an example to see the effect.

## Capability tour

| Script | What it shows |
|--------|---------------|
| `01_design_traditional.py` | Build → configure → size a fuel-only aircraft; read results |
| `02_hybrid_with_battery.py` | A parallel hybrid-electric design with a battery pack |
| `03_typed_config_and_results.py` | Typed config, validation, config↔dict, results as a dict |
| `04_flight_profile_and_custom_segment.py` | Query altitude/speed/phi(t); register a new segment type |
| `05_powertrain_graph_and_efficiency_models.py` | Power-balance graph; operating-point-dependent efficiencies; a fuel-cell+battery architecture |
| `06_utilities_atmosphere_and_speeds.py` | ISA atmosphere and Mach/TAS/CAS/EAS conversions |
| `14_welltowake_and_climate.py` | Well-to-wake source energy, mission emissions, climate impact (ATR) |
| `15_class_i_vs_class_ii.py` | Class-I vs Class-II structures (FLOPS) and battery models |
| `16_class_ii_propulsion_sizing.py` | Size the Class-II gas turbine / electric motor (nominal power) with over/under-size check |
| `20_hydrogen_fuel_cell.py` | Size a hydrogen fuel-cell aircraft and fly the full mission; polarization curve |
| `21_hydrogen_design_voltage_sweep.py` | Sweep the fuel-cell design voltage; find the take-off-weight optimum |
| `22_hydrogen_tank.py` | Size the cryogenic LH2 tank and track its pressure/mass/venting over the mission (needs CoolProp) |
| `23_fuelcell_battery_hybrid.py` | Hybridize a fuel cell with a battery; sweep the battery power share |

## Outer-loop applications

These use the stateless API `pg.run_design(config)` and `pg.evaluate(base, apply, x)`, which
run one independent design per call (safe to loop or parallelize).

| Script | What it shows |
|--------|---------------|
| `10_parameter_sweep.py` | Sweep design range; plot WTO and block fuel |
| `11_optimization.py` | Minimize block fuel over cruise Mach (SciPy; `pymoo` note inside) |
| `12_uncertainty_quantification.py` | Monte-Carlo propagation of input uncertainty (NumPy; `chaospy` note inside) |
| `13_payload_range.py` | A 2-D payload×range sweep / contour |

The outer-loop examples deliberately use only SciPy/NumPy so they run anywhere; each file
notes how the same objective/model plugs into the production tools (`pymoo`, `chaospy`).
Figures, when produced, are written to `examples/_output/`.
