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

With `weight.Class == 'II'` the structural mass is summed from FLOPS component models
(`Weight/FLOPS_model.py`): **wing, fuselage, horizontal & vertical tail, landing gear,
nacelles, paint, systems and equipment, propellers** (not for a `'Turbofan'`) and the FLOPS
**propulsion-system and operating items**: fuel system, unusable fuel, engine oil, starter,
engine controls and passenger service. The engines themselves are the powertrain mass. The
equations follow NASA Aviary's transcription of FLOPS (simple wing, transport variants);
`tests/unit/test_flops_components_vs_aviary.py` reproduces the component masses of Aviary's
`large_single_aisle_1` test case within 0.2 %.

The sizing, not the input dictionary, provides the quantities that change with the design
(`Weight/Components/sizing_inputs.py`):

| Quantity | From |
|---|---|
| wing area \(S\) | gross weight × g / design wing loading |
| span \(b\) | \(\sqrt{AR\,S}\), with AR of the aerodynamic model (a `'SPAN'` input is ignored, with a warning) |
| design range | the mission range, in nautical miles |
| design Mach | the cruise constraint (converted from TAS or KCAS if needed) |
| max operating Mach | `FLOPSInput['MAX_MACH']`, or the design Mach |
| SLS thrust per engine | the sized rating for a `'Turbofan'`, `FLOPSInput['ENGINE']['MAX_SLS_THRUST']` [lbf] otherwise |
| landing weight (gear) | FLOPS design landing weight, gross weight × (1 − 4·10⁻⁵ × range [nm]) when subsonic |

The wing mass therefore responds to the aspect ratio: at a fixed wing loading, a larger AR is
a longer span and a heavier wing (`validation/flops_class_ii_reference.py`).

Everything else is a detailed `FLOPSInput` dictionary (geometry, load factor, passenger and
crew counts, fuel capacity, scalers). `examples/common.py` has two complete, sourced examples:
`atr_flops_input()` (ATR 42-600) and `a320_flops_input()` (A320-214); the provenance of each
value is in `trunk/validation/flops_class_ii_reference.md`. Their mass scalers are 1.0.

```python
aircraft.FLOPSInput = atr_flops_input()    # detailed geometry / FLOPS parameters
cfg = traditional_config()
cfg.weight_class = 'II'
aircraft.configure(cfg)
print(aircraft.weight.WStructure)          # sum of the FLOPS component masses [kg]
```

The FLOPS correlations are imperial internally (lb, lbf, ft, ft², inches for the gear oleo
lengths); use the `Utilities` unit helpers when filling `FLOPSInput`. Component masses are
exposed on `aircraft.weight.AircraftComponents` (`Wing`, `Fuselage`, `Tail`, `LandingGear`,
`Nacelle`, `Paint`, `SystemEquipment`, `Propeller`, `OperatingItems`), in lb.

!!! note "Validation"
    `trunk/validation/flops_class_ii_reference.py` sizes both reference aircraft with Class II
    and uncalibrated scalers (all 1.0). Against the published values:

    | | MTOW | OEW | wing area |
    |---|---|---|---|
    | ATR 42-600, real wing loading (341 kg/m²) | +3.6 % | +7.8 % | +3.6 % |
    | A320-200, landing-limited wing loading (583 kg/m²) | −10.8 % | −14.2 % | −2.6 % |

    The A320 engines carry the certified CFM56-5B4 dry weight (EASA TCDS E.003); pylons and
    cargo containers are not modelled. Several ATR inputs (gear oleo lengths, taper ratios,
    nacelle) have no public source and are labelled assumptions or benchmark values in
    `trunk/validation/flops_class_ii_reference.md`. At a fixed wing loading, the take-off
    weight of the ATR 42 is lowest at AR ≈ 11 (the aircraft has 11.1), with a fixed Oswald
    factor.

---

## Choosing a fidelity

Class I is ideal for sweeps / optimization / early trades (one number, no geometry). Class II
captures how geometry and technology factors drive the structural mass, at the cost of many
inputs. Example `15_class_i_vs_class_ii.py` sizes the same aircraft both ways and compares the
structural mass and the resulting WTO.
