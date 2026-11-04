# Thermal Management (Fuel-Cell TMS)

A PEM fuel cell converts roughly half of the hydrogen energy into electricity; the rest is
low-temperature heat that the thermal-management system (TMS) must reject. PhlyGreen offers
two TMS models for the fuel-cell configurations (`'Hydrogen'` and `'FuelCellBattery'`),
selected with `TMSConfig(tms_class=...)` (legacy key `TMSInput['TMS Class']`):

| | Class I (default) | Class II |
|---|---|---|
| Model | specific power | geometric heat exchangers (FC_SPEC architecture) |
| Mass | \(Q_{\text{peak}} / \text{specific power}\) | exchanger cores + pump + pump motor |
| Drag | none | ram-air duct drag, added to the drag polar |
| Power | none | coolant pump, an electrical load on the fuel cell |
| Needs | nothing | CoolProp |
| Cost | negligible | ≈ 0.3 s per TMS sizing, ≈ 1 min per aircraft design |

---

## 1. Using the Class-II TMS

### Typed configuration

Attach a `TMSConfig` to the `AircraftConfig` of a fuel-cell aircraft. Every field except
`tms_class` is optional; see [Inputs](#5-inputs-tmsconfig-tmsinput) for the defaults.

```python
import PhlyGreen as pg
from PhlyGreen.config import TMSConfig
from common import hydrogen_config          # examples/common.py: the ATR-like hydrogen aircraft

config = hydrogen_config()
config.tms = TMSConfig(
    tms_class='II',                 # geometric model
    coolant='INCOMP::MEG-30%',      # any CoolProp fluid
    coolant_delta_t=10.0,           # [K] coolant temperature drop over the loop
    max_weight_per_unit=50.0,       # [kg] per heat-exchanger unit
    max_volume_per_unit=0.05,       # [m^3] per heat-exchanger unit
    ram_recovery=0.9,               # intake recovers 90 % of the dynamic pressure
)

aircraft = pg.build_aircraft()
aircraft.configure(config)          # sizes the aircraft with the Class-II TMS in the loop

r = aircraft.results()
print(f"MTOW {r.WTO:.0f} kg, TMS {r.tms_mass:.0f} kg (class {r.tms_class}), "
      f"pump {r.tms_pump_power/1e3:.1f} kW, ram drag {r.tms_ram_drag:.0f} N, "
      f"sized at '{r.tms_design_point}'")
aircraft.tms.report()

# The chosen hardware, rated at every mission point: heat to reject vs capacity.
tms, result = aircraft.tms, aircraft.weight.tms_result
for point in aircraft.mission.thermal_profile:
    q_cap, q_req = tms.RateAtPoint(result, point, capped=False)
    print(f"{point['name']:20s} required {q_req/1e3:7.0f} kW   capacity {q_cap/1e3:7.0f} kW")
```

Output (abridged):

```text
MTOW 22569 kg, TMS 1123 kg (class II), pump 32.8 kW, ram drag 171 N, sized at 'Mission/Climb1'
TMS Class II: design point 'Mission/Climb1' (Q_fc = 4633 kW)
  coolant_to_h2       :   1 x plate_fin            3.9 kg  0.0094 m3 per unit,   350.3 kW
  coolant_to_ram_air  :  32 x finned_tube_bank    33.5 kg  0.0495 m3 per unit,  4195.7 kW
  pump: 32.8 kW, 47.5 kg;  ram air: 83.4 kg/s, drag 171 N
  total TMS mass: 1122.8 kg
Takeoff              required    4103 kW   capacity    4642 kW
Mission/Climb1       required    4546 kW   capacity    4546 kW
Mission/Climb2       required    4944 kW   capacity    5100 kW
Mission/Cruise       required    1653 kW   capacity    5468 kW
...
```

The design point is the first climb segment. It is not the point with the most heat (that is
Climb2), but at 80 m/s it has the least ram air. The geometry sized there rejects the heat
everywhere else with margin, while a geometry sized at Climb2 would fall short at Climb1.
If even `max_hex_units` units cannot keep each unit within the mass/volume caps, the report
flags `[per-unit caps exceeded]` and a warning is issued; raise `max_hex_units` or the caps to
remove it.

### Legacy dictionaries

```python
aircraft.DesignAircraft(AerodynamicsInput, ConstraintsInput, MissionInput, EnergyInput,
                        MissionStages, DiversionStages,
                        TMSInput={'TMS Class': 'II', 'TMS Ram Recovery': 0.9})
```

Without `TMSInput` (or with `'TMS Class': 'I'`) the Class-I model is used.

### What the design exposes

| Where | What |
|---|---|
| `aircraft.results()` | `tms_class`, `tms_mass`, `tms_pump_power` [W], `tms_ram_drag` [N], `tms_design_point` |
| `aircraft.weight.WHeat_Exchanger` | TMS mass in the take-off-weight balance (the `cooling` item of the mass breakdown) |
| `aircraft.weight.tms_result` | the `FCThermalManagementResult`: `units` (per role: `design`, `n_parallel`, family, geometry), `mdot_coolant`, `mdot_ram_air`, `capture_area`, `pump_power`, `pump_mass`, `hex_mass`, `ram_drag`, `ram_drag_raw`, `heat_balance`, `candidates` (design-point selection table) |
| `aircraft.mission.thermal_profile` | the heat-load points the TMS is sized and rated on |
| `aircraft.fuelcell.P_aux_tms` | pump power carried by the fuel cell [W] |
| `aircraft.aerodynamics.extra_Cd` | ram-air drag increment on the polar |

### Sizing at a single point

The subsystem can also be used on its own, e.g. for trade studies at fixed conditions:

```python
tms = aircraft.tms                  # after configure(...) with tms_class='II'
point = {'name': 'climb', 'Q_fc': 4.0e6, 'altitude': 2000.0, 'V_inf': 100.0, 'mdot_h2': 0.05}
res = tms.SizeAtPoint(point)        # FCThermalManagementResult
print(res.total_mass, res.pump_power, res.ram_drag)
q_rejected, q_required = tms.RateAtPoint(res, {**point, 'altitude': 6000.0, 'V_inf': 130.0})
```

`examples/27_hydrogen_tms_class_ii.py` compares Class I and Class II on the same aircraft,
prints the design-point selection, plots the rating over the mission and shows the effect of
the intake ram recovery.

---

## 2. Heat load

The fuel-cell heat is the stack heat of the Kulikovsky cell model
(see [Hydrogen](hydrogen.md#4-heat-management)). `Mission` records it along the mission in
`mission.thermal_profile`, a list of points `{name, Q_fc, altitude, V_inf (TAS), mdot_h2}`:

- the **take-off/OEI point**, where the fuel cell delivers the worst-case off-mission power at
  the take-off constraint conditions (not flown by the profile);
- the **peak of each flown segment**, named `Mission/<stage>`, `Diversion/<stage>`, ....

`mission.TO_FC_Thermal_Pwr` and `mission.Max_FC_Thermal_Pwr` are the take-off and in-flight peaks.

## 3. Class I

\[
W_{\text{TMS}} = \frac{\max(Q_{\text{mission peak}},\; Q_{\text{take-off}})}{\text{HEX specific power}},
\]

with the specific power `EnergyConfig.hex_specific_power_h2` (default 5000 W/kg). The take-off
point is included because the fuel cell is sized there and rejects the most heat there.

## 4. Class II: the FC_SPEC architecture

```
stack ──coolant (T_op)──▶ [HEX 1: coolant → liquid H2] ──▶ [HEX 2: coolant → ram air] ──▶ pump ──▶ stack
```

At a design point with stack heat \(Q_{fc}\):

1. **Reactant heat.** Hydrogen and cathode air enter the stack below \(T_{op}\) and absorb
   \(q_{\text{react}} = \dot m_{H_2}\,[h(T_{op}) - h(T_{op}-\Delta T_{H_2})] + \dot m_{\text{air}}\,c_p\,(T_{op} - T_{\text{comp}})\).
   The cathode air flow follows from the hydrogen flow and the air stoichiometry, and
   \(T_{\text{comp}}\) is the compressor delivery temperature. The coolant rejects
   \(Q_{\text{ext}} = Q_{fc} - q_{\text{react}}\).
2. **Coolant loop.** The coolant leaves the stack at \(T_{op}\) and returns
   \(\Delta T_{\text{loop}}\) colder, so \(\dot m_c = Q_{\text{ext}}/(c_p\,\Delta T_{\text{loop}})\).
3. **HEX 1 (coolant → H2).** The fixed duty warms the hydrogen from saturated liquid at the
   supply pressure to \(T_{op} - \Delta T_{H_2}\):
   \(q_1 = \dot m_{H_2}\,[h(T_{op}-\Delta T_{H_2}) - h_{\text{sat,liq}}]\). Enthalpies are for
   para-hydrogen from CoolProp, so the latent heat is included. In the ε-NTU method the
   hydrogen carries an *effective* \(c_p = \Delta h / \Delta T\).
4. **HEX 2 (coolant → ram air).** This exchanger rejects the remainder \(q_2 = Q_{\text{ext}} - q_1\).
   The ram air enters at the free-stream total temperature and its temperature rise is
   \(\min(\Delta T_{\text{air}},\; \varepsilon_{\max}\,(T_{c,in} - T_{0}))\), which fixes the ram-air mass flow.
5. **Pump.** \(P_{\text{pump}} = \dot V_c\,\Delta p_{\text{loop}} / (\eta_{\text{pump}}\,\eta_{\text{motor}})\);
   the mass is \(P/\text{sp}_{\text{pump}} + P/\text{sp}_{\text{motor}}\).
6. **Ram-air drag.** This uses a Meredith-type momentum balance of the duct (`Systems/Thermal/ram_air.py`).
   The free stream is decelerated in the intake, which recovers a fraction \(\eta_{\text{ram}}\)
   of the dynamic pressure, \(p_{0,1} = p_\infty + \eta_{\text{ram}}(p_{0,\infty} - p_\infty)\).
   The air is heated at the core velocity (Rayleigh flow), loses the core pressure drop, and is
   expanded back to ambient pressure: \(D = \dot m\,(V_\infty - V_{\text{exit}})\). Negative
   values (net thrust) are reported in `ram_drag_raw` and clipped to zero in `ram_drag`.

### Exchanger sizing (`Systems/Thermal/hex.py`)

For each role, three families are sized and the lightest one that respects the per-unit
caps is kept:

| Family | Liquid side | Gas side | Arrangement |
|---|---|---|---|
| Plain tube bank (staggered, square pitch) | Gnielinski / laminar Nu = 3.66 | Zukauskas, with row correction; Jakob pressure drop (as given in Holman) | cross-flow, gas mixed |
| Annular-finned tube bank (Al fins, steel tubes) | Gnielinski / laminar Nu = 3.66 | Briggs & Young; Schmidt fin efficiency | cross-flow, gas mixed |
| Plate-fin (Al, offset-strip fins) | plain channel, Gnielinski / laminar Nu = 7.54 | Manglik & Bergles j and f | counterflow |

- **ε-NTU.** The relations are the closed forms of Incropera's Table 11.3. For cross-flow with
  one stream mixed, the relation depends on whether the mixed (gas) stream has the smaller or
  the larger heat-capacity rate.
- **Layout.** The design velocities (1.75 m/s for liquids, 15 m/s for gases) fix the flow
  areas: tube circuits, the gas face area, and the number of plate-fin layers. The required
  area then fixes the bank depth or the core length. The fin pitch is set from the fin
  diameter, so adjacent fins never overlap, and the fin densities stay within the tested
  range of Briggs & Young.
- **Self-consistency.** U is recomputed from the real velocities of the built layout, and the
  area is iterated until the two agree. Sizing and rating use the same layout and
  correlations, so rating a unit at its own design point returns its design duty.
- **Reference area.** U is referred to the gas-side area; the liquid-side and wall resistances
  are scaled by the area ratio.
- **Parallel units.** Each role uses the fewest identical units in parallel such that one unit
  respects `max_weight_per_unit` and `max_volume_per_unit`. If even `max_hex_units` units
  cannot, the units are allowed to exceed the caps and a warning is issued.
- **Pressure-drop limits.** The air-side pressure drop is limited to the recovered dynamic
  pressure, \(\eta_{\text{ram}}\,q_\infty\). The H2 side is limited to 10 kPa and the liquid
  side to the loop pressure rise.

### Design point

The hardware must reject the heat at every mission point, and the point with the most heat is
not necessarily the one that needs the heaviest exchangers. `tms.SizeForMission(profile)`:

1. sizes the TMS at every point of `thermal_profile` carrying at least half of the peak heat;
2. **rates** each geometry at every point, with the hardware fixed: the coolant flow is set by
   the pump, the air flow by the intake capture area (\(\dot m = \rho V A_{\text{capture}}\),
   flap fully open), and U is recomputed at the new flows;
3. keeps the lightest geometry whose worst shortfall is within 2 %. If none qualifies, it keeps
   the least-short one and issues a warning.

### Coupling to the aircraft

`Weight._fuel_cell_and_tms_closure` is shared by `Weight.Hydrogen` and
`Weight.FuelCellBattery`, so a battery-free fuel-cell + battery design is identical to the
hydrogen one. Each weight iteration repeats the following until the fuel-cell power, the pump
power and the drag increment all converge:

1. fly the mission;
2. size the TMS from the thermal profile;
3. set the pump power as `fuelcell.P_aux_tms`, a constant electrical load. It is added to the
   electrical demand at every operating point and to the stack rating, so its hydrogen is
   flown and the stack is sized for it;
4. set the ram drag as `aerodynamics.extra_Cd`, \(D / (q_{\text{design}}\,S)\) with
   \(S = W_{TO}\,g/(W/S)\). A constant ΔCd scales the duct drag with the dynamic pressure at
   every flight condition;
5. resize the fuel cell.

The constraint diagram is computed before the weight loop, so the duct drag does not move the
design point (W/S, P/W). It does act on the mission, the take-off and the OEI powers.

## 5. Inputs (`TMSConfig` / `TMSInput`)

| Field | Legacy key | Default | Meaning |
|---|---|---|---|
| `tms_class` | `TMS Class` | `'I'` | `'I'` or `'II'` |
| `coolant` | `TMS Coolant` | `INCOMP::MEG-30%` | CoolProp coolant name |
| `coolant_delta_t` | `TMS Coolant DeltaT` | 10 K | coolant temperature drop over the loop |
| `max_volume_per_unit` | `TMS Max Volume Per Unit` | 0.05 m³ | per-unit volume cap |
| `max_weight_per_unit` | `TMS Max Weight Per Unit` | 50 kg | per-unit mass cap |
| `max_hex_units` | `TMS Max HEX Units` | 100 | max parallel units per role |
| `ram_air_delta_t` | `TMS Ram Air DeltaT` | 50 K | design ram-air temperature rise |
| `ram_air_max_effectiveness` | `TMS Ram Air Max Effectiveness` | 0.8 | cap on that rise, as a fraction of the inlet ΔT |
| `h2_approach_delta_t` | `TMS H2 Approach DeltaT` | 30 K | H2 leaves HEX 1 at \(T_{op}\) minus this |
| `h2_supply_pressure` | `TMS H2 Supply Pressure` | 1.6 bar | LH2 enters HEX 1 saturated at this pressure |
| `loop_pressure_drop` | `TMS Loop Pressure Drop` | 2 bar | pump pressure rise (stack, piping, cores) |
| `pump_efficiency` | `TMS Pump Efficiency` | 0.75 | |
| `pump_motor_efficiency` | `TMS Pump Motor Efficiency` | 0.95 | |
| `pump_specific_power` | `TMS Pump Specific Power` | 800 W/kg | |
| `pump_motor_specific_power` | `TMS Pump Motor Specific Power` | 5000 W/kg | |
| `ram_recovery` | `TMS Ram Recovery` | 1.0 | fraction of the dynamic pressure the intake recovers |
| `takeoff_coolant_overtemperature` | `TMS Takeoff Coolant Overtemperature` | 0 K | coolant/stack allowed above \(T_{op}\) at the take-off point only |

None of the defaults is calibrated against flight hardware.

## 6. Limitations

- **Core-only mass.** Headers, manifolds, ducts, piping, the coolant inventory and the
  mounting structure are not included.
- **No fouling resistance.** The finned-bank air-side friction factor (\(f = 1.5\,Re^{-0.2}\))
  is an approximation without a literature source.
- **Drag is a lower bound.** With the default ideal intake (`ram_recovery = 1`), the Meredith
  heating can recover more momentum than the core loses, and the clipped drag is zero. There is
  no spillage or cowl drag, so use `ram_recovery < 1` for a realistic duct.
- **No fans.** Take-off and low-speed points are cooled by ram air only. When take-off is the
  largest heat load at the lowest speed, it sizes the exchangers. Two levers reduce that
  penalty:
  - letting the coolant run hotter for the short take-off phase
    (`takeoff_coolant_overtemperature`; e.g. 95 °C against 80 °C nominal);
  - covering part of the take-off power with a battery (`'FuelCellBattery'` with a take-off
    `phi`).
  When the power requirement comes from the climb rather than the take-off, the climb point
  sizes the TMS and neither lever has an effect.
- **Coolant freezing is not modelled.** HEX 1 has a water-glycol coolant facing hydrogen at
  ≈ 20 K. A real design needs an intermediate loop or a non-freezing coolant.
- **Physics not included.** Ortho/para conversion is not modelled (pure para-hydrogen
  enthalpies). The stack is assumed to hold \(T_{op}\) at all loads. There are no transients.
