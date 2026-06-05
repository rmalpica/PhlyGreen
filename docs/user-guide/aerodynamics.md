# Aerodynamics Module

The **Aerodynamics** module (`Systems/Aerodynamics/Aerodynamics.py`) provides the Class‑I
**drag polar** — the drag coefficient \(C_D\) as a function of the lift coefficient \(C_L\) (and
Mach) — together with the lift coefficients that bound the flight envelope (take‑off, landing,
minimum) and the lift coefficient for **maximum aerodynamic efficiency**. Every other module that
needs drag — the [Mission](mission.md) power integration and the [Constraints](constraints.md)
diagram — reads it through `aircraft.aerodynamics`.

---

## Overview

The model is deliberately low‑order (preliminary sizing): it returns a smooth \(C_D(C_L, M)\) from a
handful of macroscopic parameters rather than a panel/CFD solution. It offers:

- an **analytic quadratic polar** built from aspect ratio and Oswald efficiency;
- **numerical polars** — fixed \(C_D(C_L)\) fits for specific aircraft (ATR42, DO228);
- a small **transonic correction** to the zero‑lift drag above \(M = 0.8\);
- the **maximum‑efficiency lift coefficient** \(C_{L,E}\) used by the performance/mission models.

The polar is selected in `AerodynamicsInput` (typed: `AerodynamicsConfig`) by supplying either an
`AnalyticPolar` or a `NumericalPolar` block.

---

## 1. The quadratic polar

With an `AnalyticPolar` the drag coefficient is the classical quadratic form

\[
C_D(C_L, M) \;=\; C_{D_0}(M) \;+\; k_1\,C_L^2 \;+\; k_2\,C_L ,
\]

where the coefficients come from the wing geometry and a small viscous term:

\[
k_1 = k_v + \frac{1}{\pi\,A\!R\,e}, \qquad
k_2 = -2\,k_v\,C_{L,\min}, \qquad
k_v = 0.01 .
\]

The \(1/(\pi\,A\!R\,e)\) term is the **induced drag** (aspect ratio \(A\!R\), Oswald efficiency
\(e\)); the \(k_v\) terms add a shallow, slightly asymmetric viscous bucket centred near
\(C_{L,\min}\). Set it up with:

```python
from PhlyGreen.config import AerodynamicsConfig
aero = AerodynamicsConfig(
    take_off_cl=1.9, landing_cl=1.9, minimum_cl=0.20, cd0=0.017,
    analytic_polar={'type': 'Quadratic', 'input': {'AR': 11, 'e_osw': 0.8}},
)
```

### Maximum‑efficiency lift coefficient

The \(C_L\) that maximises \(L/D\) for a quadratic polar (ignoring the small \(k_2\) term) is where
induced drag equals zero‑lift drag:

\[
C_{L,E}(M) \;=\; \sqrt{\,C_{D_0}(M)\,\pi\,A\!R\,e\,}.
\]

This is what cruise/climb performance uses as the reference "fly for best efficiency" point.

---

## 2. Numerical polars

For a specific airframe you can bypass the analytic form and use a fitted \(C_D(C_L)\). Two are
built in, selected with a `NumericalPolar` block (`{'type': 'ATR42'}` or `{'type': 'DO228'}`):

\[
\text{ATR42:}\quad C_D = 0.021476 + 0.030374\,C_L^2,
\qquad
\text{DO228:}\quad C_D = 0.029 + k_1\,C_L^2 .
\]

The ATR42 polar also carries a fixed best‑efficiency value \(C_{L,E} = 0.82\). (A nominal aspect
ratio of 11 is still set internally so downstream consumers have a value.)

---

## 3. Transonic zero‑lift drag

The zero‑lift drag is constant up to \(M = 0.8\) and then rises with a simple linear
drag‑divergence bump:

\[
C_{D_0}(M) =
\begin{cases}
C_{D_0}, & M \le 0.8 \\[4pt]
0.035\,M - 0.011, & M > 0.8 .
\end{cases}
\]

!!! note "Scope"
    This is a *crude* transonic model adequate for turboprop cruise Mach (\(M \lesssim 0.6\)); it is
    **not** a drag‑divergence/buffet model for high‑subsonic jet cruise. A credible
    \(M\,0.78\text{–}0.85\) study would need a proper transonic polar.

---

## Inputs

`AerodynamicsInput` (typed: `AerodynamicsConfig`):

- `"Take Off Cl"` — maximum lift coefficient at take‑off (`take_off_cl`)
- `"Landing Cl"`  — maximum lift coefficient at landing (`landing_cl`), sets the landing W/S wall
- `"Minimum Cl"`  — lift coefficient at the bottom of the drag bucket (`minimum_cl`)
- `"Cd0"`         — zero‑lift drag coefficient (`cd0`)
- `"AnalyticPolar"` — `{'type': 'Quadratic', 'input': {'AR': …, 'e_osw': …}}`, **or**
- `"NumericalPolar"` — `{'type': 'ATR42' | 'DO228'}`

Exactly one of `AnalyticPolar` / `NumericalPolar` must be present.

---

## Usage

```python
aircraft.configure(traditional_config())          # carries an AerodynamicsInput
cd  = aircraft.aerodynamics.Cd(Cl=0.5, Mach=0.45) # drag coefficient at a point
cle = aircraft.aerodynamics.ClE(Mach=0.45)        # best-L/D lift coefficient
```

The drag polar feeds the propulsive‑power term \(C_D(C_L, M)\) in both the
[Mission](mission.md#mission-power-calculation) integration and the
[Constraints](constraints.md) diagram.

---

## References

- Raymer, D. P. *Aircraft Design: A Conceptual Approach.* (Quadratic drag polar, induced‑drag factor.)
- Ruijgrok, G. J. J. *Elements of Airplane Performance.* (Drag polar and best‑efficiency conditions.)
