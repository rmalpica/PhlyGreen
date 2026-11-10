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
their energy is computed separately by `Mission._ground_segments`:

- take-off at `Takeoff Power Fraction` (default 1.0) of the take-off-field propulsive power for
  `Takeoff Time` (default 0.7 min);
- taxi-out and taxi-in at `Taxi Power Fraction` (default 7 %) of that power for
  `Taxi Out Time` / `Taxi In Time` (default 13 + 13 min).

The defaults are the ICAO Annex 16 landing/take-off (LTO) reference values (taxi/ground idle:
26 min at 7 %; take-off: 0.7 min at 100 %), with the taxi time split equally between taxi-out
and taxi-in. Each configuration converts these powers to fuel and battery energy through its
own powertrain, at the take-off condition (fuel-cell, gas-turbine or turbofan efficiency at
that load).

In the battery configurations (`Hybrid`, `FuelCellBattery`) the battery supplies a fraction
of the ground power:

| Phase    | Battery fraction | Input | Default |
|----------|------------------|-------|---------|
| Take-off | \(\varphi_{TO}\) | `phi` of the profile's `Takeoff` stage | 0 |
| Taxi     | \(\varphi_{taxi}\) | `Taxi Supplied Power Ratio` (`MissionConfig.taxi_phi`) | \(\varphi_{TO}\) |

\(\varphi_{taxi} = 1\) is an all-electric taxi. The same \(\varphi_{TO}\) splits the take-off /
one-engine-inoperative sizing power (`TO_PBat`). The serial range extender ignores
\(\varphi_{TO}\): its turbine runs at full throttle and the battery covers the rest, as in flight.
A configuration without a battery rejects a non-zero taxi split.

The battery share of the ground segments counts like the flown one:

- its energy is added to the mission battery energy, so it sizes a Class-I battery and enters
  the well-to-wake and grid-CO2 accounting;
- the taxi and take-off battery powers enter the battery peak power `Max_PBat`;
- a Class-II pack is flown through taxi-out and the take-off run before the climb, using the
  in-flight electro-thermal model with ambient air at the take-off altitude. The climb
  therefore starts with the charge already spent and the pack temperature reached on the
  ground. The pack is checked at the worst-case take-off power after taxi-out, and taxi-in must
  fit in the charge left after landing. A ground leg without battery power leaves the pack
  state unchanged.

The taxi-out and take-off fuel is burnt before the climb, so the integration starts at

\[
\beta_0 = 1 - \frac{m_{\text{taxi-out}} + m_{\text{take-off}}}{W_{TO}} ,
\]

and the fuel of all ground segments is added to the mission fuel energy (and therefore to
\(W_f\), the hydrogen tank and the well-to-wake energy). Set the inputs through
`MissionConfig(taxi_out_time=..., taxi_in_time=..., taxi_power_fraction=..., takeoff_time=...,
takeoff_power_fraction=..., taxi_phi=...)`.

The ISA temperature deviation of the flown mission is `MissionConfig.disa` (`MissionInput`
key `DISA`, default 0 K), stored as `mission.DISA`. It sets the flight performance, the
fuel-cell ambient state and the ram air of the thermal-management system. The constraint
diagram, and with it the take-off and one-engine-inoperative sizing points, uses its own
deviation, `ConstraintsConfig.disa` (`ConstraintsInput['DISA']`). A hot-day design sets both.
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

!!! note "What φ measures"
    The supplied-power ratio φ is the battery share, but of different powers in the two battery
    architectures. In `Hybrid` (parallel and serial) it is the battery share of the power
    **supplied by the sources**, \(\varphi = P_{bat}/(P_f + P_{bat})\), with \(P_f\) the fuel
    chemical power (the split equation of the powertrain graph). In `FuelCellBattery` it is the
    battery share of the **propulsive** power: the battery delivers \(\varphi P_p\) and the fuel
    cell \((1-\varphi) P_p\). The same φ value therefore means a much smaller battery share in a
    gas-turbine hybrid, whose fuel power is about three times its shaft power. The reasons for
    the `FuelCellBattery` definition and the conversion between the two are in
    [Powertrain, Fuel cell + battery](powertrain.md#4-fuel-cell-battery). At a segment
    boundary φ takes the value of the segment that starts there.
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

## Off-design flights and limit checks

`fly_off_design(sized, range_nm, ...)` in `examples/30_off_design_mission.py` freezes a sized
aircraft (OEW, powertrain, battery, tank, TMS) and flies it on another range, payload, phi
schedule or state of health. It closes the off-design take-off mass and returns an
`OffDesignResult` with a list of `violations` (empty means feasible) and a list of `risks`.

Each check compares the flown mission with a limit of the frozen design. The limit and the
flown value come from the same models, so the model errors common to both largely cancel, and
the tolerances only absorb numerical noise. A check is a violation only when the model can
resolve it; otherwise it is reported as a risk or not checked.

| Check | Treated as | Tolerance | Fidelity |
|---|---|---|---|
| take-off mass ≤ design MTOW | violation | `tol_kg` | definition of the design |
| fuel load ≤ design fuel load (tank) | violation | 0.5 kg | definition of the design |
| Class-I battery energy ≤ usable energy, power ≤ capability | violation | 0.1 % | same specific-energy/power model as the sizing |
| Class-II battery: SOC, voltage, current, temperature | violation (cell-model limit hit in flight) | none | same cell model as the sizing |
| thermal engine: shaft power ≤ design peak (mission or take-off) | violation | 0.1 % | conservative proxy: the engine model has no explicit power limit |
| fuel cell: demand ≤ maximum net power of the stack | violation (`_power_limited`) | none | same polarization model as the sizing |
| Class-I TMS: peak heat ≤ design heat | violation | 0.1 % | the Class-I TMS is rated by its design heat |
| Class-II TMS: heat, core pressure drops, choking | violation | 2 % on the heat | same correlations as the sizing |
| Class-II TMS: coolant-side wall vs freezing point | risk | none | the wall estimate cannot decide a margin of a few kelvin |
| Class-II TMS: duct drag point by point | not checked | none | carried as a constant ΔCd, conservative over the mission; local differences are below the accuracy of the drag polar |

The fuel-cell power is not compared with the design mission peak: a stack sized on the
take-off or OEI floor can deliver more than that, and the stack's own limit is checked.

## Limitations

- Flight mechanics are 1‑D (no lateral simulation)  
- Weather and airport constraints not included  



