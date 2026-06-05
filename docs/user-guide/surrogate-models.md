# Surrogate Models

Several of PhlyGreen's Class‑II component models are **surrogates**: fast, ready‑to‑run response
surfaces (or compact physics models) fitted *offline* from a high‑fidelity tool, then shipped with
the package as small artifacts that load at run time with **no heavy dependency**. This page
collects, in one place, what is behind the four that matter most:

| Surrogate | What it predicts | Built from | Runtime module |
|-----------|------------------|------------|----------------|
| **Gas‑turbine efficiency** | thermal efficiency vs altitude / Mach / power fraction | pyCycle turboshaft deck | `gas_turbine_surrogate.py` |
| **Electric motor** | efficiency vs operating point | d‑q machine physics | `EM.py` |
| **Propeller** | efficiency + pitch governor | blade‑element data (RBF) | `propeller_surrogate.py` |
| **Gas‑turbine emissions** | EI of NOₓ / CO / UHC vs operating point | pyCycle deck → Cantera CRN | `emissions_surrogate.py` |

The common design idea is the **offline / online split**: an expensive physics chain is run once on a
grid (needing pycycle/openmdao, Cantera, pandas…), the result is fitted to a cheap response surface
(scipy `Rbf` + a `StandardScaler`), and the fitted artifact is what the package carries. At run time
the surrogate is just a few matrix multiplies, so it can be evaluated at *every* mission time step
and inside an optimisation loop. Each one is also a drop‑in `EfficiencyModel`
(`Systems/Powertrain/efficiency.py`), so it slots into the powertrain
[component graph](powertrain.md) without touching the solver.

A recurring trick is the **universal (size‑independent) map**: the surrogate is trained for a single
reference engine as a function of the *power fraction* \(P_{\text{req}}/P_{\text{avail}}\) rather than
absolute power, so one map serves engines of any size and the size effect is reintroduced separately
by a calibrated scaling law. The emission **index** is universal in the same sense — it depends only on
the operating point, not the engine size.

---

## 1. Gas‑turbine efficiency surrogate

**Runtime:** `Systems/Powertrain/gas_turbine_surrogate.py` (`GasTurbineResponseSurface`).
**Trainer:** `train_gas_turbine_surrogate.py`, from the pyCycle turboshaft deck
`Systems/Powertrain/data/Single_spool_GT.py`.

A **universal RBF response surface** maps

\[
(\text{altitude [ft]},\ \text{Mach},\ \text{power fraction}) \;\longrightarrow\; \eta_{\text{th}}
\]

for one reference engine. The grid of operating points is run through the pyCycle deck offline; the
efficiencies are fitted with a multiquadric `Rbf` on inputs normalised by a `StandardScaler`. At run
time three things happen, in order:

1. **Power lapse** — the available shaft power falls with altitude via the ISA pressure ratio,
   \(P_{\text{avail}} = P_{\text{design}}\,\delta(h)\);
2. **Read the map** — efficiency is evaluated at the current power fraction
   \(P_{\text{req}}/P_{\text{avail}}\);
3. **Size scaling** — the map is for the reference engine, so the efficiency penalty of a *smaller*
   engine is added back with a calibrated law,

\[
1-\eta \;=\; \bigl(1-\eta_{\text{ref}}\bigr)\left(\frac{P_{\text{ref}}}{P_{\text{design}}}\right)^{\!n},
\]

where the exponent \(n\) is fitted once (`calibrate_scaling_exponent`) from a small embedded dataset of
real turboshaft SFC‑vs‑power points and cached. This is why a single map can size engines from a few
hundred kW to several MW.

Because the model works as a *percentage of a fixed nominal power*, that nominal
(`GT Design Power`) must be chosen **before** the mission; after sizing,
`powertrain.report_class_ii_sizing()` flags whether the engine is power‑limited at altitude or
oversized. See example `16_class_ii_propulsion_sizing.py`.

> The size scaling moves the efficiency level but **not** the emission indices — see §4.

---

## 2. Electric‑motor model

