# Mission and Flight Profile Module

This page documents the **Mission** and **Profile** modules of PhlyGreen.  
These modules define the aircraft’s **flight profile**, **instantaneous power and overall energy consumption**,  
and provide the temporal backbone used by all sizing routines (weight, battery, powertrain, emissions).


---

## Overview

The mission solver integrates the aircraft state along a sequence of **flight segments**:

- climb  
- cruise  
- descent  
- loiter  
- diversion  

The **ground segments** (taxi-out, take-off run, taxi-in) are not part of the flown profile;
their fuel is computed separately by `Mission._ground_segments`:

- take-off at the take-off-field propulsive power for `Takeoff Time` (default 0.7 min);
- taxi-out and taxi-in at `Taxi Power Fraction` (default 7 %) of that power for
  `Taxi Out Time` / `Taxi In Time` (default 13 + 13 min).

The defaults are the ICAO Annex 16 landing/take-off (LTO) reference values (taxi/ground idle:
26 min at 7 %; take-off: 0.7 min at 100 %), with the taxi time split equally between taxi-out
and taxi-in. Each configuration converts these powers to fuel through its own powertrain
(fuel-cell, gas-turbine or turbofan efficiency at that load), on the primary fuel; the battery
share of hybrids is not counted for these short, low-power segments. The taxi-out and take-off
fuel is burnt before the climb, so the integration starts at

\[
\beta_0 = 1 - \frac{m_{\text{taxi-out}} + m_{\text{take-off}}}{W_{TO}} ,
\]

and the fuel of all ground segments is added to the mission fuel energy (and therefore to
\(W_f\), the hydrogen tank and the well-to-wake energy). Set the inputs through
`MissionConfig(taxi_out_time=..., taxi_in_time=..., taxi_power_fraction=..., takeoff_time=...)`.
The former `Beta start` input is deprecated and ignored.

Each segment prescribes:

- altitude trajectory  
- speed schedule  
- load factor  
- electrical/thermal power split  


The **Profile** module generates the *time‑resolved reference states* (altitude, speed, flight path angle), while the **Mission** module performs the **powertrain requests**, **energy integration**, and **battery/fuel usage**.

---

## Mission Class — High‑Level Responsibilities

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

## Flight Profile Generation (Profile Class)

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

The cruise is not given a length: it fills whatever range the climbs and descents of its phase
leave. A phase therefore holds a single cruise, with a linear φ from `phi_start` to `phi_end`.
If the climbs and descents alone are longer than the phase range, the cruise would get a
negative length. In that case building the profile raises a `ValueError` naming the phase. The
example profile (cruise at 8,000 m) needs about 215 nm of climb and descent.

!!! tip "Constant-throttle climb"
    A single fixed-rate climb runs the engine from light part-load near the ground to a
    power-limited 100 % near cruise, because the available power lapses with altitude. The
    example profiles in `common.py` therefore split the climb into several short
    `ConstantRateClimb` segments whose climb gradient **decreases** with altitude (rates of
    ~2400 ft/min near the ground tapering to ~600 ft/min approaching cruise). This keeps the
    gas-turbine throttle roughly constant over the climb instead of ramping to its limit. The
    diversion climb uses the same tapering.


---

## Mission Power Calculation

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

depending on the configured architecture (traditional, parallel hybrid, serial hybrid,
hydrogen fuel cell, or fuel-cell + battery). A serial hybrid given a `gt_rated_power` is flown
as a **range extender** (constant-power turbine + recharging battery buffer) via
`SerialRangeExtenderConfiguration`.

---

## Energy Integration

### Battery Energy

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

### Fuel Energy

Fuel energy integration:

\[
E_f(t+\Delta t) = E_f(t) +  \int_{t}^{t+\Delta t} \frac{P_f}{W_{TO}} \left( \varphi(t), \beta(t), h(t), V(t),\frac{W_{TO}}{S} \right) \, W_{TO} \, dt \, ,
\]

where the fuel power is obtained by amplifying the propulsive power with the thermal efficiency chain.

---

## Segment Loop (Core Mission Logic)

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


## Mission Outputs

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

## Usage Example

```python
mission = aircraft.mission
mission.SetInput()           # load MissionInput dictionary
mission.InitializeProfile()       # generate profile
results = mission.EvaluateMission(WTO) # integrate energy and power use
```

---

## Limitations

- Flight mechanics are 1‑D (no lateral simulation)  
- Weather and airport constraints not included  



