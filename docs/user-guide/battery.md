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
Q_{\text{loss}} = (V_{\text{oc}} - V)\,i - \frac{dE_0}{dT}\, i\, T
\]

The first term is the irreversible (overpotential) heat; the second is the reversible
(entropic) heat, with the sign of Bernardi's balance for a discharge current \(i>0\).

### Convection Cooling Model

\[
h = \max\left[
30\left(\frac{\dot{m}/(A_{\text{sec}}\rho)}{5}\right)^{0.8},\; 2
\right]
\]

where \(A_{\text{sec}}\) is the free cross-section of the cooling channel between cells
(`module_area_section`, \((2r)^2-\pi r^2\)), so \(\dot m/(A_{\text{sec}}\rho)\) is the coolant
velocity. The convective resistance then uses the cell lateral surface
\(A_{\text{surf}} = 2\pi r h_{\text{cell}}\) (`cell_area_surface`).

with airflow proportional to losses:

\[
\dot{m} = a \, Q_{\text{loss}}
\]

---

## Battery Sizing Loop

Inside the aircraft’s WTO root‑finding solver, for each WTO guess:

1. Start from a `P_number` guess: 128 on the first WTO, then the previous optimum scaled by
   the WTO ratio.
2. Fly the whole mission (ground legs included, see below) for a `P_number`. During each
   time step the cell model validates the state; any violation raises a `BatteryError`:
    - SOC below the minimum,
    - terminal voltage below the cell minimum,
    - current above the cell maximum,
    - no real current for the requested power (pack underpowered).
3. Bracket the smallest feasible `P_number`: halve the lower bound while it is still feasible,
   double the upper bound while it is still infeasible. The upper bound stops at the pack
   whose cell mass equals the take-off mass, \(P_{lim}=\lfloor W_{TO}/(S\,m_{cell})\rfloor\).
   If that pack is infeasible too, the search raises a `BatteryError` with code
   `"PACK_HEAVIER_THAN_AIRCRAFT"`.
4. Bisect between the bounds to the smallest feasible `P_number`.
5. Compute the pack mass from that `P_number` and return to the WTO iteration.

The temperature is not a sizing criterion: the pack is held at the maximum operating
temperature by the thermostat, and the heat rejected there sizes the battery cooling mass.

This ensures size is based on **actual in‑mission behaviour**, not just averaged metrics.

The ground segments are part of the same check. When the battery takes a share of the taxi or
take-off power (see [Mission → ground segments](mission.md)), the pack is flown through
taxi-out, a check at the worst-case take-off/OEI power and the take-off run before the climb.
After landing it must also supply taxi-in. A `P_number` is feasible only if all of these legs
respect the limits.

---

## State of health (degradation)

The battery carries a **state of health** relative to beginning of life (BOL). It is given by
the two outputs of the semi-empirical ageing models (for example Schmalstieg et al. 2014):

- the capacity fraction \(C/C_{BOL}\) (`battery_capacity_fraction`);
- the resistance factor \(R/R_{BOL}\) (`battery_resistance_factor`).

Both are `EnergyConfig` fields and default to 1 (BOL). They apply to every battery model:

| Model | Capacity fraction \(c\) | Resistance factor \(r\) |
|---|---|---|
| Class II (cell model) | cell capacity \(\times c\); the charge-proportional Shepherd terms (capacity thermal slope, exponential-zone constant) are rescaled as in `SetInput` | ohmic resistance and polarization constant \(\times r\) |
| Class I (`CellInput`) | specific energy \(\times c\) | specific power \(/ r\) |
| Class I of `FuelCellBattery` (`EnergyInput`) | `Battery Specific Energy` \(\times c\) in `Weight.FuelCellBattery` | `Battery Specific Power` \(/ r\) |

Dividing the Class-I specific power by \(r\) is a first-order approximation: the power a cell
can deliver is inversely proportional to its internal resistance. The Class-II model needs no
such approximation, because the cell model itself enforces the SOC, voltage and current limits
of the aged cell. The usable SOC window and the mass per cell do not change.

The state of health is used in two ways:

- **End-of-life sizing.** Set the fields in the `EnergyConfig` of the design. The pack is sized
  with the aged cell, so it is larger.
- **Aged flight of a sized aircraft.** Call `battery.set_state_of_health(capacity_fraction,
  resistance_factor)` on a copy of the sized aircraft, or use example 30:

```python
from importlib import import_module
ex30 = import_module("30_off_design_mission")            # run from trunk/examples
sized = ex30.fc_battery_design()                          # sized at BOL
r = ex30.fly_off_design(sized, 750.0, state_of_health={
        "battery_capacity_fraction": 0.8, "battery_resistance_factor": 1.5})
print(r.violations)
```

A pack sized for power (for example a take-off battery) is limited by the resistance growth
rather than by the capacity loss. On the take-off-sized fuel-cell + battery design of
example 30, \(c = 0.8\) and \(r = 1.5\) make the required take-off power (749 kW at the
battery terminals) exceed the deliverable power of the aged Class-I pack (500 kW).

The models that turn a mission into a state of health are not part of the package. The
post-design `thermal_degradation_analysis` below estimates the cycle life of a Class-II pack,
but it does not feed a state of health back into the design. A mission-driven ageing model
can be built on the quantities available along the Class-II mission: the spent charge `it`,
the cell temperature and the terminal voltage.

