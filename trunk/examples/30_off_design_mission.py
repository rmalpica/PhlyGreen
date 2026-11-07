"""Example 30 — Off-design missions: fly a sized aircraft on a different mission.

A design is sized for its *nominal* mission (here 750 nm). In service it mostly flies
shorter *typical* missions. This example freezes a sized aircraft (structure, powertrain,
fuel cell, battery pack, tank and OEW all fixed) and flies it on another mission: another
range, payload or power-split (phi) schedule. It returns the fuel burnt and checks that the
frozen aircraft can actually fly it.

``fly_off_design`` is the building block for multi-point studies (outer loop: design
variables -> sized aircraft; inner loop: off-design operating strategy -> fuel burn). It
works for every configuration with a fuel: 'Traditional', 'Turbofan', 'Hydrogen',
'FuelCellBattery' and 'Hybrid' (parallel or serial with a phi split), with Class-I or Class-II
batteries.

How the off-design mass is closed. The take-off mass is

    WTO_off = OEW + payload + crew + fuel load + final reserve ,

with the OEW and the final reserve of the design, and the fuel load equal to what the mission
burns (trip + diversion + ground segments). The H2 sizing margin (``h2_fuel_margin``) is a
design allowance on the tank and is not loaded off-design. The fuel depends weakly on
WTO_off (a few percent of it), so a fixed-point iteration converges to 1 kg in 3-4 missions.

What is checked (``result.violations``; empty = feasible):

- take-off mass <= the design MTOW;
- fuel load <= the design fuel load (the tank is sized for it);
- Class-I battery: energy drawn <= usable energy of the pack, peak power <= its power
  capability. Class-II battery: the pack is frozen (``mission.size_battery_pack = False``) and
  the cell model itself enforces SOC, voltage, current and temperature limits;
- thermal engine: it never delivers more shaft power than it did at design (mission peak or
  take-off share), a conservative proxy for its rating (the engine model has no explicit
  power limit);
- fuel cell: the stack can deliver the demand at every point (not power-limited at its
  present state of health, the limit of the same polarization model that sized it), and the
  TMS rejects its heat. A stack sized on the take-off or OEI floor may deliver more than the
  design mission peak, so the mission peak is not used as a limit. With a Class-I TMS the peak heat
  must not exceed the heat the TMS was sized for; with a Class-II TMS the design hardware is
  checked (``ThermalManagementSystem.CheckAtPoint``) at every point of the flown thermal
  profile and at every accepted integration point of the flown mission. It must reject the
  heat within its feasibility tolerance, its cores must fit in the coolant-loop pressure
  budget and in the recovered dynamic pressure, and the ram-air duct must not choke. The
  Class-II hardware has no margin at its design point, so comparing peak heats would not be
  conservative. A coolant-side wall below the coolant freezing point is reported in
  ``risks``, not as a violation: the wall-temperature estimate is too coarse to decide it.
  The duct drag is not checked point by point (the aircraft carries it as a constant drag
  increment, conservative over the mission).

Degraded flights. ``state_of_health`` sets the degradation of the flown copy, relative to
beginning of life (BOL), with the keys of ``EnergyConfig``: ``fc_voltage_loss`` [V],
``fc_ohmic_resistance_factor``, ``fc_exchange_current_factor``, ``battery_capacity_fraction``
and ``battery_resistance_factor``. Keys not given keep the design's state. A design sized at
end of life (those fields set in its ``EnergyConfig``) is flown at BOL by passing the neutral
values (0 V, 1.0). A degraded stack burns more hydrogen and rejects much more heat at the same
power, so the heat and the stack power limit usually bind before the tank does.

Fuel reported: ``trip_fuel`` is burnt from taxi-out to taxi-in on the off-design mission (the
diversion is carried, not flown); ``fuel_load`` adds the diversion fuel.

The demo designs a fuel-cell + battery aircraft with a take-off battery (on the 800 m field
of example 23, where it pays) and the Class-I parallel GT hybrid, and flies each one on
shorter missions, with the design phi schedule and with the cruise phi raised until the
frozen battery is fully used. Run it:

    cd trunk && python examples/30_off_design_mission.py
"""

