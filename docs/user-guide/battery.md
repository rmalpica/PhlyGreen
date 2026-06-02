# Battery Model

This page documents the high‑fidelity **electro‑thermal battery model** in PhlyGreen.

---

## Overview

PhlyGreen’s Battery module provides a **dynamic**, **temperature‑aware**, **physics‑based**
representation of a lithium‑ion battery pack suitable for hybrid‑electric aircraft preliminary design.

It simulates:

- A representative **cell**, based on a modified Shepherd equation  
- Its **thermal behaviour** using a lumped‑parameter model  
- A complete **battery pack**, built via series (`S`) and parallel (`P`) configuration  
- Full **operational constraint handling** (voltage, SOC, current, temperature)  
- A sizing loop integrated into the aircraft’s WTO iteration  

The model is based on empirical cell parameters (selected in `Cell_Models`) and is configurable via user‑provided battery settings.

---

## Battery State Variables

At every timestep, the battery tracks three continuous state variables:

- **Cell current**: `i`  
- **Spent charge** (Ah):  

  $$ i_t(t+\Delta t) = i_t(t) + \frac{i\,\Delta t}{3600} $$

- **Temperature**: \( T \)

The **State of Charge (SOC)** is defined as:

$$ \text{SOC} = 1 - \frac{i_t}{Q} $$

where \( Q \) is the cell capacity.

A `BatteryError` is raised if SOC leaves the allowable range:

$$ \text{SOC}_{\min} \le \text{SOC} \le 1 $$

---

## Pack Architecture

A battery pack is constructed as:

- `S` cells in series → increases voltage  
- `P` cells in parallel → increases current capability  

Thus:

$$ V_{\text{pack}} = S \, V_{\text{cell}} $$

$$ I_{\text{pack}} = P \, i_{\text{cell}} $$

Pack-level capacity and energy:

$$ Q_{\text{pack}} = P \, Q $$

$$ E_{\text{pack}} = S \, P \, E_{\text{cell}} $$

---

## Cell Electrical Model  
### Modified Shepherd Equation (Temperature‑Aware)

The cell voltage is computed using a temperature‑corrected modified Shepherd model:

\[
V = E_0(T)
    - K(T)\left(\frac{Q}{Q - i_t}\right)i_t
    + A(T)e^{-B(T)i_t}
    - i\,R(T)
\]

Where:

- \( E_0(T) \) — open‑circuit voltage (with thermal correction)  
- \( K(T) \) — polarization constant  
- \( A(T), B(T) \) — exponential zone parameters  
- \( R(T) \) — internal resistance (Arrhenius‑corrected)  

### Solving for Current from a Required Power

Given a required pack power \( P_{\text{pack}} \), the battery solves:

\[
P_{\text{cell}} = \frac{P_{\text{pack}}}{S\,P}
\]

\[
P_{\text{cell}} = V(i)\, i
\]

This becomes a quadratic equation:

\[
a i^2 + b i + c = 0
\]

Where:

- \( a = -(R + K_r) \) with \( K_r = K Q/(Q-i_t) \)  
- \( b = E_0 + A e^{-Bi_t} - i_t K_r \)  
- \( c = -P_{\text{cell}} \)

The physically meaningful root is selected:

\[
i = \frac{-b + \sqrt{b^2 - 4ac}}{2a}
\]

If the discriminant is negative:

\[
b^2 - 4ac < 0 \quad\Rightarrow\quad \text{BatteryError}
\]

---

## Thermal Model  
### Lumped‑Parameter Single‑Node Cell Temperature

The cell temperature evolves according to:

\[
\frac{dT}{dt} = \frac{Q_{\text{loss}}}{C_{\text{th}}}
               + \frac{T_{\infty} - T}{R_{\text{th}}\, C_{\text{th}}}
\]

Where:

- \( C_{\text{th}} \) — thermal capacitance  
- \( R_{\text{th}} \) — total thermal resistance  

### Heat Generation

\[
Q_{\text{loss}} = (V_{\text{oc}} - V)i + \frac{dE_0}{dT} i T
\]

### Convection Cooling Model

\[
h = \max\left[
30\left(\frac{\dot{m}/(A_{\text{surf}}\rho)}{5}\right)^{0.8},\; 2
\right]
\]

