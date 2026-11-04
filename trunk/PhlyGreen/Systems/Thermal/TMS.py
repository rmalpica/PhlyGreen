"""Thermal-management system (TMS) of the fuel-cell aircraft: Class I and Class II.

``ThermalManagementSystem`` is the subsystem attached to the aircraft (``aircraft.tms``).

**Class I** (default): the heat-exchanger mass is the peak fuel-cell heat divided by a
specific power, ``EnergyInput['HEX Specific Power H2']`` [W/kg]. No drag, no pump power.

**Class II**: a geometric model of the *FC_SPEC* architecture:

    stack --coolant--> [HEX 1: coolant -> liquid H2] --> [HEX 2: coolant -> ram air] --> pump

- The coolant leaves the stack at ``T_op`` and returns ``TMS Coolant DeltaT`` colder.
- HEX 1 warms the hydrogen from saturated liquid at the supply pressure to
  ``T_op - TMS H2 Approach DeltaT`` (fixed duty, enthalpy rise from CoolProp para-hydrogen,
  latent heat included).
- HEX 2 rejects the remaining heat to ram air.
- The heat absorbed by the reactants inside the stack (H2 and cathode air entering below
  ``T_op``) is subtracted from the stack heat.
- Each HEX role is sized with the geometric families of :mod:`.hex`, using as many
  identical units in parallel as needed to keep each unit within the per-unit mass and
  volume caps.
- The pump power is ``Vdot * dP_loop / (eta_pump * eta_motor)`` (an electrical load on the
  fuel cell); pump and motor masses come from specific powers.
- The ram-air duct drag comes from :func:`.ram_air.ram_air_drag`.

The design point is chosen over the mission (:meth:`ThermalManagementSystem.SizeForMission`):
every mission point carrying at least half of the peak heat is tried as the design point;
each resulting geometry is rated at every mission point with the hardware fixed (coolant flow
set by the pump, air flow by the intake capture area), and the lightest geometry that rejects
the heat everywhere is kept.
"""

import math
from dataclasses import dataclass, field
from typing import Optional

from PhlyGreen.Utilities.Atmosphere import atmosphere as _isa
from .hex import (FluidStream, DesignSpec, HEX_Design, HeatExchangerSelector, coolprop_fluid,
                  rate_design, require_coolprop)
from .ram_air import ram_air_drag

MOLAR_MASS_H2 = 2.016e-3      # [kg/mol]
MOLAR_MASS_AIR = 28.97e-3     # [kg/mol]
O2_FRACTION_AIR = 0.21        # [-] molar


@dataclass
class ExchangerUnit:
    """One HEX role of the TMS: the design of a single unit and the number in parallel."""
    role: str                     # 'coolant_to_h2' or 'coolant_to_ram_air'
    design: HEX_Design
    n_parallel: int
    q: float                      # [W] heat rejected by all units of this role
    caps_exceeded: bool = False   # True if even the max number of units broke the caps
    candidates: list = field(default_factory=list)   # best design of each family (one unit)

    @property
    def mass(self) -> float:
        return self.design.weight * self.n_parallel

    @property
    def volume(self) -> float:
        return self.design.volume * self.n_parallel


@dataclass
class FCThermalManagementResult:
    """Class-II TMS sized at one design point."""
    design_point: dict                 # mission point used for sizing
    units: list                        # ExchangerUnit, in coolant-flow order
    mdot_coolant: float                # [kg/s] (fixed by the pump)
    mdot_ram_air: float                # [kg/s] at the design point
    capture_area: float                # [m^2] intake capture area rho*V*A = mdot_ram_air
    pump_power: float                  # [W] electrical
    pump_mass: float                   # [kg] pump + its electric motor
    hex_mass: float                    # [kg] exchanger cores
    hex_volume: float                  # [m^3]
    ram_drag: float                    # [N] net ram-air drag used by the aircraft (>= 0)
    ram_drag_raw: float                # [N] momentum balance (negative = net thrust)
    heat_balance: dict                 # [W] stack heat split
    heat_shortfall: float = 0.0        # [W] heat no exchanger could reject
    candidates: list = field(default_factory=list)   # design-point selection table

    @property
    def total_mass(self) -> float:
        """Exchanger cores + pump + pump motor [kg]."""
        return self.hex_mass + self.pump_mass

    @property
    def caps_exceeded(self) -> bool:
        return any(u.caps_exceeded for u in self.units)