import copy
from dataclasses import dataclass, field

import numpy as np

import PhlyGreen as pg
from PhlyGreen.Systems.Thermal.TMS import limit_violations, limit_risks
from common import fuelcell_battery_config, hybrid_config, savefig


@dataclass
class OffDesignResult:
    range_nm: float
    WTO: float                  # off-design take-off mass [kg]
    trip_fuel: float            # fuel burnt on the mission, ground segments included [kg]
    fuel_load: float            # trip + diversion fuel loaded [kg]
    battery_energy_kWh: float   # electrical energy drawn from the battery [kWh]
    battery_soc_used: float     # fraction of the pack's usable energy (Class I), else nan
    missions_flown: int
    violations: list = field(default_factory=list)
    risks: list = field(default_factory=list)   # flagged, not limits (e.g. coolant freezing)

    @property
    def feasible(self):
        return not self.violations


FC_STATE_KEYS = {"fc_voltage_loss": "voltage_loss",
                 "fc_ohmic_resistance_factor": "ohmic_resistance_factor",
                 "fc_exchange_current_factor": "exchange_current_factor"}
BATTERY_STATE_KEYS = {"battery_capacity_fraction": "capacity_fraction",
                      "battery_resistance_factor": "resistance_factor"}


def _set_state_of_health(aircraft, state):
    """Apply ``state`` ({EnergyConfig key: value}) to the fuel cell and the battery of
    ``aircraft``; keys not given keep their present value."""
    state = dict(state or {})
    unknown = set(state) - set(FC_STATE_KEYS) - set(BATTERY_STATE_KEYS)
    if unknown:
        raise ValueError(f"unknown state-of-health keys: {sorted(unknown)}")
    fc = getattr(aircraft, "fuelcell", None)
    if fc is not None and any(k in state for k in FC_STATE_KEYS):
        fc.set_state_of_health(**{arg: state.get(key, getattr(fc, arg))
                                  for key, arg in FC_STATE_KEYS.items()})
    b = aircraft.battery
    if any(k in state for k in BATTERY_STATE_KEYS):
        b.set_state_of_health(**{arg: state.get(key, getattr(b, arg))
                                 for key, arg in BATTERY_STATE_KEYS.items()})


def _fc_design_heat(mission):
    """Largest fuel-cell heat [W] over the mission and the take-off point (the Class-I TMS is
    sized on it)."""
    return max(mission.Max_FC_Thermal_Pwr, mission.TO_FC_Thermal_Pwr)


def _tms_violation(aircraft, fc_heat_design):
    """TMS check of a flown fuel-cell mission; returns (violation messages, risk messages),
    each an empty list when there is none.

    Class II: check the design hardware (``weight.tms_result``) at every point of the flown
    thermal profile and of the flown mission (``ThermalManagementSystem.CheckAtPoint``).
    Violations: heat, core pressure drops, duct choking. Risk: coolant freezing.
    Class I: compare the peak heat with the heat the TMS was sized for.
    """
    m, result = aircraft.mission, aircraft.weight.tms_result
    if result is not None:
        tms = aircraft.tms
        checks = [tms.CheckAtPoint(result, point)
                  for point in m.thermal_profile + m.thermal_history]
        return ([f"Class-II {message}" for message in limit_violations(checks)],
                [f"Class-II TMS {message}" for message in limit_risks(checks)])
    fc_heat = _fc_design_heat(m)
    if fc_heat > fc_heat_design * (1 + 1e-3):
        return ([f"fuel-cell heat {fc_heat/1e3:,.0f} kW > TMS design heat "
                 f"{fc_heat_design/1e3:,.0f} kW"], [])
    return [], []