with airflow proportional to losses:

\[
\dot{m} = a \, Q_{\text{loss}}
\]

---

## Battery Sizing Loop

Inside the aircraft’s WTO root‑finding solver:

1. Guess `WTO`  
2. Guess `P_number`  
3. Run full mission simulation  
4. During each timestep, battery state is updated  
5. If any violation occurs:  
    - SOC too low  
    - Voltage too low  
    - Current > max  
    - Temperature out of range  
    → A `BatteryError` is thrown  
6. Increase `P_number` and retry  
7. Once feasible, compute pack weight  
8. Continue WTO iteration  

This ensures size is based on **actual in‑mission behaviour**, not just averaged metrics.

---

## Thermal management & cycle‑life degradation (opt‑in)

Beyond the in‑flight electro‑thermal model above, the Class‑II battery offers an **opt‑in,
post‑design** analysis of ground fast‑charge cooling and battery ageing. It runs on an
*already‑sized* pack and is **never** part of the WTO loop, so enabling it cannot change a
baseline design.

```python
aircraft.configure(config)                              # size as usual (Class-II battery)
ageing = aircraft.battery.thermal_degradation_analysis(charge_c_rate=2.0)
#   -> {'recharge_time_min', 'T_final', 'peak_cooling_w', 'peak_heat_w', 'dod', 'n_cycles'}
```

The results are cached on `battery.ageing` and surfaced in
`AircraftResults.extras['battery_ageing']`. See example
`17_battery_thermal_and_degradation.py`.

### Ground fast‑charge thermal model

During a constant‑current recharge from the end‑of‑flight SOC back to full, the cell
temperature is time‑stepped from a lumped balance of **Joule heating** against an **active
liquid cold‑plate**:

\[
q_{\text{gen}} = I_{\text{ch}}^2\,R(T), \qquad
R(T) = R_{\text{ref}}\,e^{\,b_R\left(\frac{1}{T}-\frac{1}{T_{\text{ref}}}\right)}
\]

\[
q_{\text{cool}} = h_{\text{ground}}\,A_{\text{cell}}\,(T - T_{\text{coolant}}), \qquad
\frac{dT}{dt} = \frac{q_{\text{gen}} - q_{\text{cool}}}{C_{\text{th}}}
\]

It returns the recharge time, the final cell temperature, and the **peak active‑cooling power**
the thermal‑management system (TMS) must reject — a sizing driver for the ground/onboard
cooling system. Faster charging shortens the turnaround but raises the temperature and the
cooling load.

### Cycle‑life degradation (Wang et al. + Miner)

The number of full cycles to end‑of‑life follows the Wang et al. capacity‑fade law, in which
the charge throughput to a given capacity loss depends on the C‑rate, the depth‑of‑discharge
(DoD) and the temperature:

\[
A_h = \left[\frac{\Delta Q_{\text{EoL}}\,[\%]}{A\,\exp\!\frac{-E_a + B\,C_{\text{rate}}}{R\,T}}\right]^{1/z},
\qquad
N_{\text{cycles to EoL}} = \frac{A_h}{\text{DoD}\cdot Q_{\text{cell}}}
\]

