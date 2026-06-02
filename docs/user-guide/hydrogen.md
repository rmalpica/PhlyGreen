# Hydrogen: Fuel Cell & Tank

PhlyGreen models hydrogen-electric aircraft in two configurations: a pure fuel-cell
(`'Hydrogen'`) and a fuel-cell + battery hybrid (`'FuelCellBattery'`). The model is a
physics-based PEM fuel-cell system (`Systems/FuelCell/FuelCell.py`) plus an optional cryogenic
liquid-hydrogen tank (`Systems/Tank/`).

---

## 1. The polarization curve

The heart of the model is the **cell voltage** as a function of current density, computed with
the analytical **Kulikovsky / Massaro** model (`FuelCell.PolarizationCurve(i, P, T)`). Starting
from the open-circuit voltage \(V_{oc}\), three loss mechanisms are subtracted:

\[
V_{\text{cell}}(j) = V_{oc} \;-\; \underbrace{R_{\Omega}\,j}_{\text{ohmic}}
\;-\; \underbrace{\eta_{0}(j)}_{\text{activation + O$_2$ transport}}
\;-\; \underbrace{V_{\text{conc}}(j)}_{\text{concentration}}
\]

- **Ohmic loss** \(R_\Omega j\) — membrane/contact resistance, linear in current density.
- **Activation + oxygen-transport loss** \(\eta_0(j)\) — the Kulikovsky closed-form for the
  catalyst layer, built from the Tafel slope \(b\), the proton conductivity \(\sigma_t\), the
  catalyst-layer thickness \(l_t\), the reference O₂ concentration and the local oxygen
  diffusivity. The cathode oxygen concentration scales with the **cathode pressure**
  (\(c_h = c_{h,\text{ref}}\,p/p_{\text{ref}}\)), so running the cathode pressurized improves
  performance.
- **Concentration loss** \(V_{\text{conc}}(j) = -B\ln(1 - j/j_{\text{lim}})\) — the steep
  drop as the limiting current density \(j_{\text{lim}}\) is approached.

The cell and chemistry constants come from `FC_Database` (`Systems/FuelCell/FC_Models.py`,
selected via `fc_model`). Plot the curve as in example `20_hydrogen_fuel_cell.py`:

```python
for j in (0.1, 0.5, 1.0, 1.5, 2.0):
    print(j, fc.PolarizationCurve(j, fc.Target_Press))
```

---

## 2. Designing the stack — the role of the design voltage

The fuel-cell stack is sized in `ComputeAndStoreWeights(WTO)`. The key design knob is the
**design cell voltage** \(V_{\text{cell,design}}\) (`v_cell_design`):

1. the **rated net power** \(P_{\text{fc,rated}}\) follows from the design power-to-weight and
   WTO;
2. the **design current density** is the point on the polarization curve at
   \(V_{\text{cell,design}}\) (solved with Brent), bounded by the rated current density
   `i_rated`;
3. the **surface power density** is \(p_s = V_{\text{cell,design}}\cdot j_{\text{design}}\)
   [W/cm²], from which the **total active area**, the **number of cells** \(N_{\text{cells}}\)
   and the per-cell area \(A_{\text{cell}}\) are obtained;
4. the **stack mass** follows from the area-specific power density (`stack_power_density`), and
   the **balance-of-plant** mass is `bop_mass_ratio` × stack, plus motor + PMAD.

There is a genuine **design trade**: a *higher* design voltage runs each cell at a lower
current density (locally more efficient), but needs more active area / a heavier stack to make
the rated power — and a heavier powertrain needs more hydrogen, which needs a bigger stack, so
the design can **snowball**. The result is a take-off-weight **optimum** at a moderate design
voltage (very high voltages fail to close). Example `21_hydrogen_design_voltage_sweep.py` sweeps
it.

```python
energy = EnergyConfig(
    Ef=120e6,                       # hydrogen lower heating value [J/kg]
    eta_gearbox=0.96, eta_pmad=0.99, eta_electric_motor=0.96,
    fc_model='PEMFC_GoodPerformance',
    i_rated=2.5,                    # rated current density [A/cm^2]
    v_cell_design=0.5,              # design cell voltage [V]  <-- the key sizing knob
    stack_power_density=3000,       # area-specific stack power [W/kg]
    bop_mass_ratio=0.40,            # balance-of-plant / stack mass
)
```

---

## 3. The air system (compressor) and net system efficiency

PEM fuel cells run the cathode **pressurized**, which costs parasitic power. The air system
(`_compute_air_system_power`) sizes a **compressor** to raise ambient air to the cathode
pressure and a **turbine** that recovers part of the energy from the pressurized exhaust:

\[
\dot m_{\text{air}} \propto N_{\text{cells}}\,I\,\lambda, \qquad
P_{\text{comp}} = \frac{\dot m_{\text{air}}\,c_{p}\,T_{\text{amb}}\,(\Pi^{0.286}-1)}{\eta_{\text{comp}}},
\qquad
P_{\text{comp,net}} = P_{\text{comp}} - P_{\text{turb}}
\]

with stoichiometry \(\lambda\), pressure ratio \(\Pi = p_{\text{cathode}}/p_{\text{amb}}\). The
compression demand grows with altitude (lower \(p_{\text{amb}}\)), so it is a real part of the
operating-point dependence.

The **net system efficiency** is the gross stack power minus the air-system (and PMAD) parasitics
over the hydrogen chemical power:

\[
\eta_{\text{sys}} = \frac{P_{\text{gross}} - P_{\text{comp,net}}}{\dot m_{\text{H}_2}\,\text{LHV}},
\qquad P_{\text{gross}} = N_{\text{cells}}\,V_{\text{cell}}\,I .
\]