def _battery_limits(aircraft):
    """Usable energy [J] and power capability [W] of a Class-I pack (None if no battery),
    at the pack's present state of health."""
    w, cfg = aircraft.weight, aircraft.Configuration
    if not getattr(w, "WBat", None):
        return None, None
    if cfg == "FuelCellBattery":
        e, b = aircraft.EnergyInput, aircraft.battery
        energy = (w.WBat * e.get("Battery Specific Energy", 250.0) * b.capacity_fraction * 3600.0
                  * e.get("Battery Usable SOC", 0.8))
        power = w.WBat * e.get("Battery Specific Power", 1500.0) / b.resistance_factor
        return energy, power
    b = aircraft.battery                                    # Hybrid, Class I
    return w.WBat * b.Ebat * (1.0 - b.SOC_min), w.WBat * b.pbat


def _fuel_energy_at(mission, t_end):
    """Cumulative fuel energy [J] at time ``t_end`` of the flown profile."""
    for sol in mission.integral_solution:
        if sol.t[0] <= t_end <= sol.t[-1] + 1e-6:
            return float(np.interp(t_end, sol.t, sol.y[0]))
    return float(mission.integral_solution[-1].y[0][-1])


def _set_phi(stages, phi):
    """Override the phi of the stages named in ``phi`` ({stage: value or (start, end)})."""
    for name, value in (phi or {}).items():
        spr = stages[name]["Supplied Power Ratio"]
        if "phi" in spr:                                    # the 'Takeoff' entry
            spr["phi"] = float(value if np.isscalar(value) else value[0])
        else:
            start, end = (value, value) if np.isscalar(value) else value
            spr["phi_start"], spr["phi_end"] = float(start), float(end)