The flight (discharge) and the recharge each contribute damage; these accumulate linearly
(Miner's rule, or a Marco–Starkey \(L_p\) norm) to give the expected cycle life. Higher
temperatures and deeper / faster cycling all shorten it.

*Adapted from the Class‑II battery heat‑management & degradation work by Francesco Campagna.*

---

## Inputs

Battery configuration comes from `CellInput` (typed: `CellConfig`):

- `"Class"` — `"I"` (simple) or `"II"` (electro‑thermal)  
- `"Model"` — reference into `Cell_Models`  
- `"SpecificEnergy"` override  
- `"SpecificPower"` override  
- `"Pack Voltage"`  
- `"Minimum SOC"`  
- `"Initial temperature"`  
- `"Max operative temperature"`

Optional fields for the **thermal‑management / degradation** analysis (defaults applied when
the analysis is invoked):

- `"Charge C-Rate"` — ground fast‑charge C‑rate [1/h]  
- `"Discharge C-Rate"` — representative in‑flight discharge C‑rate [1/h]  
- `"Maximum SOC"` — SOC at full charge (default 1.0)  
- `"EoL Capacity"` — end‑of‑life capacity fraction (e.g. 0.8)  
- `"Coolant Temperature"` — ground coolant inlet temperature [°C]  
- `"Ground Cooling Coefficient"` — cold‑plate \(h\) [W/m²K]

Cell models include:

- Mass, size, geometry  
- OCV constants  
- Polarization coefficients  
- Exponential coefficients  
- Arrhenius constants  
- Thermal properties  

---

## Outputs

Available throughout the simulation:

- `Vout` — pack voltage  
- `cell_Vout` — cell voltage  
- `I_pack` and `i_cell` — total and per‑cell current  
- `SOC`  
- `T`  
- `Q_loss` — thermal losses  
- Pack mass, volume, energy  
- Maximum deliverable power  

---

## Error Handling

The battery throws structured exceptions:

- `"SOC_OUTSIDE_LIMITS"`  
- `"VOLTAGE_OUTSIDE_LIMITS"`  
- `"CURR_OUTSIDE_LIMITS"`  
- `"NEG_BATT_TEMP"`  
- `"BATT_UNDERPOWERED"`  
- `"TEMP_OUTSIDE_LIMITS"`  

These allow the sizing algorithm to automatically increase P.

---

## Usage Example

```python
battery = Battery(aircraft)
battery.SetInput()
battery.Configure(parallel_cells=48)

I = battery.Power_2_current(P=150e3)
dTdt, Qloss = battery.heatLoss(Ta=288, rho=1.225)

battery.it += I * dt / 3600
battery.T  += dTdt * dt
```

---

## Thermal-management mass in the take-off weight

For a Class-II battery the **in-flight** thermal-management (cooling) system *is* sized and
included in the take-off-weight balance. The pack is held at its maximum operating temperature
by a thermostat: below the ceiling the heat is absorbed adiabatically by the thermal mass and
nothing is rejected, and only once the pack is **clamped at the ceiling** does the cooling
system reject the generated heat. The weight loop therefore sizes the cooling mass from the
**peak heat rejected while at the ceiling** \(Q_{\text{peak}}\) (zero if the pack never reaches
its limit), via a **specific power** (heat rejected per kg of heat-exchanger system):

\[
W_{\text{cool}} = \frac{Q_{\text{peak}}}{\text{HEX specific power [W/kg]}} .
\]

The battery HEX rejects to ambient through a liquid loop + ram-air, which is *less*
mass-effective than the cryogenic-H2-cooled fuel-cell HEX, so the two use **separate** inputs:
`EnergyConfig.hex_specific_power_battery` (default **1500 W/kg**) for the battery and
`hex_specific_power_h2` (default **5000 W/kg**) for the fuel cell. The result appears as the
`cooling` item in the mass breakdown / `WHeat_Exchanger`. (The Class-I battery has no thermal
model, so it carries no cooling mass.) The separate *ground fast-charge* cooling load from
`thermal_degradation_analysis` is a post-design study and is **not** added to the WTO.

## Limitations

- Single‑node temperature model (no spatial gradients).  
- Ageing and the ground recharge/cooling load are modelled only in the **opt‑in post‑design**
  analysis (Wang/Miner cycle life, cold‑plate cooling); the in‑flight sizing loop itself
  remains discharge‑only.  

---

# References

- Shepherd, C. M. *Design of Primary and Secondary Cells: II. An Equation Describing Battery Discharge.*  
   Journal of The Electrochemical Society, 112(7):657, 1965.

- Tremblay, O., & Dessaint, L.-A. *A Generic Battery Model for the Dynamic Simulation of Hybrid Electric Vehicles.*  
   Proceedings of the 2007 IEEE Vehicle Power and Propulsion Conference, pp. 284–289.

- Saw, L., Somasundaram, K., Ye, Y., & Tay, A. *Electro-thermal analysis of Lithium Iron Phosphate battery for electric vehicles.*  
   Journal of Power Sources, 249:231–238, 2014.

- Wang, J. et al. *Cycle-life model for graphite-LiFePO4 cells.*  
   Journal of Power Sources, 196(8):3942–3948, 2011. (capacity-fade law used for cycle life)