For the mission, `ComputePRatio(alt, vel, P_net)` solves for the operating current density that
delivers the required **net** shaft power at the current flight condition and returns the
hydrogen *chemical* power required (i.e. \(1/\eta_{\text{sys}}\) of the net power), so the
mission integrates hydrogen energy consistently.

---

## 4. Heat management

A fuel cell is roughly half-efficient, so it rejects a large heat load. The waste heat is the
difference between the thermo-neutral voltage (~1.48 V) and the operating cell voltage:

\[
Q_{\text{thermal}} = N_{\text{cells}}\,I\,(1.48 - V_{\text{cell}}) .
\]

Because \(V_{\text{cell}}\) falls with load and altitude, the heat load peaks where the system
works hardest. The weight loop sizes the **cooling-system mass** (`WHeat_Exchanger`) from the
peak mission heat and a **specific power** (heat per kg of HEX),
\(W_{\text{cool}} = Q_{\text{peak}} / \text{HEX specific power}\). Because the cryogenic H2 is a
very effective heat sink, the fuel-cell HEX is light per kW: `EnergyConfig.hex_specific_power_h2`
defaults to **5000 W/kg** (vs ~1500 W/kg for a battery HEX rejecting to ambient — see
[Battery](battery.md)). Even so, a multi-MW fuel cell rejects a large heat load, so the TMS is a
significant mass. The heat also registers as a source for the thermal-management scaffold (below).

---

## 5. Mission and weight closure

`Mission.HydrogenConfiguration` integrates the hydrogen chemical energy over the mission, and
the weight loop `Weight.Hydrogen` closes the take-off weight over

\[
W_{TO} = W_{\text{struct}} + W_{\text{FC system}} + W_{\text{H}_2} + W_{\text{tank}}
         + W_{\text{cooling}} + W_{\text{payload}} + W_{\text{crew}} + W_{\text{reserve}} .
\]

**Fuel-cell sizing is self-consistent and constraint-aware.** Inside each weight iteration the
stack is *not* sized to the mission peak alone: it is sized to the worst case of the **mission
peak, the take-off** (field length) **and the OEI climb** — the latter two evaluated at the
constraint conditions, since they are not flown by the mission profile but the fuel cell must
still supply their power. To keep the *flown* fuel cell and the *weighed* fuel cell the same,
the loop is `SizeFromConstraint` (seed) → fly → `SizeForPropulsivePower(max(mission, take-off,
OEI))` → re-fly until the required power converges. A single, explicit margin
(`FuelCell.SizingMargin`, default 1.0) is applied — there are no hidden oversizing factors.

See example `20_hydrogen_fuel_cell.py`.

---

## 6. Cryogenic LH2 tank

Hydrogen is stored as a cryogenic liquid (~20 K). `Systems/Tank/` provides `LH2_Tank`:
structural + multi-layer-insulation (MLI) sizing (after Svensson et al.) and a transient
`time_step` model of the tank thermodynamic state:

- **heat ingress** through the insulation slowly boils the liquid and **self-pressurizes** the
  tank;
- a **vent valve** opens at the maximum pressure \(P_{\max}\) (venting gas, a fuel loss);
- a **heater** adds power at the minimum pressure \(P_{\min}\) to keep feed pressure up.

It requires **CoolProp** (para-hydrogen properties) and is therefore optional: with a
`TankConfig` and CoolProp installed it is used for sizing (reporting the **gravimetric index**
H₂/(H₂+tank), geometry and pressure limits); otherwise a simple gravimetric-index mass model is
used so the design always closes.

```python
from PhlyGreen.config import TankConfig
config.tank = TankConfig(max_diameter=2.4, number_of_tanks=1, tank_model='Svensson_Default')
```

To watch the tank state evolve over the mission, switch on tracking and re-fly:

```python
aircraft.configure(config)                       # sizes the tank
aircraft.mission.track_tank = True
aircraft.mission.EvaluateMission(aircraft.weight.WTO)
from PhlyGreen import postprocess as pp
pp.plot_tank_state(aircraft)                      # pressure / mass / vent vs time
```

See example `22_hydrogen_tank.py` and notebook `03_hydrogen_fuel_cell.ipynb`.

---

## 7. Fuel cell + battery hybrid

`'FuelCellBattery'` splits the propulsive power between the fuel cell and a (Class-I) battery
via the profile's supplied-power ratio φ (the battery fraction). The fuel cell uses its physics
efficiency above; the battery is sized from its energy and power needs. The fuel cell is sized
(by the same self-consistent loop as the pure-hydrogen path) to the worst of its *own share*
`(1−φ)` of the mission peak, take-off and OEI — so a larger φ *shrinks the stack*, but never
below the `(1−φ)` share of the take-off/OEI floor. Because the battery stores little energy per
kg, hybridization helps short power-limited segments more than sustained cruise. A φ = 0
`FuelCellBattery` design reproduces a pure `Hydrogen` design exactly.
See example `23_fuelcell_battery_hybrid.py`.

---

## 8. Thermal management (scaffold)

`Systems/Thermal/` provides the interfaces for a future heat-exchanger-network module
(`HeatSource`, `HeatSink`, `HeatExchangerNetwork`). The fuel cell's heat load and the tank's
heat leak can register as sources today; a detailed coolant-loop sizing model will plug into
the same interfaces.

---

## References

- Kulikovsky, A. A. *A physically–based analytical polarization curve of a PEM fuel cell.*
  Journal of The Electrochemical Society, 161(3):F263–F270, 2014.
- Massaro et al. *Analytical modelling of PEM fuel-cell systems for aircraft.*
- Svensson, F. *Potential of reducing the environmental impact of civil subsonic aviation by
  using liquid hydrogen.* (LH2 tank sizing.)