def fly_off_design(sized, range_nm, payload_kg=None, phi=None, state_of_health=None,
                   tol_kg=1.0, max_iter=20):
    """Fly the frozen design ``sized`` on another mission. ``sized`` is not modified.

    range_nm   : off-design mission range [nm] (the diversion is the design one).
    payload_kg : off-design payload [kg] (default: the design payload).
    phi        : {stage name: phi or (phi_start, phi_end)} overriding the design schedule,
                 e.g. {"Takeoff": 0.15, "Cruise": 0.3}. Stages not listed keep their value.
    state_of_health : {EnergyConfig key: value} degradation of the flown aircraft relative to
                 BOL, e.g. {"fc_voltage_loss": 0.05, "battery_capacity_fraction": 0.8}.
                 Keys not given keep the design's state.
    """
    if sized.Configuration == "Hybrid" and sized.EnergyInput.get("GT Rated Power"):
        raise NotImplementedError("the serial range-extender strategy has no phi split to fly")
    w = sized.weight
    design_fuel = w.Wf
    oew = w.WTO - w.Wf - w.final_reserve - w.WPayload - w.WCrew
    design_pk_engine = max(sized.mission.Max_PEng, getattr(sized.mission, "TO_PP", 0.0) or 0.0)
    class_ii = getattr(sized.battery, "BatteryClass", None) == "II" and (w.WBat or 0) > 0
    fc_heat_design = _fc_design_heat(sized.mission) if sized.fuelcell is not None else None

    a = copy.deepcopy(sized)
    _set_state_of_health(a, state_of_health)
    e_bat_max, p_bat_max = _battery_limits(a)
    if a.fuelcell is not None:
        a.fuelcell.reset_adequacy()
    a.MissionInput["Range Mission"] = range_nm
    payload = w.WPayload if payload_kg is None else payload_kg
    a.MissionInput["Payload Weight"] = payload
    _set_phi(a.MissionStages, phi)
    a.mission.size_battery_pack = False                     # Class II: fly the frozen pack
    a.mission.InitializeProfile()        # raises ValueError if the range is shorter than climb + descent

    wto, n, violations = w.WTO, 0, []
    for n in range(1, max_iter + 1):
        out = a.mission.EvaluateMission(wto)
        e_fuel = out[0] if isinstance(out, tuple) else out
        if e_fuel == 0:                                     # Class-II pack limit hit
            violations.append(f"battery limit (Class-II cell model, code {out[1]})")
            break
        fuel = e_fuel / a.mission.ef
        wto_new = oew + payload + w.WCrew + fuel + w.final_reserve
        converged = abs(wto_new - wto) < tol_kg
        wto = wto_new
        if converged:
            break

    if violations:
        return OffDesignResult(range_nm, wto, np.nan, np.nan, np.nan, np.nan, n, violations)

    m = a.mission
    trip = (_fuel_energy_at(m, m.profile.MissionTime) + m.E_ground) / m.ef
    e_bat = float(out[1]) if isinstance(out, tuple) and len(out) > 1 else 0.0
    if np.ndim(e_bat):
        e_bat = float(np.asarray(e_bat)[-1])
    soc_used = np.nan
    if wto > w.WTO + tol_kg:
        violations.append(f"take-off mass {wto:,.0f} kg > MTOW {w.WTO:,.0f} kg")
    if fuel > design_fuel + 0.5:
        violations.append(f"fuel load {fuel:,.0f} kg > design fuel load {design_fuel:,.0f} kg")
    if e_bat_max and not class_ii:
        soc_used = e_bat / e_bat_max
        if soc_used > 1.0 + 1e-3:
            violations.append(f"battery energy {e_bat/3.6e6:,.0f} kWh > usable {e_bat_max/3.6e6:,.0f} kWh")
        p_bat = max(m.Max_PBat, getattr(m, "TO_PBat", 0.0) or 0.0)
        if p_bat > p_bat_max * (1 + 1e-3):
            violations.append(f"battery power {p_bat/1e3:,.0f} kW > capability {p_bat_max/1e3:,.0f} kW")
    fuel_cell = a.fuelcell is not None and a.Configuration in ("Hydrogen", "FuelCellBattery")
    pk_engine = max(m.Max_PEng, getattr(m, "TO_PP", 0.0) or 0.0)
    if not fuel_cell and pk_engine > design_pk_engine * (1 + 1e-3):
        violations.append(f"engine power {pk_engine/1e3:,.0f} kW > design {design_pk_engine/1e3:,.0f} kW")
    risks = []
    if fuel_cell:
        fc = a.fuelcell
        if fc._power_limited:
            violations.append(f"fuel cell power-limited: demand up to {fc._worst_load_ratio:.3f} "
                              f"of the deliverable power")
        tms_violations, tms_risks = _tms_violation(a, fc_heat_design)
        violations.extend(tms_violations)
        risks.extend(tms_risks)
    return OffDesignResult(range_nm, wto, trip, fuel, e_bat / 3.6e6, soc_used, n, violations,
                           risks)


def max_battery_phi(sized, range_nm, stage="Cruise", base_phi=None, step=0.1, tol=0.01):
    """Largest constant phi on ``stage`` the frozen design can fly, and that mission.

    A simple inner-loop strategy: on a mission shorter than the design one the pack has spare
    energy, which can displace fuel. Feasibility is not monotonic in phi (too little battery
    overfills the tank, too much empties the pack), so scan down from phi = 1 in ``step``s to
    the first feasible value, then bisect between it and the infeasible one above.
    Returns (None, last result) if no phi is feasible.
    """
    base = dict(base_phi or {})
    fly = lambda p: fly_off_design(sized, range_nm, phi={**base, stage: p})
    hi, r = 1.0, fly(1.0)
    if r.feasible:
        return 1.0, r
    lo = hi
    while lo > 0.0:
        lo = max(0.0, lo - step)
        best = fly(lo)
        if best.feasible:
            break
        hi = lo
    else:
        return None, best
    while hi - lo > tol:
        mid = 0.5 * (lo + hi)
        r = fly(mid)
        if r.feasible:
            lo, best = mid, r
        else:
            hi = mid
    return lo, best


