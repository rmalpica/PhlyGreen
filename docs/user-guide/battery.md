# Battery Model

This page documents the `Battery` class, which implements the electro‑thermal model, safety constraints, configuration logic, and power–current conversion used in PhlyGreen.

---

## Overview

The `Battery` class models the behavior of a lithium‑ion battery pack at both the **cell level** and **pack level**.  
It handles:

- Validation of operating conditions (SOC, current, voltage, temperature)
- The electro‑thermal voltage model
- Pack sizing (series/parallel)
- Thermal dynamics via a lumped‑parameter model
- Current estimation from requested power
- Integration with the Mission and Powertrain models

The model is based on empirical cell parameters (selected in `Cell_Models`) and is configurable via user‑provided battery settings.

---

## Key Concepts

### Cell‑Level Quantities

The battery pack consists of:

- `S_number`: number of cells in **series**
- `P_number`: number of cells in **parallel**
- Total cells = `S_number × P_number`

A few important cell quantities:

- `cell_Vout` — instantaneous cell voltage under load  
- `cell_it` — charge spent per cell (Ah)  
- `cell_i` — discharge current per cell (A)  
- `cell_capacity` — nominal capacity (Ah)  
- `cell_max_current` — max allowable cell current  

SOC is computed as:

```text
SOC = 1 − cell_it / cell_capacity
```

---

## Safety Checks

The model automatically enforces:

- **SOC limits** (`SOC_min ≤ SOC ≤ 1`)
- **Voltage limits** (`cell_Vmin ≤ Vout`)
- **Current limits** (per‑cell)
- **Temperature positivity**

Failures raise a `BatteryError` with a diagnostic code.

---

## Pack Configuration

Use the method:

```python
battery.Configure(parallel_cells)
```

This sets:

- Pack mass  
- Pack volume  
- Pack nominal energy  
- Pack peak power capability  

Series count is determined automatically from the requested pack voltage.

---

## Power → Current Conversion

The function:

```python
I_out = battery.Power_2_current(P)
```

solves the quadratic relationship:

$$
P = V(I) · I
$$

using the electro‑thermal voltage model:

$$
V = E0 − (i + it)·K·Q/(Q−it) + A·exp(−B·it) − i·R
$$

The returned current is the **total pack current**, not per‑cell.

---

## Thermal Model

Battery heat generation:

$$
P_{loss} = (V_{oc} − V)·i + \frac{dE}{dT} · i · T
$$

Cooling is modeled with a convection coefficient:

$$
h = \text{max} \left(30 \cdot  \left(\frac{\dot{m}/(A·\rho)}{5} \right)^{0.8} , 2 \right)
$$

Temperature change follows:

$$
\frac{dT}{dt} = \frac{P_{loss}}{C_{th}} + \frac{T_a − T}{R_{th} \cdot C_{th}}
$$

---

## Initialization via `SetInput()`

When `BatteryClass == 'II'`, the model loads all cell parameters from `Cell_Models` and applies user-specified overrides:

- `SpecificEnergy`
- `SpecificPower`
- `Pack Voltage`
- `Minimum SOC`

These values update:

- Capacity
- Resistance
- Polarization constants
- Max current
- Thermal slopes

---

## Typical Usage

```python
battery = Battery(aircraft)
battery.SetInput()
battery.Configure(parallel_cells=40)

battery.i = battery.Power_2_current(P=120e3)
battery.it += battery.i * dt / 3600  # integrate Ah
battery.T += dTdt * dt               # thermal integration
```

---

## Returned Attributes

After configuration, the following are available:

- `pack_weight`
- `pack_volume`
- `pack_energy`
- `pack_power_max`
- `Vout` / `Voc`
- `SOC`, `T`, `i`, `it`

---

## Error Handling

The model raises:

```python
BatteryError(message, code="...")
```

Codes include:

- `"SOC_OUTSIDE_LIMITS"`
- `"VOLTAGE_OUTSIDE_LIMITS"`
- `"CURR_OUTSIDE_LIMITS"`
- `"NEG_BATT_TEMP"`
- `"BATT_UNDERPOWERED"`
- and others

This ensures numerical stability when running long mission simulations.

---

## Notes for Users

- Most failures indicate physically impossible demands (e.g., power > battery can deliver).  
- Ensure consistent timestep scaling when integrating `it` and `T`.  
- Pack sizing should be performed before mission evaluation.  
- The model supports both simple (`BatteryClass == 'I'`) and full (`BatteryClass == 'II'`) configurations.

---