**Runtime:** `Systems/Powertrain/EM.py` (`ElectricMotor`), wrapped as `MotorEfficiencyModel`.

Strictly a **physics model** rather than a fitted surrogate, but it plays the same Class‑II role: given
the motor's design power, voltage and rpm it returns efficiency as a function of the operating point
from a **d‑q machine** loss breakdown — copper (\(I^2R\)), iron and switching losses — so the battery
power ratio changes with load instead of being a constant. Like the gas turbine it needs a fixed
nominal (design) power, voltage and rpm, set before the mission
(`EM Design Power`, `EM Design Voltage`, `EM Design RPM`). It is the worked Class‑II example for the
electric path and can be plotted as an efficiency map in
`05_powertrain_graph_and_efficiency_models.py`.

---

## 3. Propeller surrogate

**Runtime:** `Systems/Powertrain/propeller_surrogate.py` (`PropellerSurrogate`).
**Data:** `Systems/Powertrain/data/propeller_data_rbf.csv` (power, altitude, airspeed, rpm, pitch,
efficiency).

A **data‑trained RBF** propeller model with two coupled maps fitted from blade‑element data:

- a **pitch governor** — the blade pitch needed to hold a *target rpm*,
  \((P,\ h,\ V,\ \text{rpm}) \to \beta\);
- an **efficiency** map — \((P,\ h,\ V,\ \beta,\ \text{rpm}) \to \eta_{\text{prop}}\).

Both are multiquadric `Rbf` surfaces on min‑max‑normalised features; the governor lets the model
behave like a real constant‑speed propeller (you ask for an rpm, it finds the pitch, then reads the
efficiency at that pitch). It is the data‑driven alternative to the analytic **Hamilton‑Standard**
method (`propeller_hamilton.py` + `propeller_hamilton_tables.py`); select it with
`'Eta Propulsive Model': 'Surrogate'` (needs pandas). See [Powertrain](powertrain.md) for the
selection mechanics.

---

## 4. Gas‑turbine emissions surrogate

**Runtime:** `Systems/Powertrain/emissions_surrogate.py` (`EmissionSurrogate`).
**Pipeline:** `Systems/Powertrain/emissions_pipeline/` (reproducible, offline).

A **certification‑anchored** response surface for the gas‑turbine emission *indices*:

\[
(\text{altitude [ft]},\ \text{Mach},\ \text{power fraction})\;\longrightarrow\;
\bigl(EI_{NO_x},\ EI_{CO},\ EI_{UHC}\bigr)\ \ [\text{g/kg fuel}].
\]

It is built for the **PW127** turboprop and is engine‑size‑independent (it predicts the index, not the
mass), mirroring the GT efficiency map. CO and UHC are fitted in \(\log_{10}\) because they span orders
of magnitude across the power range.

### The two‑stage physics chain

```
(alt, Mach, power)  ──pyCycle PW127 deck──▶  combustor inlet state (T3, P3, FAR, ṁ_air)
                                                       │
                                                       ▼
                                         Cantera CRN  ──▶  emission indices  ──▶  RBF surrogate
```

1. **Engine deck (`pw127_deck.py`, `pw127_partpower.py`).** The two‑shaft turboshaft deck
   (`data/Single_spool_GT.py`) is re‑tuned to the PW127 (OPR 14.7; rated power set so the SLS take‑off
   fuel flow matches the FOCA/EASA certification). A calibrated gas‑generator power schedule \(G(f)\)
   makes the deck reproduce the certified **part‑power** fuel flow (idle/approach). The deck exports the
   combustor inlet state — temperature \(T_3\), pressure \(P_3\), fuel‑air ratio FAR, air mass flow — over
   a flight‑envelope grid (Mach ≥ 0.1; the Mach = 0 static point is a deck convergence artifact and is
   dropped).
2. **Chemical Reactor Network (`crn/`).** A Cantera CRN — a 9‑PSR primary zone
   plus secondary and dilution zones, with a Luche kerosene surrogate mechanism and an evaporation model —
   is run at each combustor state to produce \(EI_{NO_x},\ EI_{CO},\ EI_{UHC}\). It is calibrated to the
   PW127 with a richer primary‑zone air fraction `ARPZ = 0.24` (vs the CFM56 baseline 0.31), found by
   `calibrate_crn_pw127.py` scanning the four ICAO LTO modes.

