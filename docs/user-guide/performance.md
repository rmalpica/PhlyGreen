# Performance Module

The performance module provides all low-level performance computations for an aircraft within the conceptual design loop: speed conversions, aerodynamic state evaluation, power-to-weight constraints, take-off, landing, ceiling, climb, turn, and acceleration requirements.

The Performance class centralizes all the physics relating thrust/power, speed, lift, drag, and mission requirements. It is meant to be used inside the Constraint analysis and Mission modules.

The key responsibilities of the Performance class are:

- Convert between Mach, CAS, TAS, KCAS, KTAS using ISA atmosphere and units
- Compute dynamic pressure, lift coefficient, drag coefficient, exploiting the aircraft aerodynamics module
- Compute required Power-to-Weight ratio (PoWTO) for a generic flight condition, plus phase-specific P/W ratios for the constraint analysis:
    * One-Engine-Inoperative (OEI) climb
    * Ceiling Rate-of-Climb (ROC) requirement
    * Take-off field length
    * Landing approach/stall constraint (gives W/S max)
    * Finger methods (Torenbeek / Raymer-like approximations)

---

## Generic Power-to-Weight ratio

```python
def PoWTO(self, WTOoS, beta, Ps, n, altitude, DISA, speed, speedtype):
    #...
```

This method computes the required **power-to-weight ratio** \\( P/W_{T0} \\) for a generic
steady flight or climb condition. Note that the power-to-weight ratio is computed with reference to the takeoff weight \\( W_{T0} \\).

**Inputs**

- `WTOoS`: wing loading \\( W_{T0} / S \\) [N/m²].
- `beta`: weight fraction \\( \beta = W / W_{T0} \\).
- `Ps`: required specific excess power (e.g. for climb), in m/s.
- `n`: load factor.
- `altitude`, `DISA`, `speed`, `speedtype`: define the operating point.

**Algorithm**

1. Call `set_speed` to compute Mach and TAS for the given condition.
2. Compute dynamic pressure:
   \\[ q = \tfrac{1}{2} \, \rho(h,\Delta T) \, V^2. \\]
3. Compute lift coefficient from vertical equilibrium:
   \\[ C_L = \frac{n \, \beta \, (W_{T0}/S)}{q}. \\]
4. Get drag coefficient from the aircraft polar (see [Aerodynamics](aerodynamics.md)):
   \\[ C_D = C_D(C_L, M). \\]
5. Compute required power-to-weight:

   ```python
   PW = self.g_acc * (1.0/WTOoS * q * self.TAS * Cd + beta * Ps)
   ```

   which corresponds to

   \\[
   \frac{P}{W_{T0}} = g\left[
     \frac{q \, V}{W_{T0}/S} C_D + \beta P_s
   \right].
   \\]

    where the power-to-weight ratio is expressed in [W/kg]
--- 

## Phase-specific Power-to-Weight ratios

## 1. OEI Climb


```python
def OEIClimb(self, WTOoS, beta, Ps, n, altitude, DISA, speed, speedtype):
    #...
```

This method implements the **one-engine-inoperative** (OEI) climb constraint.
It uses the same structure as `PoWTO`, but multiplies the result by
the factor \\( n_{eng}/(n_{eng} - 1) \\) to model the loss of one engine.

Hence, OEI climb yields:

\[
\left(\frac{P}{W_{T0}}\right)_{\text{OEI}}
= \frac{n_{eng}}{n_{eng}-1} \, g\left[\frac{qV}{W_{T0}/S}C_D + \beta P_s\right].
\]

---

## 2. Ceiling 

```python
def Ceiling(self, WTOoS, beta, Ps, n, altitude, DISA, MachC):
    #...
```

This method computes the power-to-weight required to satisfy a given **rate of climb**
at the **service ceiling** altitude.

**Inputs**

- `WTOoS`, `beta`, `Ps`, `n`: as in `PoWTO`.
- `altitude`, `DISA`: service ceiling conditions.
- `MachC`: Mach number at ceiling (used for drag and dynamic pressure).

**Key relations**

1. Compute ceiling TAS from a characteristic max-efficiency lift coefficient \\( C_{L,E} \\):

   \\[
   V_{ceiling} =
   \sqrt{
     \frac{2 \beta (W_{TO}/S)}{\rho(h, \Delta T) \, C_{L,E}(M_C)}
   }.
   \\]