class ThermalManagementSystem:
    """Thermal-management subsystem (``aircraft.tms``). See the module docstring."""

    # Mission points carrying at least this fraction of the peak heat are tried as design points.
    CANDIDATE_HEAT_FRACTION = 0.5
    # Relative shortfall tolerated at a rated point for a design to count as feasible.
    FEASIBILITY_TOLERANCE = 0.02

    def __init__(self, aircraft):
        self.aircraft = aircraft
        self.Class = 'I'
        # Class-II inputs (defaults; see the user guide for their meaning)
        self.coolant = 'INCOMP::MEG-30%'
        self.coolant_delta_T = 10.0           # [K]
        self.max_volume_per_unit = 0.05       # [m^3]
        self.max_weight_per_unit = 50.0       # [kg]
        self.max_units = 100
        self.ram_air_delta_T = 50.0           # [K] design temperature rise of the ram air
        self.ram_air_max_effectiveness = 0.8  # [-] cap on the ram-air temperature rise
        self.h2_approach_delta_T = 30.0       # [K] H2 leaves HEX 1 at T_op - this
        self.h2_supply_pressure = 1.6e5       # [Pa] LH2 enters HEX 1 saturated at this pressure
        self.loop_pressure_drop = 2.0e5       # [Pa] total coolant-loop pressure rise of the pump
        self.pump_efficiency = 0.75
        self.pump_motor_efficiency = 0.95
        self.pump_specific_power = 800.0      # [W/kg] electrical power per pump mass
        self.pump_motor_specific_power = 5000.0  # [W/kg]
        self.ram_recovery = 1.0               # [-] fraction of the dynamic pressure the intake recovers
        self.takeoff_overtemperature = 0.0    # [K] coolant allowed above T_op at take-off only
        self.result = None                    # last Class-II FCThermalManagementResult

    # ------------------------------------------------------------------------------------
    # Input
    # ------------------------------------------------------------------------------------
    def SetInput(self):
        """Read ``aircraft.TMSInput`` (all keys optional; absent input = Class I)."""
        tms_input = getattr(self.aircraft, 'TMSInput', None) or {}
        self.Class = tms_input.get('TMS Class', 'I')
        if self.Class not in ('I', 'II'):
            raise ValueError(f"TMS Class must be 'I' or 'II', got {self.Class!r}")
        self.coolant = tms_input.get('TMS Coolant', self.coolant)
        self.coolant_delta_T = tms_input.get('TMS Coolant DeltaT', self.coolant_delta_T)
        self.max_volume_per_unit = tms_input.get('TMS Max Volume Per Unit', self.max_volume_per_unit)
        self.max_weight_per_unit = tms_input.get('TMS Max Weight Per Unit', self.max_weight_per_unit)
        self.max_units = int(tms_input.get('TMS Max HEX Units', self.max_units))
        self.ram_air_delta_T = tms_input.get('TMS Ram Air DeltaT', self.ram_air_delta_T)
        self.ram_air_max_effectiveness = tms_input.get('TMS Ram Air Max Effectiveness',
                                                       self.ram_air_max_effectiveness)
        self.h2_approach_delta_T = tms_input.get('TMS H2 Approach DeltaT', self.h2_approach_delta_T)
        self.h2_supply_pressure = tms_input.get('TMS H2 Supply Pressure', self.h2_supply_pressure)
        self.loop_pressure_drop = tms_input.get('TMS Loop Pressure Drop', self.loop_pressure_drop)
        self.pump_efficiency = tms_input.get('TMS Pump Efficiency', self.pump_efficiency)
        self.pump_motor_efficiency = tms_input.get('TMS Pump Motor Efficiency',
                                                   self.pump_motor_efficiency)
        self.pump_specific_power = tms_input.get('TMS Pump Specific Power', self.pump_specific_power)
        self.pump_motor_specific_power = tms_input.get('TMS Pump Motor Specific Power',
                                                       self.pump_motor_specific_power)
        self.ram_recovery = tms_input.get('TMS Ram Recovery', self.ram_recovery)
        self.takeoff_overtemperature = tms_input.get('TMS Takeoff Coolant Overtemperature',
                                                     self.takeoff_overtemperature)
        self.result = None
        if self.Class == 'II':
            require_coolprop()

    # ------------------------------------------------------------------------------------
    # Class I
    # ------------------------------------------------------------------------------------
    def ClassI_Mass(self, Q_peak):
        """Class-I exchanger mass [kg]: peak fuel-cell heat [W] / 'HEX Specific Power H2'."""
        hex_sp_h2 = self.aircraft.EnergyInput.get('HEX Specific Power H2', 5000.0)
        return Q_peak / hex_sp_h2 if Q_peak > 0 else 0.0

    # ------------------------------------------------------------------------------------
    # Class II: operating conditions at one mission point
    # ------------------------------------------------------------------------------------
    def _ambient(self, altitude):
        """(T_static [K], P_static [Pa], rho [kg/m^3]) at altitude, with the mission DISA."""
        DISA = getattr(self.aircraft.mission, 'DISA', 0.0) or 0.0
        T = float(_isa.Tstd(altitude)) + DISA
        P = float(_isa.Pstd(altitude))
        return T, P, P / (_isa.Rair * T)

    def _conditions(self, point):
        """Heat split and the hydrogen stream at a mission point.

        Returns a dict with: ``Q_ext`` (heat the coolant must reject [W]), ``q_h2_target``
        (duty of HEX 1 [W]), ``q_reactant`` (heat absorbed by the reactants in the stack [W]),
        ``h2`` (FluidStream, effective cp), ``T_op`` and the ambient state.
        """
        from CoolProp.CoolProp import PropsSI
        fc = self.aircraft.fuelcell
        # The coolant (and stack) may run hotter for the short take-off phase: a larger
        # temperature difference to the ram air for the same hardware.
        T_op = fc.T_op + (self.takeoff_overtemperature if point.get('takeoff') else 0.0)
        Q_fc = max(point['Q_fc'], 0.0)
        mdot_h2 = max(point['mdot_h2'], 0.0)
        T_amb, P_amb, rho_amb = self._ambient(point['altitude'])

        # Hydrogen: saturated liquid at the supply pressure -> T_op - approach (HEX 1),
        # then -> T_op inside the stack. Para-hydrogen enthalpies (no ortho-para conversion).
        P_h2 = self.h2_supply_pressure
        T_sat = PropsSI('T', 'P', P_h2, 'Q', 0, 'ParaHydrogen')
        h_liq = PropsSI('H', 'P', P_h2, 'Q', 0, 'ParaHydrogen')
        T_h2_out = T_op - self.h2_approach_delta_T
        h_out = PropsSI('H', 'T', T_h2_out, 'P', P_h2, 'ParaHydrogen')
        h_op = PropsSI('H', 'T', T_op, 'P', P_h2, 'ParaHydrogen')
        q_h2_target = mdot_h2 * (h_out - h_liq)
        T_mean = 0.5 * (T_sat + T_h2_out)
        h2 = coolprop_fluid('H2', 'ParaHydrogen', T_mean, P_h2, mdot_h2, T_in=T_sat)
        h2.cp = (h_out - h_liq) / (T_h2_out - T_sat)        # effective cp, latent heat included

        # Cathode air from the H2 flow and the air stoichiometry, compressed to the stack pressure.
        mdot_air = (mdot_h2 / MOLAR_MASS_H2) * 0.5 / O2_FRACTION_AIR * MOLAR_MASS_AIR * fc.stoich
        PR = max(fc.Target_Press / P_amb, 1.0)
        T_comp = T_amb * (1.0 + (PR ** (0.4 / 1.4) - 1.0) / fc.comp_eta)
        cp_air = PropsSI('C', 'T', 0.5 * (T_comp + T_op), 'P', fc.Target_Press, 'Air')
        q_reactant = mdot_h2 * (h_op - h_out) + mdot_air * cp_air * (T_op - T_comp)

        Q_ext = max(Q_fc - q_reactant, 0.0)
        return {'Q_ext': Q_ext, 'q_h2_target': min(q_h2_target, Q_ext), 'q_reactant': q_reactant,
                'h2': h2, 'T_op': T_op, 'T_amb': T_amb, 'P_amb': P_amb, 'rho_amb': rho_amb,
                'V_inf': max(point['V_inf'], 0.0)}

    def _coolant(self, T_op, mdot):
        return coolprop_fluid('coolant', self.coolant, T_op, 2.0e5, mdot)

    def _ram_air(self, cond, mdot):
        """Ram-air stream at the HEX: inlet at the free-stream total temperature."""
        T0 = cond['T_amb'] + cond['V_inf'] ** 2 / (2.0 * 1005.0)
        dT = self.ram_air_delta_T
        return coolprop_fluid('ram_air', 'Air', T0 + 0.5 * dT, cond['P_amb'], mdot, T_in=T0)

    # ------------------------------------------------------------------------------------
    # Class II: sizing at one design point
    # ------------------------------------------------------------------------------------
    def _size_role(self, role, hot, cold, q, dP_hot_max, dP_cold_max):
        """Size one HEX role: the fewest identical parallel units such that one unit respects
        the per-unit mass and volume caps. Returns an ExchangerUnit, or None if no family
        can do the duty at all."""
        def select(n, capped):
            spec = DesignSpec(hot=hot.split(n), cold=cold.split(n), q_target=q / n,
                              dP_hot_max=dP_hot_max, dP_cold_max=dP_cold_max,
                              max_volume=self.max_volume_per_unit if capped else math.inf,
                              max_weight=self.max_weight_per_unit if capped else math.inf)
            sel = HeatExchangerSelector(spec)
            return sel.select_best(), sel.candidates()

        # Unit designs scale ~1/n (fixed design velocities), so one uncapped single-unit
        # design gives the starting unit count.
        single, _ = select(1, capped=False)
        if single is None:
            return None
        n_start = max(1, math.ceil(max(single.weight / self.max_weight_per_unit,
                                       single.volume / self.max_volume_per_unit)) - 1)
        # 1) first feasible unit count upward from the estimate ...
        found = None
        for n in range(min(n_start, self.max_units), self.max_units + 1):
            best, cands = select(n, capped=True)
            if best is not None:
                found = (n, best, cands)
                break
        if found is not None:
            # 2) ... then bisect below it for the fewest feasible units (feasibility is
            # monotone in n up to the discreteness of the candidate grid).
            lo, (hi, best, cands) = 0, found
            while hi - lo > 1:
                mid = (lo + hi) // 2
                b_mid, c_mid = select(mid, capped=True)
                if b_mid is not None:
                    hi, best, cands = mid, b_mid, c_mid
                else:
                    lo = mid
            return ExchangerUnit(role, best, hi, q, False, cands)
        best, cands = select(self.max_units, capped=False)
        if best is None:
            return None
        return ExchangerUnit(role, best, self.max_units, q, True, cands)

    def SizeAtPoint(self, point):
        """Size the Class-II TMS at one mission point.

        ``point`` is a dict with ``name, Q_fc [W], altitude [m], V_inf [m/s TAS],
        mdot_h2 [kg/s]`` (see ``Mission.thermal_profile``). Returns a
        :class:`FCThermalManagementResult`.
        """
        cond = self._conditions(point)
        Q_ext, T_op = cond['Q_ext'], cond['T_op']
        coolant = self._coolant(T_op, 1.0)
        coolant = coolant.with_mdot(Q_ext / (coolant.cp * self.coolant_delta_T))
        units, shortfall = [], 0.0
        dP_hot_max = self.loop_pressure_drop

        # HEX 1: coolant -> hydrogen (fixed duty).
        q1 = cond['q_h2_target']
        T1 = T_op
        if q1 > 0 and coolant.mdot > 0:
            u1 = self._size_role('coolant_to_h2', coolant, cond['h2'], q1, dP_hot_max, 1.0e4)
            if u1 is None:
                q1 = 0.0
            else:
                units.append(u1)
            T1 = T_op - q1 / coolant.C
        else:
            q1 = 0.0

        # HEX 2: coolant -> ram air (the remainder).
        q2 = Q_ext - q1
        mdot_air, drag_raw, capture = 0.0, 0.0, 0.0
        if q2 > 1.0:
            T0 = cond['T_amb'] + cond['V_inf'] ** 2 / (2.0 * 1005.0)
            dT_air = min(self.ram_air_delta_T, self.ram_air_max_effectiveness * (T1 - T0))
            # the core may not lose more than the dynamic pressure the intake recovers
            q_dyn = self.ram_recovery * 0.5 * cond['rho_amb'] * cond['V_inf'] ** 2
            u2 = None
            if dT_air > 0 and q_dyn > 0:
                air = self._ram_air(cond, 1.0)
                mdot_air = q2 / (air.cp * dT_air)
                air = air.with_mdot(mdot_air)
                u2 = self._size_role('coolant_to_ram_air', coolant.with_inlet(T1), air, q2,
                                     dP_hot_max, q_dyn)
            if u2 is None:
                shortfall += q2
                mdot_air = 0.0
            else:
                units.append(u2)
                capture = mdot_air / (cond['rho_amb'] * cond['V_inf'])
                drag_raw = ram_air_drag(q2, mdot_air, cond['T_amb'], cond['P_amb'], cond['V_inf'],
                                        V_core=u2.design.v_cold, dP_core=u2.design.dP_cold,
                                        eta_ram=self.ram_recovery)
        # (if no family could do the H2 duty, q1 = 0 and the ram air takes the whole heat)

        V_dot = coolant.mdot / coolant.rho if coolant.mdot > 0 else 0.0
        pump_power = V_dot * self.loop_pressure_drop / (self.pump_efficiency * self.pump_motor_efficiency)
        pump_mass = pump_power / self.pump_specific_power + pump_power / self.pump_motor_specific_power

        return FCThermalManagementResult(
            design_point=point, units=units, mdot_coolant=coolant.mdot, mdot_ram_air=mdot_air,
            capture_area=capture, pump_power=pump_power, pump_mass=pump_mass,
            hex_mass=sum(u.mass for u in units), hex_volume=sum(u.volume for u in units),
            ram_drag=max(drag_raw, 0.0), ram_drag_raw=drag_raw,
            heat_balance={'stack': max(point['Q_fc'], 0.0), 'reactants': cond['q_reactant'],
                          'HEX H2': q1, 'HEX ram air': q2 if mdot_air > 0 else 0.0,
                          'unmet': shortfall},
            heat_shortfall=shortfall)

    # ------------------------------------------------------------------------------------
    # Class II: off-design rating and design-point selection
    # ------------------------------------------------------------------------------------
    def RateAtPoint(self, result, point, capped=True):
        """Heat the FIXED hardware of ``result`` rejects at another mission point.

        Coolant flow = the pump's design flow; ram-air flow = intake capture area x rho x V
        (flap fully open); each unit's U is recomputed from its geometry at the new flows.
        With ``capped`` (default) the rejected heat is limited to what is required (the
        hydrogen to its target temperature, the ram air by the flap); ``capped=False`` returns
        the full capacity of the hardware at that point.
        Returns ``(q_rejected [W], q_required [W])``.
        """
        cond = self._conditions(point)
        q_req = cond['Q_ext']
        if q_req <= 0.0:
            return 0.0, 0.0
        T_op = cond['T_op']
        coolant = self._coolant(T_op, result.mdot_coolant)
        by_role = {u.role: u for u in result.units}
        q1, T1 = 0.0, T_op
        u1 = by_role.get('coolant_to_h2')
        if u1 is not None and cond['h2'].mdot > 0:
            n = u1.n_parallel
            q1 = n * rate_design(u1.design, coolant.split(n), cond['h2'].split(n))
            if capped:
                q1 = min(q1, cond['q_h2_target'])
            T1 = T_op - q1 / coolant.C
        q2 = 0.0
        u2 = by_role.get('coolant_to_ram_air')
        mdot_air = result.capture_area * cond['rho_amb'] * cond['V_inf']
        if u2 is not None and mdot_air > 0:
            n = u2.n_parallel
            air = self._ram_air(cond, mdot_air)
            q2 = n * rate_design(u2.design, coolant.with_inlet(T1).split(n), air.split(n))
            if capped:
                q2 = min(q2, q_req - q1)
        return q1 + q2, q_req

    def SizeForMission(self, points):
        """Choose the design point over the mission and size the Class-II TMS there.

        Every point carrying at least ``CANDIDATE_HEAT_FRACTION`` of the peak heat is tried
        as the design point; each geometry is rated at every point (:meth:`RateAtPoint`);
        the lightest geometry with a worst shortfall within ``FEASIBILITY_TOLERANCE`` is
        kept. If none qualifies, the one with the smallest worst shortfall is kept.
        Stores and returns the chosen :class:`FCThermalManagementResult` (its
        ``candidates`` attribute holds the selection table).
        """
        Q_max = max(p['Q_fc'] for p in points)
        trials = [p for p in points if p['Q_fc'] >= self.CANDIDATE_HEAT_FRACTION * Q_max]
        table = []
        for p in trials:
            res = self.SizeAtPoint(p)
            worst, worst_at = 0.0, None
            for other in points:
                q_rej, q_req = self.RateAtPoint(res, other)
                if q_req > 0:
                    gap = max(0.0, (q_req - q_rej) / q_req)
                    if gap > worst + 1e-9:
                        worst, worst_at = gap, other['name']
            table.append({'point': p['name'], 'result': res, 'mass': res.total_mass,
                          'worst_shortfall': worst, 'worst_shortfall_at': worst_at,
                          'feasible': worst <= self.FEASIBILITY_TOLERANCE})
        feasible = [t for t in table if t['feasible']]
        if feasible:
            chosen = min(feasible, key=lambda t: t['mass'])
        else:
            chosen = min(table, key=lambda t: (t['worst_shortfall'], -t['mass']))
        result = chosen['result']
        result.candidates = [{k: v for k, v in t.items() if k != 'result'} for t in table]
        self.result = result
        return result

    def RamDragCoefficient(self, result, wing_area):
        """Ram-air drag of ``result`` as a drag-coefficient increment referred to
        ``wing_area`` [m^2], at the dynamic pressure of its design point. Applied as a constant
        increment it scales the ram drag with the dynamic pressure at every flight condition."""
        p = result.design_point
        _, _, rho = self._ambient(p['altitude'])
        q_dyn = 0.5 * rho * p['V_inf'] ** 2
        if q_dyn <= 0.0 or wing_area <= 0.0:
            return 0.0
        return result.ram_drag / (q_dyn * wing_area)

    def report(self):
        """Print a short summary of the last Class-II sizing."""
        r = self.result
        if r is None:
            print("TMS: Class I (specific-power model)" if self.Class == 'I' else "TMS: not sized")
            return
        print(f"TMS Class II: design point '{r.design_point['name']}' "
              f"(Q_fc = {r.design_point['Q_fc']/1e3:.0f} kW)")
        for u in r.units:
            flag = "  [per-unit caps exceeded]" if u.caps_exceeded else ""
            print(f"  {u.role:20s}: {u.n_parallel:3d} x {u.design.family:17s} "
                  f"{u.design.weight:6.1f} kg {u.design.volume:7.4f} m3 per unit, "
                  f"{u.q/1e3:7.1f} kW{flag}")
        print(f"  pump: {r.pump_power/1e3:.1f} kW, {r.pump_mass:.1f} kg;  ram air: "
              f"{r.mdot_ram_air:.1f} kg/s, drag {r.ram_drag:.0f} N")
        print(f"  total TMS mass: {r.total_mass:.1f} kg")
        if r.heat_shortfall > 1e-3 * max(r.design_point['Q_fc'], 1.0):
            print(f"  WARNING: {r.heat_shortfall/1e3:.1f} kW of heat not rejected")