### NOₓ certification anchor

The CRN reproduces PW127 **CO** well, but its NOₓ is too peaky for this network structure (a physically
calibrated NOₓ would need a staged/pilot primary zone — future work). So NOₓ keeps the CRN's
*altitude / Mach / power shape* but is rescaled to the certified value at the sea‑level modes:

\[
EI_{NO_x}(\text{op}) \;=\; EI_{NO_x}^{\text{CRN}}(\text{op})\cdot k(PC),
\qquad
k(PC)=\frac{EI_{NO_x}^{\text{ICAO}}(PC)}{\overline{EI_{NO_x}^{\text{CRN,SLS}}}(PC)} .
\]

CO and UHC come straight from the CRN. The result is an EI map that **matches the ICAO certification by
construction** at the in‑range modes while carrying physically sensible trends across the rest of the
flight envelope.

### Validation and trends

The pipeline ships two diagnostic plots (`emissions_pipeline/validation_plots.py`):

- **`validation_vs_icao.png`** — surrogate \(EI_{NO_x}/EI_{CO}\) at the LTO modes against the FOCA/EASA
  PW127 ICAO data. NOₓ matches by construction (the anchor); CO is order‑of‑magnitude correct and rises
  at low power as expected, slightly over‑predicting at approach. Idle (taxi, \(PC = 0.07\)) lies **below
  the modelled flight‑envelope range** \(PC \in [0.3,\,1.0]\) and is flagged as out of range.
- **`ei_vs_combustor_state.png`** — EI vs the combustor inlet state \((T_3, P_3, \text{FAR})\). The
  physics reads correctly: NOₓ **rises** with \(T_3\), \(P_3\) and FAR (thermal/Zeldovich), while CO and
  UHC are high only at the low‑temperature, low‑power end and fall steeply as combustion completes.

> **Scope.** NOₓ is *certification‑anchored*, not physically calibrated; the model range is
> \(PC \in [0.3,\,1.0]\) (idle is below it); soot is documented for a future phase
> (`EMISSIONS_MODEL_NOTES.md`). The emission index is engine‑size‑independent, so the GT efficiency
> size‑scaling of §1 does not affect it.

### Using it

The surrogate feeds the [climate‑impact](emissions.md) model: set `EINOx_model = 'Surrogate'` and the
NOₓ/CO/UHC are integrated over the mission from the response surface instead of the Filippone NOₓ
correlation. You can also query it directly:

```python
from PhlyGreen.Systems.Powertrain.emissions_surrogate import EmissionSurrogate
es = EmissionSurrogate()                      # packaged PW127 artifact
ei = es.predict_op(altitude_ft=20000, mach=0.45, power_fraction=0.8)
print(ei)   # {'EINOX': ..., 'EICO': ..., 'EIUHC': ...}  g/kg fuel
```

See example `24_gt_emissions_surrogate.py` (EI at operating points + mission emissions
Surrogate vs Filippone), the emission time history in `16_class_ii_propulsion_sizing.py`, and the
[Emissions & Climate Impact](emissions.md) page.

### Regenerating the surrogate

The shipped `.pkl`/`.csv` need no heavy dependencies; *regenerating* needs `pycycle`, `openmdao` and
`cantera`:

```bash
cd PhlyGreen/Systems/Powertrain/emissions_pipeline
python pw127_partpower.py        # -> pw127_crn_inputs_corrected.csv   (pyCycle deck)
python build_pw127_surrogate.py  # -> ../data/PW127_Emission_Map.csv + Emission_Model_PW127.pkl (CRN + fit)
python validation_plots.py       # -> validation_vs_icao.png + ei_vs_combustor_state.png
```

See `emissions_pipeline/README.md` for the full provenance and `EMISSIONS_MODEL_NOTES.md` for the
design history and the soot groundwork.


