# Class-II (FLOPS) structural model: inputs and provenance

Inputs of `atr_flops_input()` and `a320_flops_input()` (`trunk/examples/common.py`), used by
`flops_class_ii_reference.py`. Every value is either taken from a source listed below, a
FLOPS/Aviary default, a value of an Aviary benchmark aircraft, or an assumption, and it is
labelled as such in the code. All mass scalers are 1.0: the model is not calibrated to the
reference aircraft.

The span, wing area, design range, design (cruise) Mach number and gross weight are not
inputs: they come from the sizing (`PhlyGreen/Weight/Components/sizing_inputs.py`). The span is
`sqrt(AR * S)`, with AR the aspect ratio of the aerodynamic model.

## Implementation check

The component equations follow NASA Aviary's transcription of FLOPS
(`aviary/subsystems/mass/flops_based`, simple wing, transport variants).
`tests/unit/test_flops_components_vs_aviary.py` feeds them the inputs of Aviary's
`large_single_aisle_1` FLOPS test case and reproduces its component masses within 0.2 %: wing
shear/control and miscellaneous terms, fuselage, tails, nacelles, landing gear (at the FLOPS
design landing weight), every system and equipment item, fuel system, unusable fuel, engine
oil, starter, engine controls and passenger service. Not compared: the wing bending material
(the Aviary case uses the detailed wing) and the paint (the case overrides the wetted areas).

## Sources

| Key | Source | Class |
|---|---|---|
| FS | ATR, *ATR 42-600* factsheet (2020), https://www.atr-aircraft.com/wp-content/uploads/2020/07/Factsheets_-_ATR_42-600.pdf | primary |
| TC-ATR | EASA TCDS EASA.A.084 ATR 42 / ATR 72, Issue 14, 23 Feb 2026, https://www.easa.europa.eu/en/downloads/7358/en | primary |
| TE | EASA TCDS IM.E.041 PW100 series, Issue 07, 20 Dec 2023, https://www.easa.europa.eu/en/downloads/7725/en | primary |
| AC | Airbus, *A320 Aircraft Characteristics – Airport and Maintenance Planning*, Rev. 46, Jul 01/26 | primary |
| TC-A320 | EASA TCDS EASA.A.064, Issue 12 (see `a320_reference.md`) | primary |
| TE-CFM | EASA TCDS E.003 CFM56-5B and -5C, Issue 06, 9 Jan 2023, https://www.easa.europa.eu/en/downloads/7797/en | primary |
| AB | Airbus A320ceo product page, "Dimensions", https://aircraft.airbus.com/en/aircraft/a320-family/a320ceo | primary (web) |
| CS | 14 CFR 25.337(b) (limit manoeuvring load factor) and 25.303 (factor of safety 1.5) | regulation |
| JSR | Jenkinson, Simpson & Rhodes, *Civil Jet Aircraft Design*, Data A, Table 1 (A320-200 column: CFM56-5A3, 73.5 t variant) | secondary |
| LED | Lednicer, *The Incomplete Guide to Airfoil Usage* (Apr 2026) | secondary |
| HAW | HAW Hamburg aircraft database (Scholz group); ATR tail and fuselage values cite the ATR 42 AFM (1995), not verified | secondary |
| DEF | FLOPS/Aviary default value (`aviary/variable_info/variable_meta_data.py`) | default |
| LSA | Aviary `large_single_aisle_1` FLOPS model (a 181,200 lb single-aisle transport) | benchmark value |
| A | assumption, no source found | assumption |

## ATR 42-600

| Input | Value | Key |
|---|---|---|
| ultimate load factor | 3.86 (1.5 × 2.57 at 41,005 lb MTOW) | CS |
| wing t/c | 0.155 (mean of 18 % root, 13 % tip) | LED |
| wing taper ratio | 0.54 | A |
| wing sweep | 0° | A |
| composite fraction, aeroelastic tailoring, strut bracing | 0 | DEF |
| horizontal tail area / taper | 11.73 m² / 0.54 | HAW / A |
| vertical tail area / taper | 12.48 m² / 0.33 | HAW / LSA |
| fuselage length | 22.67 m (overall length of the aircraft) | FS |
| fuselage max width / height | 2.87 / 2.63 m | HAW |
| passenger compartment length | 0.7 × 22.67 m | A |
| main / nose gear oleo length | 102 / 67 in | LSA (no ATR value found) |
| nacelle diameter / length | 0.8 m / 2.13 m | A (PW127M width 0.72 m, TE) / TE |
| seats | 48, single class | FS |
| flight crew | 2 | TC-ATR |
| engines | 2, wing-mounted | TC-ATR |
| SLS thrust per engine | 26,000 N / 2 = 2,923 lbf | A |
| propeller | 6 blades, 12.9 ft | FS |
| propeller shaft power | 2,400 shp per engine | FS |
| max fuel | 4,500 kg | FS |
| fuel tanks / density | 7 / 6.7 lb/US gal | DEF |
| max operating Mach | not given: the design cruise Mach is used | – |
| control surface area ratio, paint, hydraulic pressure | 0.1, 0.037 lb/ft², 3,000 psi | LSA |

## A320-214 (CFM56-5B4), WV017

| Input | Value | Key |
|---|---|---|
| ultimate load factor | 3.75 (1.5 × 2.5) | CS |
| wing taper ratio / sweep | 0.240 / 25° | JSR |
| wing t/c | 0.13 (mean of 15 % root, 11 % tip) | LED |
| composite fraction, aeroelastic tailoring, strut bracing | 0 | DEF |
| horizontal tail area / taper | 31.00 m² / 0.256 | JSR |
| vertical tail area / taper | 21.50 m² / 0.303 | JSR |
| fuselage length / width / height | 37.57 / 3.95 / 4.14 m | AC (2-2-0) |
| passenger compartment length | 27.51 m (cabin length) | AB |
| main / nose gear length | 2,868.7 / 1,957.0 mm (extended, pivot to axle) | AC (2-9-0) |
| nacelle diameter / length | 2.37 / 4.44 m (CFM56-5A3) | JSR |
| seats | 150, two class (12 + 138) | AC (2-4-1) |
| flight crew | 2 | TC-A320 |
| engines | 2, wing-mounted | TC-A320 |
| thrust reversers | yes (fan reverser cowls, CFM56) | AC (2-12-0) |
| engine mass | thrust-to-weight 4.99: dry weight 2,454.8 kg at 12,010 daN take-off thrust (set by `flops_class_ii_reference.py`; `turbofan_config()` keeps its unsourced 5.5) | TE-CFM |
| max operating Mach | 0.82 | TC-A320 |
| usable fuel | 24,209 l at 0.785 kg/l (19,004 kg) | AC (2-1-1) |
| fuel tanks | 3 (two wing tanks, centre tank) | AC (2-1-1) |
| control surface area ratio, paint, hydraulic pressure | 0.1, 0.037 lb/ft², 3,000 psi | LSA |

## Known limits of the comparison

- The ATR 42-600 has no public Airport Planning document: its gear, nacelle, taper and cabin
  inputs are assumptions or benchmark values. The gear mass scales with the oleo length to
  the power 0.43.
- The turbofan engine mass is the powertrain mass `thrust / (g * Engine Thrust to Weight)`,
  with the certified dry weight of the CFM56-5B4 (TCDS E.003). Pylons and cargo containers
  are not modelled.
- The OEW of the A320 reference (42,600 kg) is a secondary, operator-dependent figure
  (`a320_reference.md`).
- The aerodynamic model keeps a fixed Oswald factor and Cd0, so the aspect-ratio sweep shows
  the structural side of the trade only.
