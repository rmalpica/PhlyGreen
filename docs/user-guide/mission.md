# Mission and Flight Profile Module

This page documents the **Mission** and **Profile** modules of PhlyGreen.  
These modules define the aircraft’s **flight profile**, **instantaneous power and overall energy consumption**,  
and provide the temporal backbone used by all sizing routines (weight, battery, powertrain, emissions).


---

# 1. Overview

The mission solver integrates the aircraft state along a sequence of **flight segments**:

- climb  
- cruise  
- descent  
- loiter  
- diversion  

Taxi and Take-off phases are presently **not** integrated in time, but accounted for with assigned fuel mass fractions.

Each segment prescribes:

- altitude trajectory  
- speed schedule  
- load factor  
- electrical/thermal power split  


The **Profile** module generates the *time‑resolved reference states* (altitude, speed, flight path angle), while the **Mission** module performs the **powertrain requests**, **energy integration**, and **battery/fuel usage**.

---

# 2. Mission Class — High‑Level Responsibilities

The `Mission` class:

- Reads user mission inputs (`MissionInput` dictionary)
- Builds the flight profile via the `Profile` class
- Computes **instantaneous power** using aerodynamic and performance models
- Integrates:
   - battery power  
   - gas turbine power  
- Detects mission failures (insufficient power, battery issues)
- Returns mission total energies used for sizing

---

# 3. Flight Profile Generation (Profile Class)

The `Profile` class discretizes the flight profile.  
It stores vectors of:

- `altitude[t]`
- `speed[t]`
- `flight_path_angle[t]`
- `load_factor[t]`

It supports the following segments:

- Climb
- Cruise
- Descent
- Loiter
- Diversion

Each segment **appends time‑resolved states** to the global mission arrays.


---

# 4. Mission Power Calculation

At each timestep \( t \), the Mission module computes the required **propulsive power** using the aircraft’s `Performance` instance:

\[
P_{prop}(t)= W_{TO}
\left[
\frac{q V}{W_{TO}/S}\, C_D(C_L, M)
+ \beta P_s
\right]
\]

where:

- \( q = \frac{1}{2}\rho V^2 \)  
- \( W_{TO}/S \) wing loading  
- \( C_L, C_D \) aerodynamic coefficients  
- \( \beta \) = weight fraction  
- \( P_s \) = excess power requirement for climb  

The Mission module then calls the **Powertrain** module to split this power into:

- fuel power  
- battery power  

depending on the configured architecture (tradition, serial hybrid, parallel hybrid).

---

# 5. Energy Integration

## 5.1 Battery Energy

The integrated battery power request yields:

\[
E_{bat}(t+\Delta t) = E_{bat}(t) +  \int_{t}^{t+\Delta t} \frac{P_{bat}}{W_{TO}} \left( \varphi(t), \beta(t), h(t), V(t),\frac{W_{TO}}{S} \right) \, W_{TO} \, dt \, ,
\]

where \( P_{\text{bat}} \) is given by processing the propulsive power with the electrical efficiency chain. 
If the Class II battery model is used, the current is computed:

\[
I(t) = \text{Battery.Power_2_current}(P_{\text{bat}})
\]

and the SOC evolution is:

\[
\text{SOC}(t+\Delta t)
=
1
-
\frac{i_t(t)+ I\Delta t/3600}{Q}
\]

Battery temperature uses the thermal ODE:

\[
\frac{dT}{dt}
=
\frac{Q_{\text{loss}}}{C_{\text{th}}}
+
\frac{T_\infty - T}{R_{\text{th}}C_{\text{th}}}
\]

## 5.2 Fuel Energy

Fuel energy integration:

\[
E_f(t+\Delta t) = E_f(t) +  \int_{t}^{t+\Delta t} \frac{P_f}{W_{TO}} \left( \varphi(t), \beta(t), h(t), V(t),\frac{W_{TO}}{S} \right) \, W_{TO} \, dt \, ,
\]

where the fuel power is obtained by amplifying the propulsive power with the thermal efficiency chain.

---

# 6. Segment Loop (Core Mission Logic)

Pseudocode equivalent to the Mission solver:

```
for each timestep t in mission_profile:
    read altitude, speed, gamma
    compute performance propulsive power Pp
    request powertrain split
    update fuel and battery states
    check SOC, voltage, current, T
    accumulate segment energy
```

If any constraint is violated, a `MissionError` or `BatteryError` is thrown, causing the **aircraft sizing loop** to increase P‑number or adjust weight.

---


# 7. Mission Outputs

After integrating the full mission, the module returns:

- Total mission fuel energy  
- Total mission battery energy  
- Total emissions (if enabled)  
- Segment‑by‑segment logs (power, altitude, speed, SOC, T)  
- Peak power requirements  
- Mission duration  
- Required reserve energy  
- Whether mission constraints were satisfied  

These outputs feed directly into:

- **Powertrain Sizing**  
- **Battery Sizing**  
- **WTO iteration**  
- **Emissions accounting**  
- **Well‑to‑Wake energy evaluation**

---

# 10. Usage Example

```python
mission = aircraft.mission
mission.SetInput()           # load MissionInput dictionary
mission.InitializeProfile()       # generate profile
results = mission.EvaluateMission(WTO) # integrate energy and power use
```

---

# 11. Limitations

- Flight mechanics are 1‑D (no lateral simulation)  
- Weather and airport constraints not included  



