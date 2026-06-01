# Configuration & Workflow

PhlyGreen is driven by **typed configuration objects** and a small set of entry points.
This page is the practical "how do I set up and run a design" reference.

## Build an aircraft

```python
import PhlyGreen as pg
aircraft = pg.build_aircraft()     # all subsystems created and cross-linked
```

## Describe the design with a typed config

`PhlyGreen.config` provides validated dataclasses. `AircraftConfig` bundles the flags with
the input sections:

```python
from PhlyGreen.config import (
    AircraftConfig, MissionConfig, EnergyConfig, AerodynamicsConfig,
    ConstraintsConfig, StagesConfig, Segment,
)

config = AircraftConfig(
    configuration='Traditional',   # 'Traditional' | 'Hybrid' | 'Hydrogen' | 'FuelCellBattery'
    aircraft_type='ATR', weight_class='I',
    mission=MissionConfig(range_mission=750, range_diversion=220, beta_start=0.97,
                          payload_weight=4560, crew_weight=500),
    energy=EnergyConfig(Ef=43.5e6, contingency_fuel=130, eta_gearbox=0.96,
                        eta_gas_turbine=0.22, eta_propulsive=0.9,
                        specific_power_powertrain=[3900, 7700]),
    aerodynamics=AerodynamicsConfig(take_off_cl=1.9, landing_cl=1.9, minimum_cl=0.2, cd0=0.017,
                                    analytic_polar={'type': 'Quadratic',
                                                    'input': {'AR': 11, 'e_osw': 0.8}}),
    constraints=ConstraintsConfig(disa=0.0, phases={...}),
    mission_stages=StagesConfig(segments=[Segment('Takeoff', phi=0.0), ...]),
    diversion_stages=StagesConfig(segments=[...]),
)
```

Validation happens on construction (e.g. efficiencies in (0, 1], φ in [0, 1], positive
ranges), so mistakes are caught immediately. The ready-made baselines in
`examples/common.py` (`traditional_config()`, `hybrid_config()`, `hydrogen_config()`,
`fuelcell_battery_config()`) are the easiest starting point — copy and tweak.

### Changing an input

Every field is a plain attribute:

```python
config.mission.range_mission = 600          # nm
config.energy.eta_gas_turbine = 0.30
for seg in config.mission_stages.segments:  # raise the cruise battery share
    if seg.name == 'Cruise':
        seg.phi_end = 0.5
```

The legacy dict API still works: `ReadInput`/`DesignAircraft` accept either config objects
or the original dictionaries (each config has `to_dict`/`from_dict`).

## Size it and read the results

```python
aircraft.configure(config)        # validate inputs + run the full sizing loop
results = aircraft.results()       # an AircraftResults dataclass
print(results.WTO, results.Wf, results.WingSurface)
results.to_dict()                  # JSON-serializable
```

## Outer loops (optimization / UQ / sweeps)

`PhlyGreen.api` gives a pure, stateless evaluation:

```python
results = pg.run_design(config)                     # fresh aircraft per call
results = pg.evaluate(config, apply, x)             # apply(config_copy, x) then design
```

`apply(cfg, x)` encodes a parameter set onto a copy of the baseline (the baseline is never
mutated), so it is safe to call in a loop or in parallel. See `examples/10`–`13`.

## Post-processing

`PhlyGreen.postprocess` extracts and plots the outcomes:

```python
from PhlyGreen import postprocess as pp
pp.plot_constraint_diagram(aircraft)
pp.plot_mission_profile(aircraft)      # altitude / speed / phi vs time
pp.plot_energy_timeseries(aircraft)    # fuel / battery energy / SOC vs time
pp.plot_mass_breakdown(aircraft)
ts = pp.mission_timeseries(aircraft)   # raw arrays
```

See the runnable notebooks in `trunk/notebooks/`.
