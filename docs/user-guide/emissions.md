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
is not free). NOₓ is estimated with one of two models, selected by `EINOx_model`:

- **`'Filippone'`** — a semi-empirical \(EI_{NO_x}\) correlation (default, no extra files);
- **`'GasTurb'`** — a regression surrogate loaded from `EINOx_gasturb.joblib`.

```python
aircraft.configure(hybrid_config())            # carries a ClimateImpactInput
aircraft.MissionType = 'Continue'
aircraft.climateimpact.calculate_mission_emissions()
print(aircraft.climateimpact.mission_emissions) # {'co2','h2o','so4','soot','nox'} in kg
```

The CO₂ intensities are user inputs: `WTW_CO2` (well-to-wake CO₂ of the fuel, kg CO₂/MJ) and
`Grid_CO2` (CO₂ of the electricity, kg CO₂/MJ) — so the emissions accounting is consistent with
the [Well-To-Wake](well-to-wake.md) *energy* accounting.

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
- `"EINOx_model"` — `'Filippone'` or `'GasTurb'`
- `"WTW_CO2"` — well-to-wake CO₂ intensity of the fuel [kg CO₂ / MJ]
- `"Grid_CO2"` — CO₂ intensity of the electricity [kg CO₂ / MJ]

---

## Usage

See example `14_welltowake_and_climate.py`, which prints the per-species mission emissions and
the ATR, and plots the emissions breakdown alongside the design dashboard.

```python
aircraft.MissionType = 'Continue'
aircraft.climateimpact.calculate_mission_emissions()
for species, kg in aircraft.climateimpact.mission_emissions.items():
    print(f"{species}: {float(kg):.2f} kg")
print("ATR:", aircraft.climateimpact.ATR(), "K")
```

---

## References

- Filippone, A. *Comprehensive analysis of transport aircraft flight performance.* (EI\_NOx
  correlation.)
- Dallara, E. S., Kroo, I. M., & Waitz, I. A. *Metrics for comparing the environmental impact
  of aircraft.* (ATR / climate-response framework.)
