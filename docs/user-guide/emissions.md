# Emissions & Climate Impact

The **Climate Impact** module (`ClimateImpact/ClimateImpact.py`) turns a sized design into
emissions and a climate metric. It computes, for the mission (and the fleet over its life):

- **emissions** of CO₂, H₂O, SO₄, soot and NOₓ;
- the **radiative forcing** (RF) of every relevant species — CO₂, H₂O, SO₄, soot, CH₄,
  short- and long-lived O₃, and contrail cirrus (AIC);
- the **temperature response** ΔT(t) from convolving the forcing with a climate kernel;
- the **Average Temperature Response** `ATR(H)` over a time horizon — the headline metric.

It is enabled by supplying a `ClimateImpactInput` (typed: `ClimateImpactConfig`).

---

## 1. Mission emissions

CO₂, H₂O, SO₄ and soot scale with the **fuel burned** through fixed emission indices; CO₂ also
picks up the **electricity** contribution via the grid intensity (so a hybrid's battery energy
is not free). The combustion pollutants NOₓ (and, with the surrogate, CO and UHC) are estimated
with one of two models, selected by `EINOx_model`:

- **`'Filippone'`** — a semi-empirical \(EI_{NO_x}\) correlation (default, no extra files);
- **`'Surrogate'`** — a packaged **emission‑index response surface**, which integrates
  operating‑point‑dependent \(EI_{NO_x}\), \(EI_{CO}\) and \(EI_{UHC}\) over the mission.
  See [Surrogate Models](surrogate-models.md#4-gasturbine-emissions-surrogate) for how it is built
  (pyCycle deck → Cantera CRN → EI map).

!!! note "Two artifacts, selected by configuration"
    A combustor calibration is engine‑specific and does **not** transfer between engine classes,
    so two maps ship and `ClimateImpact` picks by `Configuration`
    (`emissions_surrogate.default_model_path`):

    | configuration | artifact | third coordinate | NOₓ |
    |---|---|---|---|
    | `Traditional`, `Hybrid` | `Emission_Model_PW127.pkl` | shaft power over lapsed rating, \(P_{shaft}/(P_{rated}\,\delta(h))\) | certification‑**anchored** |
    | `Turbofan` | `Emission_Model_Turbofan.pkl` | **thrust** over lapsed thrust, \(F/(F_{00}\,\lambda_T(h,M))\) | **unanchored** (predicted) |

    The turboprop NOₓ is anchored because an equal‑split CRN cannot reproduce a *staged*
    turboprop combustor. The Cantera CRN is natively a CFM56 single‑annular model, so for the
    turbofan its raw NOₓ is reported: at the CRN's own four ICAO LTO states it gives +16 %
    (take‑off), +29 % (climb), +19 % (approach). That is a prediction with a stated error, not a
    level asserted from certification data.

    Each map is read at the coordinate it was generated at
    (`ClimateImpact._surrogate_load_fraction`):

    - **Turboprop.** The PW127 deck of `emissions_pipeline/pw127_partpower.py` is run at a gross
      power \(G(PC)\,\delta(h)\), with \(\delta\) the ISA pressure ratio, so \(PC\) is the
      gas‑turbine **shaft** power over the rated power lapsed by \(\delta\). `ClimateImpact`
      forms the same quantity: `PRatio[1] * P / (engineRating * delta(h))`. In a `Hybrid` only
      the thermal share passes through the combustor, so the battery share is excluded.
      `engineRating` is rated with `Powertrain.PowerLapse`. With the Class‑II gas‑turbine
      map that lapse is \(\delta\) itself, so the fraction reaches exactly 1 at the sizing
      point and never exceeds it. With constant efficiencies the rating uses Ruijgrok's
      \((\rho/\rho_0)^{0.75}\), which lapses less than \(\delta\): at cruise altitude the
      fraction then exceeds 1 (132 of 239 points, up to 1.75, on the constant‑efficiency
      turboprop of `examples/common.py`) and is clipped to the map edge, i.e. read at the
      full‑power indices. \(\delta\) stays the coordinate either way, because it is how the
      map was generated.
    - **Turbofan.** The fraction is taken against the **lapsed** available thrust
      \(F/(F_{00}\lambda_T(h,M))\), the map's thrust fraction, not against the sea‑level
      rating — otherwise the load would be understated everywhere above the ground and the map
      read at the wrong place.

    Queries outside a map box (below \(PC = 0.3\), Mach or altitude outside the grid) are
    clipped to its edge.

    Until this coordinate was fixed, the turboprop map was read at the propulsive power over the
    sea‑level rating, i.e. at part power. On the turboprop reference of `examples/common.py`
    this gave 8.1 kg of NOₓ instead of 22.2 kg (Filippone: 21.8 kg) for the flown mission.

```python
aircraft.configure(hybrid_config())            # carries a ClimateImpactInput
aircraft.climateimpact.calculate_mission_emissions()
print(aircraft.climateimpact.mission_emissions) # {'co2','h2o','so4','soot','nox'} in kg
print(aircraft.climateimpact.ground_emissions)  # ground-segment share of fuel and NOx
```

**Ground segments.** Taxi‑out, the take‑off run and taxi‑in are not in the flown profile, but
their fuel is in `weight.Wf` (see [Mission](mission.md)). Both NOₓ models add them, so NOₓ (CO,
UHC) and CO₂ cover the same fuel. Each leg is taken at the fuel flow and duration that
`Mission._ground_segments` used (`mission._ground_fuel_legs_out/_in`), at the take‑off
condition:

- **Filippone**: climb‑out coefficients for the take‑off run, idle coefficients for taxi;
- **Surrogate**: the map at the leg's load fraction (taxi at Mach 0). Taxi runs at 7 % of the
  take‑off power by default, below the \(PC = 0.3\) edge of both maps, so it is read at the
  map edge (approach indices): taxi NOₓ is overestimated and taxi CO underestimated relative
  to an idle index.

On the turboprop reference the ground legs burn 42 kg of the 1,939 kg of fuel and add about
0.5 kg of NOₓ; on the turbofan reference 200 kg of 21,216 kg, about 2–3 kg of NOₓ.

**Mission type and engine count.** `build_aircraft` sets `aircraft.MissionType = 'Continue'`
(the continuous mission solution, which both NOₓ paths integrate), and `ClimateImpact` assumes
it when the attribute is missing. The Filippone correlation is per engine; the engine count is
`powertrain.n_engines` (2 if the powertrain has none).

The CO₂ intensities are user inputs: `WTW_CO2` (upstream CO₂ of the fuel, kg CO₂ per MJ of
`EnergyInput['Ef']`) and `Grid_CO2` (CO₂ of the electricity, kg CO₂/MJ). This keeps the
emissions accounting consistent with the [Well-To-Wake](well-to-wake.md) *energy* accounting.

The emission indices depend on the fuel:

| Species | Jet-A [kg/kg fuel] | Hydrogen fuel cell [kg/kg H₂] |
|---|---|---|
| CO₂ (tank-to-wake) | 3.16 | 0 |
| H₂O | 1.26 | 8.94 (stoichiometric, \(M_{H_2O}/M_{H_2}\)) |
| SO₄ | 2·10⁻⁴ | 0 |
| soot | 4·10⁻⁵ | 0 |
| NOₓ | Filippone correlation or EI surrogate | 0 (no combustion) |

- **Fuel mass.** For hydrogen the burnt mass comes from the mission energy. The loaded mass
  `weight.Wf` also carries the sizing margin `h2_fuel_margin`, which is not burnt.
- **Upstream CO₂.** It is `WTW_CO2 × m_fuel × Ef`. With `Ef` set to the hydrogen HHV,
  `WTW_CO2` must be given per MJ of HHV.
- **Grid CO₂.** It is counted for every configuration that draws battery energy (`Hybrid` and
  `FuelCellBattery`).
- **Contrail term.** The contrail term (AIC, §2) keeps its kerosene-derived parametrisation.
  For a fuel cell it is a placeholder, not a model.

---

## 2. Radiative forcing and CO₂-equivalence

Each species' forcing is computed from its annual emissions and normalized by the forcing of a
CO₂ doubling, \(RF_{2\times CO_2} = 3.7~\mathrm{W/m^2}\), and weighted by its efficacy — so all
contributions are expressed in **CO₂-equivalent** terms and can be summed:

\[
RF^{*}(t) = \sum_i RF^{*}_i(t), \qquad
i \in \{CO_2, H_2O, SO_4, soot, CH_4, O_{3s}, O_{3l}, AIC\}.
\]

Short-lived species (NOₓ-driven O₃/CH₄, contrails) depend on the **cruise altitude**: the
module weights the AIC and ozone forcings by where the mission spends its time, using a
mission-altitude distribution.

---

## 3. Temperature response and ATR

The surface temperature response is the convolution of the total forcing with the climate
impulse-response kernel \(G_T\):

\[
\Delta T(t) = \int_0^t RF^{*}(t')\,G_T(t - t')\,\mathrm{d}t' .
\]

The fleet scenario is set by three inputs: **`N`** flights per year over **`Y`** years of
operation, evaluated over a time horizon **`H`** [years]. The headline metric is the
**Average Temperature Response**:

\[
ATR(H) = \frac{1}{H}\int_0^{H} \Delta T(t)\,\mathrm{d}t .
\]

```python
atr = aircraft.climateimpact.ATR()             # [K]
```

---

## Inputs

`ClimateImpactInput` (typed: `ClimateImpactConfig`):

- `"H"` — time horizon for ATR [years]
- `"N"` — number of flights per year
- `"Y"` — number of operating years
- `"EINOx_model"` — `'Filippone'` or `'Surrogate'` (see [Surrogate Models](surrogate-models.md))
- `"WTW_CO2"` — well-to-wake CO₂ intensity of the fuel [kg CO₂ / MJ]
- `"Grid_CO2"` — CO₂ intensity of the electricity [kg CO₂ / MJ]

---

## Usage

See example `14_welltowake_and_climate.py`, which prints the per-species mission emissions and
the ATR, and plots the emissions breakdown alongside the design dashboard.

```python
aircraft.climateimpact.calculate_mission_emissions()
for species, kg in aircraft.climateimpact.mission_emissions.items():
    print(f"{species}: {float(kg):.2f} kg")
print("ATR:", aircraft.climateimpact.ATR(), "K")
```

---

## References

- Filippone, A. *Comprehensive analysis of transport aircraft flight performance.* (EI\_NOx
  correlation.)
- Dallara, E. S., Kroo, I. M., & Waitz, I. A. *Metric for Comparing Lifetime average Climate Impact of Aircraft.* (ATR / climate-response framework.)