2. Dynamic pressure using Mach:

   \\[
   q = \tfrac12 \, \gamma \, p(h) \, M_C^2
   \\]

3. Lift and drag coefficients:

   \\[ C_L = \frac{n\beta(W_{TO}/S)}{q}, \qquad C_D = C_D(C_L, M_C). \\]

4. Required power-to-weight:

   \\[
   \frac{P}{W_{TO}} = g\left[ \frac{q \, V_{ceiling}}{W_{TO}/S} C_D + \beta P_s \right].
   \\]

---

## 3. Takeoff (Mattingly)

```python
def TakeOff(self, WTOoS, beta, altitudeTO, kTO, sTO, DISA, speed, speedtype):
    #...
```

This method implements a **Mattingly-style** takeoff field length constraint for power-to-weight.

**Inputs**

- `WTOoS`: wing loading \\( W_{T0}/S \\).
- `beta`: takeoff weight fraction.
- `altitudeTO`: takeoff altitude.
- `kTO`: ratio \\( V_{TO} / V_{S,TO} \\).
- `sTO`: required takeoff field length.
- `DISA`: temperature deviation at takeoff.
- `speed`, `speedtype`: define TAS used as `V_TO`.

Core relationship in the code:

```python
PW = self.TAS * beta**2 * WTOoS * (kTO**2) / (
        sTO * ISA.atmosphere.RHOstd(altitudeTO, DISA)
             * self.aircraft.aerodynamics.Cl_TO
     )
```

Mathematically:

 \\[
 \frac{P}{W_{TO}} =
 V_{TO}
 \frac{\beta^2 (W_{TO}/S) k_{TO}^2}{s_{TO} \, \rho(h_{TO}, \Delta T) \, C_{L,TO}}.
 \\]

---

## 4. Takeoff (Torenbeek)


```python
def TakeOff_TORENBEEK(self, altitudeTO, sTO, fTO, hTO, V3oVS, mu,
                      speed, speedtype, DISA):
    #...
```

This method generates a **parametric (P/W, W/S) curve** for takeoff using
Torenbeek's analytical approach.

**Inputs**

- `altitudeTO`: takeoff altitude.
- `sTO`: required takeoff distance.
- `fTO`: fraction of field length for ground run.
- `hTO`: obstacle height.
- `V3oVS`: speed ratio (e.g. certification-related).
- `mu`: ground friction coefficient.
- `speed`, `speedtype`, `DISA`: define TAS at takeoff.

**Algorithm sketch**

1. Use `set_speed` to compute TAS at TO.
2. Define a range of P/W values:

   ```python
   PW = np.linspace(1, 300, num=100)
   ToWTO = PW / self.TAS
   ```

3. Approximate the lift-off climb angle:

   ```python
   gammaLOF = 0.9 * ToWTO - 0.3/np.sqrt(self.aircraft.aerodynamics.AR)
   ```

4. Adjust friction including lift:

   ```python
   mu1 = mu + 0.01 * self.aircraft.aerodynamics.ClMax
   ```

5. Solve analytically for \\( W_{T0}/S \\) as function of P/W_{TO} (closed-form formula in the code).
   The result is an array `WTOoS` such that each pair `(PW[i], WTOoS[i])` lies on the
   Torenbeek takeoff constraint.

---

## 5. Takeoff (Finger)

```python
def TakeOff_Finger(self, WTOoS, beta, altitudeTO, kTO, sTO, DISA, speed, speedtype):
    #...
```

This method uses Finger's analytical approach for **takeoff** power-to-weight.
From the structure of the code, it computes:

```python
self.set_speed(altitudeTO, speed, speedtype, DISA)
PW = self.TAS * (
    1.21 * WTOoS / (sTO * ISA.atmosphere.RHOstd(altitudeTO, DISA)
                    * self.aircraft.aerodynamics.ClTO * self.g_acc)
    + 1.21 * self.aircraft.aerodynamics.Cd(self.aircraft.aerodynamics.ClTO, self.Mach)
            / self.aircraft.aerodynamics.ClTO
    + 0.21 * 0.04
)
```