# ---------------------------------------------------------------------------------- demo
def fc_battery_design():
    """FC + battery, battery on the take-off only (phi 0.15), 800 m field (see example 23)."""
    cfg = fuelcell_battery_config(cruise_phi=0.0)
    cfg.constraints.phases["Take Off"]["sTO"] = 800.0
    for s in cfg.mission_stages.segments:
        if s.name == "Takeoff":
            s.phi = 0.15
    a = pg.build_aircraft()
    a.configure(cfg)
    return a


def gt_hybrid_design():
    """Parallel GT hybrid, Class-I battery, cruise phi 0 -> 0.5 (common.hybrid_config)."""
    a = pg.build_aircraft()
    a.configure(hybrid_config(battery_class="I"))
    return a


def study(name, sized, ranges, fuel_name):
    w = sized.weight
    print(f"\n=== {name} ===")
    print(f"design: MTOW {w.WTO:,.0f} kg, battery {w.WBat:,.0f} kg, design fuel load {w.Wf:,.0f} kg "
          f"(nominal {sized.MissionInput['Range Mission']} nm)")
    print(f"{'range':>6} | {'design phi: trip ' + fuel_name:>24} {'bat kWh':>8} | "
          f"{'max cruise phi':>14} {'trip ' + fuel_name:>10} {'bat kWh':>8} {'saving':>7}")
    rows = []
    for rng in ranges:
        nominal = fly_off_design(sized, rng)
        phi_max, best = max_battery_phi(sized, rng)
        rows.append((rng, nominal, phi_max, best))
        flag = "" if nominal.feasible else "  INFEASIBLE: " + "; ".join(nominal.violations)
        if nominal.risks:
            flag += "  RISK: " + "; ".join(nominal.risks)
        if phi_max is None:          # every constant phi breaks the tank or the pack limit
            alt = f"{'none feasible':>14} {'-':>10} {'-':>8} {'-':>7}"
        else:
            save = 100 * (best.trip_fuel - nominal.trip_fuel) / nominal.trip_fuel
            alt = (f"{phi_max:14.2f} {best.trip_fuel:10.1f} {best.battery_energy_kWh:8.0f} "
                   f"{save:+6.1f}%")
        print(f"{rng:6.0f} | {nominal.trip_fuel:24.1f} {nominal.battery_energy_kWh:8.0f} | {alt}{flag}")
    return rows


def main():
    ranges = [250.0, 300.0, 500.0, 750.0]   # below ~210 nm the 8,000 m profile has no cruise
    results = {
        "FC + battery (take-off assist, 800 m field)": (study(
            "FC + battery, take-off battery: H2 [kg]", fc_battery_design(), ranges, "H2"), "H2"),
        "parallel GT hybrid (Class-I battery)": (study(
            "Parallel GT hybrid, Class-I battery: fuel [kg]", gt_hybrid_design(), ranges, "fuel"), "fuel"),
    }
    print("""
Reading the tables
- 'design phi' flies the off-design mission with the design schedule; 'max cruise phi' raises
  the cruise battery share until the frozen pack is empty (or its power limit is reached).
- On short missions a pack sized for the nominal mission has spare energy, so the operating
  strategy can displace fuel: this is the inner (off-design) optimisation of a multi-point
  study. The battery energy comes from the grid, so compare designs on an energy, cost or
  well-to-wake metric, not on fuel alone.""")
    _plot(results)


def _plot(results):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for ax, (name, (rows, fuel_name)) in zip(axes, results.items()):
        rng = [r[0] for r in rows]
        ax.plot(rng, [r[1].trip_fuel / r[0] for r in rows], "o-", label="design phi schedule")
        ax.plot(rng, [r[3].trip_fuel / r[0] if r[2] is not None else np.nan for r in rows], "s--",
                label="cruise phi raised to empty the pack")
        ax.set_xlabel("mission range [nm]")
        ax.set_ylabel(f"trip {fuel_name} per nm [kg/nm]")
        ax.set_title(name, fontsize=10)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=8)
    fig.tight_layout()
    print("\nFigures:")
    savefig(fig, "30_off_design_fuel_per_nm.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
