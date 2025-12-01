# Weight Module

The **Weight** module in PhlyGreen computes the aircraft’s **takeoff weight (WTO)** through an iterative
process that exploits the mission simulation workflow. The iterative process is necessary because the 
mission simulation workflow requires the takeoff weight as input, which is unknown a priori. 
It supports two fidelity levels:

- **Class I** – simplified empirical structural weight model  
- **Class II** – detailed FLOPS-based component weight estimation  


---

# 1. Overview of the Weight Estimation Process

PhlyGreen solves for the takeoff weight that satisfies the aircraft mass balance:

\[
W_{\text{TO}}^{(i+1)} = 
W_{\text{payload}}
+ W_{\text{crew}}
+ W_{\text{structure}}(W_{\text{TO}}^{(i)})
+ W_{\text{powertrain}}(W_{\text{TO}}^{(i)})
+ W_{\text{fuel}}(W_{\text{TO}}^{(i)})
+ W_{\text{battery}}(W_{\text{TO}}^{(i)})
+ W_{\text{reserve}}
\]

where it is evident that the fuel, battery, structure, and powertrain masses depend on the takeoff weight. 
More specifically, fuel and battery masses are solved for in the mission workflow, while the structure and powertrain masses are computed afterwards in the weight workflow.

This is rewritten into a root-finding function:

\[
f(W_{\text{TO}}) =
W_{\text{payload}} + W_{\text{crew}}
+ W_{\text{structure}} + W_{\text{PT}}
+ W_{\text{fuel}} + W_{\text{battery}} + W_{\text{reserve}}
- W_{\text{TO}}
\]

The algorithm finds \( W_{\text{TO}}^{\star} \) such that:

\[
f(W_{\text{TO}}^{\star}) = 0
\]

using the **Brent root-finding method**. Each iteration, thus, requires the evaluation of the mission workflow.

---

# 2. Weight Breakdown Components

PhlyGreen aggregates all mass contributions:

| Component | Traditional | Hybrid |
|----------|-------------|--------|
| Fuel weight | ✓ | ✓ |
| Battery weight | ✗ | ✓ |
| Structural weight | ✓ | ✓ |
| Powertrain weight | ✓ | ✓ thermal + electric |
| Payload + crew | ✓ | ✓ |

Each component is recomputed at every iteration of WTO, except for the payload and crew, which are given as input requirements by the user.

---

# 3. Fuel Weight from Mission Energy

The **Mission** module returns the energy required, in [J], depending on the aircraft configuration:

- Traditional:

```python
  E_f = mission.EvaluateMission(WTO)
```

- Hybrid:

```python
  (E_f, E_bat) = mission.EvaluateMission(WTO)
```

The fuel mass is computed as:

\[
W_f = \frac{E_f}{e_f}
\]

with \( e_f \) the fuel LHV [J/kg].

If user does not specify a final reserve:

\[
W_{\text{reserve}} = 0.05\, W_f
\]

---

# 4. Battery Weight in Hybrid Configurations


The battery mass computation differs between Class I and Class II models:

- Class I: Battery mass must satisfy **both** energy and peak power requirements:

\[
W_{\text{bat}}
=
\max\left(
\frac{E_{\text{bat}}/(1-\text{SOC}_{\min})}{e_{\text{bat}}},
\quad
\frac{P_{\text{peak}}}{p_{\text{bat}}}
\right)
\]

where:

- \( e_{\text{bat}} \): battery specific energy [Wh/kg] 
- \( p_{\text{bat}} \): battery specific power [W/kg]  
- \( P_{\text{peak}} \): maximum electrical power demanded [W], stored in `mission.Max_PBat` by the mission module. 

The code stores which term dominates (`WBatidx`).

- Class II: Battery mass is computed by the battery sizing loop in the mission module and accessed via the `battery.pack_weight` attribute.

---

# 5. Powertrain Weight

For both traditional and hybrid aircraft, powertrain mass scales with subsystem specific powers, hence it is a Class I estimation:

\[
W_{\text{PT}}
=
\frac{P_{\text{thermal,max}}}{SP_{\text{thermal}}}
+
\frac{P_{\text{electric,max}}}{SP_{\text{electric}}}
\]


---

# 6. Structural Weight Models

## 6.1 Class I Model

The structural mass is computed with semi-empirical functions of the takeoff mass. 

\[
W_{\text{structure}} = f(W_{\text{TO}})
\]

The function is accessed via the `structures.StructuralWeight(WTO)` method.

Class I is fast and used for conceptual studies.


---

## 6.2 Class II Model — FLOPS Implementation

If `Class == "II"`, the code uses **FLOPS_model.py**, which estimates the masses of:

- Wing  
- Fuselage  
- Horizontal / vertical tail  
- Landing gear  
- Nacelle assemblies  
- Propellers  
- Systems and equipment  
- Paint  

The FLOPS component masses (in lb) are summed and converted to kg:

\[
W_{\text{structure}} = \sum_i W_{i,\text{FLOPS}}
\]

This model captures:

- aerodynamic load scaling  
- geometric effects  
- structural layout assumptions  

---

# 7. Brent Root-Finding Loop

PhlyGreen solves:

\[
f(W_{\text{TO}}) = 0
\]

with:

```python
self.WTO = brenth(func, WTO_min, WTO_max, xtol=0.1)
```

The function returns:

```python
W_total - WTO
```