The corresponding expression is:

 \\[
 \frac{P}{W_{TO}} = V_{TO} \Bigg[
   1.21 \, \frac{W_{TO}/S}{s_{TO} \, \rho \, C_{L,TO} \, g}
  + 1.21 \, \frac{C_{D,TO}}{C_{L,TO}}
  + 0.21 \times 0.04
 \Bigg],
 \\]

where \\( C_{D,TO} = C_D(C_{L,TO}, M) \\). The terms account for:

- ground roll constraint;
- climb-out over obstacle;
- additional margin / safety term.

---

## 6. Landing (Mattingly)

This method encodes the **landing** constraint, typically used to determine a
maximum allowable wing loading \\( (W_{T0}/S)_{max,landing} \\).
The implementation uses standard relations:

- Stall speed in landing configuration:
  \\[ V_{S,L} = \sqrt{\frac{2 (W_{TO}/S)}{\rho C_{L,max,L}}}. \\]
- Approach speed:
  \\[ V_{app} \approx 1.3 V_{S,L}. \\]

Given a maximum allowed approach speed or landing distance, the method limits
the wing loading accordingly. In a constraint diagram this becomes a **vertical line**
at \\( W_{TO}/S = (W_{TO}/S)_{max,landing} \\).

---

## 7. Climb (Finger)


```python
def ClimbFinger(self, WTOoS, beta, Ps, n, altitude, DISA, speed, speedtype):
    #...
```

This method implements **Finger's analytical climb approximation**.
Instead of numerically searching the best climb speed, it uses closed-form
expressions derived from the drag polar.

Key ingredients from the code:

- Induced drag factor:
  ```python
  k = self.aircraft.aerodynamics.ki()
  ```
- Zero-lift drag \\( C_{D0}(M) \\) and minimum lift coefficient \\( C_{L,min} \\).

The method computes a characteristic speed \\( V_{L/D} \\) and a helper quantity \\( H \\), then
obtains an approximate optimum climb speed:

 \\[
 V = \sqrt{ H - \sqrt{H^2 - V_{L/D}^4} }.
 \\]

At this speed, dynamic pressure and drag are computed and plugged into a
PoW expression similar to `PoWTO`:

 \\[
 \frac{P}{W_{TO}} = g\left[ \frac{q V}{W_{TO}/S} C_D^{Finger} + \beta P_s \right],
 \\]

producing an explicit climb constraint without a numeric optimization.

---

## 8. OEI Climb (Finger)

```python
def OEIClimbFinger(self, WTOoS, beta, Ps, n, altitude, DISA, speed, speedtype):
    #...
```

This is the **OEI** version of `ClimbFinger`. It uses the same analytical
Finger approximation and then applies the OEI factor:

\[
\left(\frac{P}{W_{TO}}\right)_{\text{OEI,Finger}}
= \frac{n_{eng}}{n_{eng}-1} \, g\left[ \frac{q V}{W_{TO}/S} C_D^{Finger} + \beta P_s \right].
\]

---

## Speed Conversion

```python
def set_speed(self, altitude, speed, speedtype, DISA):
    # fills Mach, TAS, CAS, KTAS, KCAS from one given speed
    #...
```

**Inputs**

- `altitude` [m]: flight altitude.
- `speed`: numeric value of the given speed.
- `speedtype`: one of `'Mach'`, `'TAS'`, `'CAS'`, `'KTAS'`, `'KCAS'`.
- `DISA`: ISA temperature deviation (delta ISA).

Depending on `speedtype`, the method uses functions in `Speed` and `Units` to convert
between all speed representations. Typical relations:

- If `speedtype == 'Mach'`:
  - Set Mach:  \\( M = s \\).
  - Compute TAS:  \\( V_{TAS} = f_M(M, h, \Delta T) \\).
  - Compute CAS from TAS:  \\( V_{CAS} = f_{TC}(V_{TAS}, h, \Delta T) \\).

- If `speedtype == 'TAS'`:
  - Set TAS:  \\( V_{TAS} = s \\).
  - Compute Mach:  \\( M = f_{MT}(V_{TAS}, h, \Delta T) \\).
  - Compute CAS:  \\( V_{CAS} = f_{TC}(V_{TAS}, h, \Delta T) \\).

and similarly for `CAS`, `KTAS`, `KCAS` by appropriate inversion.

After this call,

- `self.Mach`, `self.TAS`, `self.CAS`, `self.KTAS`, `self.KCAS`

are all consistent at the given `altitude` and `DISA`.