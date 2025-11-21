# Battery Model

This page documents the high‑fidelity **electro‑thermal battery model** in PhlyGreen.

---

# 1. Overview

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

# 2. Battery State Variables

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

# 3. Pack Architecture

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

# 4. Cell Electrical Model  
## Modified Shepherd Equation (Temperature‑Aware)

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

# 5. Thermal Model  
## Lumped‑Parameter Single‑Node Cell Temperature

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

# 6. Battery Sizing Loop

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

# 7. Inputs

Battery configuration comes from `CellInput`:

- `"Class"` — `"I"` (simple) or `"II"` (electro‑thermal)  
- `"Model"` — reference into `Cell_Models`  
- `"SpecificEnergy"` override  
- `"SpecificPower"` override  
- `"Pack Voltage"`  
- `"Minimum SOC"`  
- `"Initial temperature"`  
- `"Max operative temperature"`

Cell models include:

- Mass, size, geometry  
- OCV constants  
- Polarization coefficients  
- Exponential coefficients  
- Arrhenius constants  
- Thermal properties  

---

# 8. Outputs

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

# 9. Error Handling

The battery throws structured exceptions:

- `"SOC_OUTSIDE_LIMITS"`  
- `"VOLTAGE_OUTSIDE_LIMITS"`  
- `"CURR_OUTSIDE_LIMITS"`  
- `"NEG_BATT_TEMP"`  
- `"BATT_UNDERPOWERED"`  
- `"TEMP_OUTSIDE_LIMITS"`  

These allow the sizing algorithm to automatically increase P.

---

# 10. Usage Example

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

# 11. Limitations

- Single‑node temperature model (no spatial gradients).  
- No ageing/SEI model.  
- Cooling system mass is not sized.  
- Discharge‑only model (no charging).  

---

# References

- Shepherd, C. M. *Design of Primary and Secondary Cells: II. An Equation Describing Battery Discharge.*  
   Journal of The Electrochemical Society, 112(7):657, 1965.

- Tremblay, O., & Dessaint, L.-A. *A Generic Battery Model for the Dynamic Simulation of Hybrid Electric Vehicles.*  
   Proceedings of the 2007 IEEE Vehicle Power and Propulsion Conference, pp. 284–289.

- Saw, L., Somasundaram, K., Ye, Y., & Tay, A. *Electro-thermal analysis of Lithium Iron Phosphate battery for electric vehicles.*  
   Journal of Power Sources, 249:231–238, 2014.