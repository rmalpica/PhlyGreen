# Structures Module

PhlyGreen estimates the airframe (structural / empty) mass at **two fidelity levels**, chosen
with `weight.Class`:

- **Class I** — a regression that returns the empty mass as a fraction of the take-off weight
  (`Systems/Structures/Structures.py`). Fast, no geometry needed; selected with the
  `AircraftType` flag.
- **Class II** — a **FLOPS** component-by-component build-up (`Weight/FLOPS_model.py`), which
  needs a detailed `FLOPSInput`. More inputs, more fidelity.

Both feed the take-off-weight convergence loop in [Weight](weight.md): at each WTO guess the
structural mass is recomputed, so the airframe mass is consistent with the converged design.

---

## Class I — regression model

`Structures.StructuralWeight(WTO)` returns the empty mass [kg] from a correlation selected by
the **`AircraftType`** flag. Four correlations are available:

| `AircraftType` | Empty-mass correlation | Notes |
|----------------|------------------------|-------|
| `'ATR'`        | \(W_{TO}^{-0.06}\,W_{TO}\) | tuned to the ATR42-600 |
| `'DO228'`      | \(0.545\,W_{TO}\)          | tuned to the Dornier 228 |
| `'Jet'`        | \(0.97\,W_{TO}^{-0.06}\,W_{TO}\) | classic jetliner correlation |
| `'TwinTP'`     | \(0.92\,W_{TO}^{-0.05}\,W_{TO}\) | generic twin turboprop |

`AircraftType` only affects this Class-I model; it is ignored when `weight.Class == 'II'`
(FLOPS). If `AircraftType` is unset or unrecognized the model returns nothing, so pick one of
the four values above.

```python
config.aircraft_type = 'TwinTP'    # generic twin turboprop correlation
config.weight_class  = 'I'         # (default)
aircraft.configure(config)
print(aircraft.weight.WStructure)  # structural (empty) mass [kg]
```

---

## Class II — FLOPS component build-up

With `weight.Class == 'II'` the airframe mass is summed from FLOPS component models
(`Weight/FLOPS_model.py`): **wing, fuselage, horizontal & vertical tail, landing gear,
nacelle, paint, system equipment and propeller**. This requires a detailed `FLOPSInput`
dictionary (geometry, load factors, scalers, passenger/crew counts, …) set on the aircraft;
`examples/common.py:atr_flops_input()` is a complete ATR-class example.

```python
aircraft.FLOPSInput = atr_flops_input()    # detailed geometry / FLOPS parameters
cfg = traditional_config()
cfg.weight_class = 'II'
aircraft.configure(cfg)
print(aircraft.weight.WStructure)          # sum of the FLOPS component masses [kg]
```

The FLOPS correlations are imperial internally; use the `Utilities` unit helpers when filling
`FLOPSInput`. Component masses are exposed on `aircraft.weight.AircraftComponents`
(`Wing`, `Fuselage`, `Tail`, `LandingGear`, `Nacelle`, `Paint`, `SystemEquipment`,
`Propeller`).

---

## Choosing a fidelity

Class I is ideal for sweeps / optimization / early trades (one number, no geometry). Class II
captures how geometry and technology factors drive the structural mass, at the cost of many
inputs. Example `15_class_i_vs_class_ii.py` sizes the same aircraft both ways and compares the
structural mass and the resulting WTO.