---

## Thermal management & cycle‑life degradation (opt‑in)

Beyond the in‑flight electro‑thermal model above, the Class‑II battery offers an **opt‑in,
post‑design** analysis of ground fast‑charge cooling and battery ageing. It runs on an
*already‑sized* pack and is **never** part of the WTO loop, so enabling it cannot change a
baseline design.

```python
aircraft.configure(config)                              # size as usual (Class-II battery)
ageing = aircraft.battery.thermal_degradation_analysis(charge_c_rate=2.0)
#   -> {'recharge_time_min', 'T_start', 'T_final', 'peak_cooling_w', 'peak_pulldown_w',
#       'peak_heat_w', 'dod', 'soc_start', 'T_flight', 'n_cycles'}
```

One cycle is the mission last flown by the sized pack, followed by a ground recharge. The
analysis reads it from the mission (`Mission.integral_solution` and
`Mission.battery_end_state`):

- the depth of discharge is one minus the lowest SOC reached, taxi-in included, because the
  pack starts the taxi-out full;
- the flight temperature `T_flight` is the time average of the cell temperature from the start
  of the climb to the landing;
- the recharge starts from the SOC and the cell temperature at the end of the taxi-in.

An explicit `soc_start=` sets the recharge start and the DoD `Maximum SOC - soc_start`; an
explicit `flight_temp_k=` sets the flight temperature.

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

It returns the recharge time, the start and final cell temperatures, and two cooling peaks.
The cold-plate heat \(q_{\text{cool}}\) carries the Joule heat of the charge, up to
\(\min(q_{\text{cool}}, q_{\text{gen}})\), and the heat the pack brought from the flight, the
rest. `peak_cooling_w` is the peak of the first part, the cooling load set by the charge rate.
`peak_pulldown_w` is the peak of the second part, set by the temperature at which the pack
arrives. Faster charging shortens the turnaround but raises the temperature and the charge
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

The electric machines of a hybrid are sized from `EnergyInput` (typed: `EnergyConfig`).
`"Specific Power Powertrain"` (`specific_power_powertrain`) gives [thermal, electric motor] in
W/kg. A serial hybrid also carries a generator, sized on the engine rating with
`"Specific Power Generator"` (`specific_power_generator`, W/kg). Its default is the electric
motor value.

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
- `"NEG_BATT_TEMP"` (a non-physical temperature, below 0 K)  
- `"BATT_UNDERPOWERED"`  

These tell the `P_number` search that a pack is infeasible. The search itself raises
`"PACK_HEAVIER_THAN_AIRCRAFT"` when no pack lighter than the aircraft flies the mission. The
post-design ageing analysis raises `"REQUIRES_CLASS_II"` and `"NO_CHARGE_C_RATE"` for invalid
calls.

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
`hex_specific_power_h2` (default **5000 W/kg**) for the fuel cell (its Class-I TMS; see
[Thermal Management](thermal-management.md) for the geometric Class-II model). The result appears as the
`cooling` item in the mass breakdown / `WHeat_Exchanger`. (The Class-I battery has no thermal
model, so it carries no cooling mass.) The separate *ground fast-charge* cooling load from
`thermal_degradation_analysis` is a post-design study and is **not** added to the WTO.

## Limitations

- Single‑node temperature model (no spatial gradients).  
- The intrinsic thermal resistance of the cell, \(R_{i,th}=3.3\,(r/0.022)^2\) K/W, is uncited:
  no file of the repository gives the source of the value or of the reference radius.  
- The cycle life takes one temperature per part of the cycle. The time-averaged flight
  temperature gives a fade rate no larger than the time average of the rate, because the
  rate is convex in temperature, so the estimate is slightly optimistic.  
- Ageing enters the design only as a prescribed state of health (capacity fraction,
  resistance factor). The cycle-life estimate and the ground recharge/cooling load are an
  **opt‑in post‑design** analysis (Wang/Miner cycle life, cold‑plate cooling) and do not feed
  back into the sizing. The in‑flight sizing loop remains discharge‑only.  

---

# References

- Shepherd, C. M. *Design of Primary and Secondary Cells: II. An Equation Describing Battery Discharge.*  
   Journal of The Electrochemical Society, 112(7):657, 1965.

- Tremblay, O., & Dessaint, L.-A. *A Generic Battery Model for the Dynamic Simulation of Hybrid Electric Vehicles.*  
   Proceedings of the 2007 IEEE Vehicle Power and Propulsion Conference, pp. 284–289.

- Saw, L., Somasundaram, K., Ye, Y., & Tay, A. *Electro-thermal analysis of Lithium Iron Phosphate battery for electric vehicles.*  
   Journal of Power Sources, 249:231–238, 2014.

- Schmalstieg, J., Käbitz, S., Ecker, M., & Sauer, D. U. *A holistic aging model for Li(NiMnCo)O2 based 18650 lithium-ion batteries.*  
   Journal of Power Sources, 257:325–334, 2014. (capacity fraction and resistance factor as ageing outputs)

- Wang, J. et al. *Cycle-life model for graphite-LiFePO4 cells.*  
   Journal of Power Sources, 196(8):3942–3948, 2011. (capacity-fade law used for cycle life)