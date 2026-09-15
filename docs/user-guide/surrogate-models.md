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
| **Turbofan** | overall efficiency, TSFC and thrust lapse vs operating point | pyCycle high‑bypass turbofan deck | `turbofan_surrogate.py` |

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

## 1b. Turbofan surrogate

**Runtime:** `Systems/Powertrain/turbofan_surrogate.py` (`TurbofanResponseSurface`).
**Trainer:** `train_turbofan_surrogate.py`, from the vendored pyCycle high‑bypass turbofan
deck `Systems/Powertrain/data/HBTF_turbofan.py`.

Three surfaces from one sweep:

\[
(\text{altitude [ft]},\ \text{Mach},\ \text{thrust fraction}) \longrightarrow
(\eta_o,\ \mathrm{TSFC}), \qquad
(\text{altitude [ft]},\ \text{Mach}) \longrightarrow \lambda_T
\]

where \(\eta_o = F V /(\dot m_f\,\mathrm{LHV})\) is the **overall** efficiency and
\(\lambda_T\) the full‑throttle thrust lapse \(F_\max(h,M)/F_{00}\).

**Why overall efficiency rather than TSFC.** The powertrain graph normalises everything to
propulsive power, so the turbofan is a single node and \(P_f/P_p = 1/\eta_o\) drops straight
into the existing fuel closure. That closure *is* a TSFC law: \(\mathrm{TSFC} = V/(\eta_o\,
\mathrm{LHV})\) — the same information, exactly, not an approximation. TSFC is fitted
alongside anyway so results can be read against published engine data.

**The grid follows the flight envelope, not a rectangle.** The shipped map holds **72 points**
over **18 flight conditions** (4 thrust fractions each), and each Mach number carries only the
altitudes at which it is actually flown. Sweeping a rectangle instead is what makes a turbofan
deck look unreliable: Mach 0.2 at 39,000 ft is not a condition any aircraft flies, the engine is
effectively windmilling there, and the off‑design solve has no physical solution to find. The
sweep also marches in **altitude at constant Mach**, warm‑starting each solve from the previous
one — the continuation path is what gets the high‑altitude points to converge at all.

**Validated to 35,000 ft.** Above that this deck's off‑design balance stops converging, and the
generator *rejects* those points rather than recording them (see below). 35,000 ft covers the
cruise regime of the engine class the deck describes. `TurbofanResponseSurface` clips its inputs
to the training box, so a query above 35,000 ft returns the 35,000 ft answer — safe, but
**optimistic on available thrust**, so keep ceiling requirements at or below it.

**Every point is validated before it is recorded.** `prob.run_model()` does *not* raise when
pyCycle's Newton solve stalls — it returns whatever state it reached. An early version of this
sweep recorded those states silently and produced thrust lapses above 1.0 (more thrust at
altitude than at sea level), an OPR of ~26,000, and an efficiency that did not respond to
throttle. Each point is now checked against physics it must satisfy by construction, the
sharpest test being that `percent_thrust` mode must deliver the thrust fraction it was asked
for.

**Thrust fraction is a native coordinate.** At each (altitude, Mach) the deck is solved twice:
once at full throttle (`throttle_mode='T4'`) for \(F_\max\), and once in `percent_thrust`
mode at each fraction `PC` of it, with `Fn_max` connected between the two points. So the map
describes the *cycle* rather than one engine size — the same universality the turboshaft map
gets from power fraction — and the thrust lapse comes out **fitted** rather than assumed.
The lapse reference is full throttle at sea level and M 0.001; a true standstill is not run,
because the deck does not converge there (the same reason the PW127 pipeline drops its Mach 0
point).

> **No size scaling.** The turboshaft map corrects small‑engine efficiency with an exponent
> fitted to turboshaft SFC‑vs‑shaft‑power data. That dataset does not describe turbofans, so
> applying it here would be quietly wrong; none is applied, and modern high‑bypass engines in
> the 100–150 kN band vary far less than small turboshafts anyway.

The deck also exports the combustor inlet state \((T_3, P_3, \mathrm{FAR}, \dot m_{air})\)
in the schema `emissions_pipeline/` consumes — the groundwork for a turbofan emission‑index
surrogate (see §4; the packaged EI artifact is still the PW127 turboprop map, and
`ClimateImpact` refuses to apply it to a turbofan).

Regenerating (needs `pycycle` + `openmdao`; ~30–60 min):

```bash
cd PhlyGreen/Systems/Powertrain
python data/HBTF_turbofan.py        # -> data/Turbofan_Universal_Map.csv
python train_turbofan_surrogate.py  # -> data/Turbofan_Engine_Model.pkl
```

The sweep writes each point as it converges and **resumes** from a partial CSV, so an
interrupted run (or a later extension of the envelope) costs only the points still missing.
The sea‑level‑static reference thrust is cached beside the map for the same reason.

See example `26_turbofan_design.py`.

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


