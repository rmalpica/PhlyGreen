import warnings
import numpy as np
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed
import PhlyGreen.Utilities.Units as Units
from scipy.optimize import brentq, brenth, ridder, newton
from pprint import pprint
from .FLOPS_model import FLOPS_model

# Max inner passes of the fuel-cell "size -> fly -> resize -> re-fly" loop (the fuel-cell
# rated power converges in 2-3 passes since efficiency depends only weakly on stack size).
_FC_RESIZE_ITERS = 3
# With the Class-II TMS the same loop also converges the TMS pump load and ram-air drag.
_FC_TMS_RESIZE_ITERS = 6
# Max passes and relative tolerance of the "fly -> rate -> set the nominal" loop of a Class-II
# gas turbine whose nominal follows the sized rating (Weight._mission_and_powertrain).
_GT_RATING_ITERS = 20
_GT_RATING_RTOL = 1e-7


class Weight:
    """
    Aircraft weight estimation module.

    This class estimates the aircraft Take-Off Weight (WTO) by solving the 
    coupled mission-powertrain-structure design problem:

        WTO = W_fuel(WTO) + W_battery(WTO) + W_struct(WTO) + W_powertrain(WTO) + W_payload + W_crew

    The aircraft model and the mission profile determine fuel and battery energy consumption, the 
    powertrain model provides propulsion system mass, and the structural 
    model (or FLOPS surrogate model) provides airframe component masses.

    Two weight estimation classes are supported:

    - Class I:  Simplified regression model from the user's Structures module.
    - Class II: Uses FLOPS-based component mass estimation (empirical).

    Two propulsion configurations are supported:

    - Traditional (thermal only)
    - Hybrid-electric (thermal + electric battery pack)

    Brent's root-finding method is used to find the WTO that satisfies the 
    mass consistency equation above.

    Parameters
    ----------
    aircraft : Aircraft
        Parent aircraft object containing mission, powertrain, structure, and 
        battery models."""
  
    def __init__(self, aircraft):
        self.aircraft = aircraft
        self.tol = 0.1
        self.final_reserve = None  
        self.Class = 'I'
        self.tms_result = None     # Class-II TMS result of the last fuel-cell weight closure
        # When True, the powertrain mass is not added on top of a structural model that already
        # contains it (see powertrain_in_closure). Off by default: switching it on changes the
        # converged take-off weight, so it is a deliberate choice per configuration.
        self.avoid_powertrain_double_count = False
        
            
        
    def SetInput(self):
        """
        Load required user inputs from the aircraft data structure.

        Sets:
        - Payload weight
        - Crew weight
        - Fuel specific energy
        - Contingency fuel or final reserve
        - FLOPS model components (Class II only)
        """
        
        self.WPayload = self.aircraft.MissionInput['Payload Weight']
        self.WCrew = self.aircraft.MissionInput['Crew Weight']
        self.ef = self.aircraft.EnergyInput['Ef']
        # Contingency / final-reserve fuel: a fixed input mass if given, else a fraction of the
        # mission fuel applied each weight iteration (see the weight loops). Store the input
        # separately so the fallback is recomputed on the *converged* fuel, not frozen at the
        # first Brent probe.
        self._contingency = self.aircraft.EnergyInput.get('Contingency Fuel', 0)
        self.final_reserve = self._contingency

        if self.Class == 'II':
            self.AircraftComponents = FLOPS_model(self.aircraft)

        return None

    def _solve_wto(self, func, lower=1000, upper=300000, step=10000, xtol=None):
        """Robustly solve ``f(WTO) = 0`` for the take-off weight with Brent's method.

        First tries Brent on the full ``[lower, upper]`` bracket — the historical behaviour,
        so well-posed designs converge to exactly the same root as before. If that fails
        (the endpoints do not bracket a sign change, or ``func`` errors mid-range — common in
        parametric sweeps near the edge of the feasible space), it scans ``[lower, upper]`` in
        ``step``-kg increments for the *first* sign-change bracket and runs Brent on that
        narrow, valid interval. This makes the WTO loop converge smoothly across sweeps
        without changing any result that already converged.

        ``lower``/``upper`` can be overridden per design via the ``MissionInput`` keys
        ``'Brenth Lower Limit'`` / ``'Brenth Upper Limit'``.
        """
        if xtol is None:
            xtol = self.tol
        mi = getattr(self.aircraft, 'MissionInput', None) or {}
        lower = mi.get('Brenth Lower Limit', lower)
        upper = mi.get('Brenth Upper Limit', upper)

        try:
            return brenth(func, lower, upper, xtol=xtol)
        except Exception as exc_full:
            # Robust fallback: grid-scan for the first interval that brackets a root.
            weights = np.arange(lower, upper + step, step)
            prev_w = weights[0]
            try:
                prev_f = func(prev_w)
            except Exception:
                prev_f = np.nan
            for curr_w in weights[1:]:
                try:
                    curr_f = func(curr_w)
                except Exception:
                    curr_f = np.nan
                if np.isfinite(prev_f) and np.isfinite(curr_f) and prev_f * curr_f < 0:
                    return brenth(func, prev_w, curr_w, xtol=xtol)
                prev_w, prev_f = curr_w, curr_f
            # No valid bracket found anywhere — surface the original failure.
            raise exc_full

    def WeightEstimation(self):
        """
         Perform full aircraft weight estimation for the selected configuration.

        Returns
        -------
        float or str
            Converged take-off weight WTO, or a string if configuration is invalid."""
        

        if self.aircraft.Configuration in ('Traditional', 'Turbofan'):
                 # The take-off weight equation is the same for a turbofan -- fuel, reserve,
                 # powertrain, structure, payload, crew. Only the powertrain mass differs,
                 # and that is Powertrain.WeightPowertrain's business, not this loop's.
                 return self.Traditional()
             
             
        elif self.aircraft.Configuration == 'Hybrid':


                 return self.Hybrid()

        elif self.aircraft.Configuration == 'Hydrogen':

                 return self.Hydrogen()

        elif self.aircraft.Configuration == 'FuelCellBattery':

                 return self.FuelCellBattery()

        else:
                 return "Try a different configuration..."


    def powertrain_in_closure(self, WPT):
        """Powertrain mass to ADD to the take-off-weight closure [kg].

        Returns 0 when the structural model already contains the powertrain, so that the
        engines are not counted twice. ``self.WPT`` still holds the computed powertrain mass
        for reporting either way -- what changes is only whether it is added again.

        Class-I regressions are empty-weight fractions and so *do* include the powertrain
        (``Structures.includes_powertrain``); Class-II FLOPS sums airframe components only and
        does not. The behaviour is opt-in through ``Weight.avoid_powertrain_double_count`` so
        that enabling it is a deliberate act: it changes the take-off weight of every design
        that turns it on.
        """
        if not self.avoid_powertrain_double_count:
            return WPT
        if self.Class == 'I' and self.aircraft.structures.includes_powertrain():
            return 0.0
        return WPT

    def _mission_and_powertrain(self, WTO):
        """Fly the mission and size the gas-turbine powertrain at one take-off weight; return
        ``(mission energies, powertrain mass)``.

        Without a Class-II gas turbine whose nominal follows the rating this is
        ``EvaluateMission`` then ``WeightPowertrain``. With one (Class-II map and no explicit
        'GT Design Power', ``powertrain.gt_design_power_follows_rating``), the map's nominal
        is seeded with ``DesignPW * WTO``, the mission is flown, the engine is rated, and the
        nominal is set to that rating and the mission re-flown until the two agree within
        ``_GT_RATING_RTOL``: the engine that flies the mission is the one that is weighed.
        """
        mission = self.aircraft.mission
        pt = self.aircraft.powertrain
        if not pt.gt_design_power_follows_rating:
            energies = mission.EvaluateMission(WTO)
            return energies, pt.WeightPowertrain(WTO)
        pt.set_gt_design_power(self.aircraft.DesignPW * WTO)
        for _ in range(_GT_RATING_ITERS):
            energies = mission.EvaluateMission(WTO)
            WPT = pt.WeightPowertrain(WTO)
            if abs(pt.engineRating - pt.gt_design_power) <= _GT_RATING_RTOL * pt.engineRating:
                self._gt_rating_converged = True
                return energies, WPT
            pt.set_gt_design_power(pt.engineRating)
        # the last nominal set was not flown: fly it, so the reported mission uses it.
        # Reported by _warn_gt_rating_not_converged if it happens at the converged WTO (the
        # far probes of the root bracket may not converge without consequence).
        energies = mission.EvaluateMission(WTO)
        WPT = pt.WeightPowertrain(WTO)
        self._gt_rating_converged = False
        return energies, WPT

    def _warn_gt_rating_not_converged(self):
        """Warn when the nominal of a rating-following Class-II gas turbine did not converge
        at the last weight evaluation (the converged WTO)."""
        pt = self.aircraft.powertrain
        if pt.gt_design_power_follows_rating and not getattr(self, '_gt_rating_converged', True):
            warnings.warn(
                f"Class-II gas turbine: the nominal did not converge to the sized rating in "
                f"{_GT_RATING_ITERS} passes (nominal {pt.gt_design_power/1e3:.1f} kW, rating "
                f"{pt.engineRating/1e3:.1f} kW).", RuntimeWarning)

    def _structural_weight(self, WTO):
        """Airframe structural mass [kg] for the current weight class.

        Class I: the regression empty-weight model selected by ``AircraftType``. Class II:
        the sum of the FLOPS component masses (computed in imperial units, converted to kg).
        Identical for every configuration, so the four weight loops share this one method.
        """
        if self.Class == 'I':
            return self.aircraft.structures.StructuralWeight(WTO)
        # Class II: FLOPS component masses (lb) at this gross weight -> kg.
        self.aircraft.FLOPSInput['GROSS_WEIGHT'] = WTO  # UNITS KG
        self.AircraftComponents.SetInput()
        self.AircraftComponents.CalculateComponentMasses()
        c = self.AircraftComponents
        return Units.lbTokg(
            c.Wing.wingmass + c.Fuselage.fuselagemass + c.Tail.HTailmass
            + c.Tail.VTailmass + c.LandingGear.Landing_gearmass + c.Nacelle.nacellemass
            + c.Paint.paintmass + c.SystemEquipment.system_equipment_mass
            + c.Propeller.propellermass)


    def Traditional(self):
        """
        Solve the weight equation for a traditional (non-hybrid) 
        propulsion system.

        The objective function is:

            f(WTO) = W_fuel + W_final_reserve + W_powertrain + W_structure
                     + W_payload + W_crew - WTO

        The root of f(WTO) is the correct takeoff weight.

        Returns
        -------
        float
            Converged take-off weight WTO.
        """
        
        # self.WTO = [0, 16000]
        # WDifference = self.WTO[1] - self.WTO[0]
        # i = 1
        
        def func(WTO):
                """
                Weight residual function for use with Brent's method.

                Evaluates:
                 - Mission fuel burn
                 - Propulsion system weight
                 - Structural weight (Class I or II)
                 - Final reserve rule
                """
            
                E_fuel, self.WPT = self._mission_and_powertrain(WTO)
                self.Wf = E_fuel/self.ef
                # Energies used over the mission [J] = [fuel, battery]; consumed by the
                # well-to-wake accounting (no battery in a traditional aircraft).
                self.TotalEnergies = [E_fuel, 0.0]

                self.WStructure = self._structural_weight(WTO)


                self.final_reserve = self._contingency if self._contingency else 0.05 * self.Wf

                return (self.Wf + self.final_reserve + self.powertrain_in_closure(self.WPT) + self.WStructure + self.WPayload + self.WCrew - WTO)

        self.WTO = self._solve_wto(func, 1000, 300000, xtol=0.1)
        self._warn_gt_rating_not_converged()


    def Hydrogen(self):
        """Solve the take-off-weight equation for a hydrogen fuel-cell aircraft.

            f(WTO) = W_structure + W_fuelcell + W_H2 + W_tank + W_HX
                     + W_payload + W_crew + W_reserve - WTO

        The fuel-cell system mass is sized by ``FuelCell.ComputeAndStoreWeights`` (which
        also sets ``aircraft.weight.WPT``); the mission returns the hydrogen chemical
        energy (flown profile + ground segments), converted to H2 mass with ``self.ef`` and
        increased by ``EnergyInput['H2 Fuel Margin']`` (default 0.05: unusable/residual
        hydrogen, feed system). The final reserve (``Contingency Fuel``, else 5 % of that
        load) is weighed AND stored: the tank holds load + reserve. Hydrogen storage mass uses
        the cryogenic ``LH2_Tank`` if available, otherwise a simple gravimetric-index model.
        """
        # Gravimetric index of the H2 storage system (usable H2 / total tank+H2 mass),
        # used as a fallback when the detailed cryogenic tank model is unavailable.
        grav_index = self.aircraft.EnergyInput.get('H2 Gravimetric Index', 0.35)
        # Extra H2 loaded on top of the flown H2 (unusable/residual hydrogen, feed system).
        h2_margin = self.aircraft.EnergyInput.get('H2 Fuel Margin', 0.05)

        # Use the physics-based LH2 tank model when a TankInput is given and CoolProp is
        # installed; otherwise fall back to the simple gravimetric-index model.
        LH2_Tank = self._physics_tank_class(grav_index)

        def func(WTO):
            # Fuel cell (and Class-II TMS) sized self-consistently with the flown mission.
            E_h2_chem = self._fuel_cell_and_tms_closure(WTO)
            self.WPT = self.aircraft.fuelcell.Weight

            self.WH2_Fuel = (E_h2_chem / self.ef) * (1.0 + h2_margin)
            self.Wf = self.WH2_Fuel
            # Energies used over the mission [J] = [hydrogen, battery]; consumed by the
            # well-to-wake accounting (no battery in a pure fuel-cell aircraft).
            self.TotalEnergies = [E_h2_chem, 0.0]

            # 3. Reserve hydrogen (fixed input mass, else 5% of the H2 load) and the tank
            # (empty) mass. The tank holds ALL the hydrogen on board: load + reserve.
            self.final_reserve = self._contingency if self._contingency else 0.05 * self.Wf
            self.WTank = self._hydrogen_tank_mass(self.WH2_Fuel + self.final_reserve,
                                                  LH2_Tank, grav_index)

            # 4. Thermal-management mass (Class I: peak heat / specific power; Class II:
            # geometric exchangers + pump, sized in the closure above).
            self.WHeat_Exchanger = self._fuel_cell_tms_mass()

            # 5. Structure.
            self.WStructure = self._structural_weight(WTO)

            return (self.WStructure + self.WPT + self.WH2_Fuel + self.WTank
                    + self.WHeat_Exchanger + self.WPayload + self.WCrew
                    + self.final_reserve - WTO)

        try:
            self.WTO = self._solve_wto(func, 1000, 300000, xtol=self.tol)
        except (ValueError, RuntimeError):
            raise RuntimeError(
                "Hydrogen weight loop did not converge: the design did not close within "
                "1000-300000 kg (the fuel-cell system mass may be snowballing — try a lower "
                "design cell voltage, a higher stack power density, or a shorter mission).")
        self._warn_tms_shortfall()
        return self.WTO


    def _physics_tank_class(self, grav_index):
        """The cryogenic ``LH2_Tank`` class when a TankInput is given and the tank module can
        be imported (it needs CoolProp), else None. Shared by :meth:`Hydrogen` and
        :meth:`FuelCellBattery`.

        ``aircraft.tank`` is reset to None here; ``_hydrogen_tank_mass`` sets it again only
        when the physics tank is used, so it never keeps a tank from an earlier design.
        A TankInput that cannot be honoured raises a warning (the design then uses the
        gravimetric index).
        """
        self.aircraft.tank = None
        if getattr(self.aircraft, 'TankInput', None) is None:
            return None
        try:
            from PhlyGreen.Systems.Tank import LH2_Tank
        except ImportError as err:
            warnings.warn(
                f"A TankConfig is given but the cryogenic LH2 tank model cannot be imported "
                f"({err}; it needs CoolProp). The tank mass uses the gravimetric index "
                f"H2 Gravimetric Index = {grav_index} instead, and aircraft.tank is None.",
                RuntimeWarning)
            return None
        return LH2_Tank

    def _hydrogen_tank_mass(self, m_h2, LH2_Tank, grav_index):
        """Empty mass [kg] of the tank holding ``m_h2`` kg of hydrogen: the cryogenic
        ``LH2_Tank`` model when available, else the gravimetric index
        (usable H2 / (H2 + tank))."""
        if m_h2 <= 0:
            return 0.0
        if LH2_Tank is not None:
            self.aircraft.tank = LH2_Tank(capacity_kg=m_h2, aircraft=self.aircraft)
            return self.aircraft.tank.mass_system_empty
        return m_h2 * (1.0 / grav_index - 1.0)

    def _fuel_cell_and_tms_closure(self, WTO):
        """Size the fuel cell (and the Class-II TMS) self-consistently at one take-off weight
        and fly the mission. Shared by :meth:`Hydrogen` and :meth:`FuelCellBattery`.

        1. Reset the TMS couplings (ram-air drag increment, pump load) and seed the fuel cell
           from the constraint diagram.
        2. Fly -> resize the fuel cell to max(mission peak, take-off/OEI) -> re-fly until the
           required power converges, so the fuel cell that flies the mission is the one that
           is weighed (the take-off/OEI requirement is a hard floor on its power).
        3. With the Class-II TMS, every pass also sizes the TMS over the mission thermal
           profile, checked along the continuous mission (``mission.thermal_history``): its
           pump becomes a constant electrical load on the fuel cell (``fuelcell.P_aux_tms``) and its ram-air drag a drag-coefficient increment
           (``aerodynamics.extra_Cd``, referred to the wing area S = WTO g / (W/S)); the loop
           then also waits for these two to converge.

        Returns what ``mission.EvaluateMission`` returns for the final pass.
        """
        fc = self.aircraft.fuelcell
        tms = getattr(self.aircraft, 'tms', None)
        class_ii = tms is not None and tms.Class == 'II'
        aero = self.aircraft.aerodynamics
        aero.extra_Cd = 0.0
        fc.P_aux_tms = 0.0
        self.tms_result = None
        fc.SizeFromConstraint(WTO)

        P_req, converged = None, False
        for _ in range(_FC_TMS_RESIZE_ITERS if class_ii else _FC_RESIZE_ITERS):
            energies = self.aircraft.mission.EvaluateMission(WTO)
            demand = max(self.aircraft.mission.TO_PP, self.aircraft.mission.Max_PEng)
            tms_settled = True
            if class_ii:
                res = tms.SizeForMission(self.aircraft.mission.thermal_profile,
                                         self.aircraft.mission.thermal_history)
                wing_area = WTO * 9.81 / self.aircraft.DesignWTOoS
                new_Cd = tms.RamDragCoefficient(res, wing_area)
                tms_settled = (abs(res.pump_power - fc.P_aux_tms) <= 1e-3 * max(res.pump_power, 1.0)
                               and abs(new_Cd - aero.extra_Cd) <= 1e-3 * max(new_Cd, 1e-6))
                fc.P_aux_tms = res.pump_power
                aero.extra_Cd = new_Cd
                self.tms_result = res
            if (P_req is not None and tms_settled
                    and abs(demand - P_req) <= 1e-3 * max(P_req, 1.0)):
                converged = True
                break
            P_req = demand
            fc.SizeForPropulsivePower(P_req)
        if not converged:
            # Ensure the final stack size was actually flown and, with the Class-II TMS, that
            # the TMS is sized on that flight and its couplings are those the mission uses.
            energies = self.aircraft.mission.EvaluateMission(WTO)
            if class_ii:
                res = tms.SizeForMission(self.aircraft.mission.thermal_profile,
                                         self.aircraft.mission.thermal_history)
                fc.P_aux_tms = res.pump_power
                aero.extra_Cd = tms.RamDragCoefficient(res, WTO * 9.81 / self.aircraft.DesignWTOoS)
                self.tms_result = res
                energies = self.aircraft.mission.EvaluateMission(WTO)
        return energies

    def _fuel_cell_tms_mass(self):
        """Fuel-cell thermal-management mass [kg].

        Class I: the larger of the peak fuel-cell heat over the mission and the heat at the
        take-off/OEI point (either can be the larger: on the hydrogen reference the climb
        rejects more than the take-off), divided by the specific power
        ``EnergyInput['HEX Specific Power H2']``. Class II: exchanger cores + pump +
        pump motor of the TMS sized in :meth:`_fuel_cell_and_tms_closure`.
        """
        if self.tms_result is not None:
            return self.tms_result.total_mass
        m = self.aircraft.mission
        Q_peak = max(m.Max_FC_Thermal_Pwr, m.TO_FC_Thermal_Pwr)
        tms = getattr(self.aircraft, 'tms', None)
        if tms is not None:
            return tms.ClassI_Mass(Q_peak)
        hex_sp_h2 = self.aircraft.EnergyInput.get('HEX Specific Power H2', 5000.0)
        return Q_peak / hex_sp_h2 if Q_peak > 0 else 0.0

    def _warn_tms_shortfall(self):
        """Warn, once at the converged design, if the Class-II TMS could not reject all the
        heat, needed exchangers beyond the per-unit caps, or breaks a limit of
        :meth:`ThermalManagementSystem.CheckAtPoint` along the mission."""
        r = self.tms_result
        if r is None:
            return
        Q = max(r.design_point['Q_fc'], 1.0)
        if r.heat_shortfall > 1e-3 * Q:
            warnings.warn(f"Class-II TMS: {r.heat_shortfall/1e3:.1f} kW of fuel-cell heat could "
                          f"not be rejected at the design point '{r.design_point['name']}'.",
                          RuntimeWarning)
        if r.caps_exceeded:
            warnings.warn("Class-II TMS: even 'TMS Max HEX Units' units in parallel exceed the "
                          "per-unit mass/volume caps; the units were allowed to grow beyond them.",
                          RuntimeWarning)
        bad = [c for c in r.candidates if not c['feasible']]
        if len(bad) == len(r.candidates):
            warnings.warn("Class-II TMS: no candidate design point gives exchangers that reject "
                          "the heat at every mission point; the least-short one was used.",
                          RuntimeWarning)
        # limits of the chosen hardware along the last flown mission, the one it was sized on
        # (ThermalManagementSystem.CheckAtPoint at every profile and integration point)
        mission = self.aircraft.mission
        self.aircraft.tms.CheckMission(r, mission.thermal_profile, mission.thermal_history)
        for message in r.violations():
            warnings.warn(f"Class-II TMS: {message}.", RuntimeWarning)
        for message in r.risks():
            warnings.warn(f"Class-II TMS: {message}.", RuntimeWarning)

    def FuelCellBattery(self):
        """Solve the take-off-weight equation for a fuel-cell + battery hybrid aircraft.

            f(WTO) = W_structure + W_fuelcell + W_battery + W_H2 + W_tank + W_HX
                     + W_payload + W_crew + W_reserve - WTO

        The fuel cell is sized by ``FuelCell.ComputeAndStoreWeights``; the mission returns
        the hydrogen and battery energies. The battery is sized (Class I) by the larger of
        its energy and power requirements, using specific energy/power from EnergyInput.
        """
        energy = self.aircraft.EnergyInput
        spec_energy_Wh = energy.get('Battery Specific Energy', 250.0)   # Wh/kg
        spec_power = energy.get('Battery Specific Power', 1500.0)       # W/kg
        usable_soc = energy.get('Battery Usable SOC', 0.8)
        grav_index = energy.get('H2 Gravimetric Index', 0.35)
        h2_margin = energy.get('H2 Fuel Margin', 0.05)

        LH2_Tank = self._physics_tank_class(grav_index)

        def func(WTO):
            # Size the fuel cell self-consistently (same rule as the pure-hydrogen path, so a
            # phi=0 design coincides with it): seed from the constraints, then fly -> resize
            # the fuel cell to max(mission FC peak, take-off, OEI) of its propulsive share ->
            # re-fly until converged. The battery offloads the fuel cell (its share is
            # 1 - phi), so a larger phi shrinks the stack — but never below the take-off/OEI
            # share, which is a hard floor.
            E_h2_chem, E_bat = self._fuel_cell_and_tms_closure(WTO)
            self.WPT = self.aircraft.fuelcell.Weight

            self.WH2_Fuel = (E_h2_chem / self.ef) * (1.0 + h2_margin)
            self.Wf = self.WH2_Fuel
            # Energies used over the mission [J] = [hydrogen, battery]; consumed by the
            # well-to-wake accounting.
            self.TotalEnergies = [E_h2_chem, E_bat]

            # Battery mass. Class II: the P-number-sized physics pack (mass from the cell model,
            # set during the mission). Class I (default): max of energy- and power-limited sizing
            # from the EnergyInput specific energy/power.
            if self.aircraft.battery.BatteryClass == 'II':
                self.WBat = self.aircraft.battery.pack_weight
            else:
                # Aged pack (state of health, see Battery.set_state_of_health): the capacity
                # scales the energy per kg, the resistance growth divides the power per kg.
                b = self.aircraft.battery
                WBat_energy = (E_bat / 3600.0) / (spec_energy_Wh * b.capacity_fraction * usable_soc)
                WBat_power = self.aircraft.mission.Max_PBat * b.resistance_factor / spec_power
                self.WBat = max(WBat_energy, WBat_power)

            # Reserve hydrogen and the tank (empty) mass, sized for load + reserve.
            self.final_reserve = self._contingency if self._contingency else 0.05 * self.Wf
            self.WTank = self._hydrogen_tank_mass(self.WH2_Fuel + self.final_reserve,
                                                  LH2_Tank, grav_index)

            # Fuel-cell thermal-management mass (Class I or II, see Hydrogen()).
            self.WHeat_Exchanger = self._fuel_cell_tms_mass()
            # Class-II battery: add its thermal-management (cooling) mass from the peak in-flight
            # pack waste heat (rejected to ambient — lower specific power than the cryo-H2 HEX).
            if self.aircraft.battery.BatteryClass == 'II':
                Q_bat = self.aircraft.mission.Max_Bat_Thermal_Pwr
                hex_sp_bat = self.aircraft.EnergyInput.get('HEX Specific Power Battery', 1500.0)
                self.WHeat_Exchanger += Q_bat / hex_sp_bat if (Q_bat and Q_bat > 0) else 0.0

            # Structure.
            self.WStructure = self._structural_weight(WTO)

            return (self.WStructure + self.WPT + self.WBat + self.WH2_Fuel + self.WTank
                    + self.WHeat_Exchanger + self.WPayload + self.WCrew
                    + self.final_reserve - WTO)

        try:
            self.WTO = self._solve_wto(func, 1000, 300000, xtol=self.tol)
        except (ValueError, RuntimeError):
            raise RuntimeError(
                "Fuel-cell+battery weight loop did not converge within 1000-300000 kg "
                "(try a lower fuel-cell design voltage, more battery hybridization, or a "
                "shorter mission).")
        self._warn_tms_shortfall()
        return self.WTO


    def Hybrid(self):
        """
        Solve the weight equation for a hybrid-electric aircraft.

        Same logic as Traditional(), but includes battery sizing.

        Battery mass is computed differently depending on battery class:

        - Class I  : analytical battery mass formula
        - Class II : battery pack weight determined by P-number sizing loop
                     inside the mission model

        Returns
        -------
        float
            Converged take-off weight WTO
        """

        def func(WTO):
                """
                Weight residual function evaluated at a given WTO.

                Includes:
                 - fuel mass
                 - battery mass 
                 - propulsion mass
                 - structure mass
                 - payload + crew
                 - reserve fuel
                """

                self.TotalEnergies, self.WPT = self._mission_and_powertrain(WTO)
                self.Wf = self.TotalEnergies[0]/self.ef
                if self.aircraft.battery.BatteryClass == 'II':
                    self.WBat=self.aircraft.battery.pack_weight
                elif self.aircraft.battery.BatteryClass == 'I':
                    WBat  = [(self.TotalEnergies[1]/(1-self.aircraft.battery.SOC_min))/self.aircraft.battery.Ebat , self.aircraft.mission.Max_PBat*(1/self.aircraft.battery.pbat), self.aircraft.mission.TO_PBat*(1/self.aircraft.battery.pbat)]
                    self.WBatidx = np.argmax(WBat)
                    self.WBat = WBat[self.WBatidx] 

                self.WStructure = self._structural_weight(WTO)

                # Battery thermal-management (cooling) mass from the peak *in-flight* battery
                # waste heat (Class-II battery only; the Class-I battery has no thermal model).
                # The battery HEX rejects to ambient via a liquid loop + ram-air, so it is less
                # mass-effective than the cryo-H2 fuel-cell HEX -> a lower specific power [W/kg]
                # (user input 'HEX Specific Power Battery').
                Q_bat = self.aircraft.mission.Max_Bat_Thermal_Pwr
                hex_sp_bat = self.aircraft.EnergyInput.get('HEX Specific Power Battery', 1500.0)
                self.WHeat_Exchanger = Q_bat / hex_sp_bat if (Q_bat and Q_bat > 0) else 0.0

                self.final_reserve = self._contingency if self._contingency else 0.05 * self.Wf

                return (self.Wf + self.final_reserve + self.WBat + self.powertrain_in_closure(self.WPT) + self.WStructure
                        + self.WHeat_Exchanger + self.WPayload + self.WCrew - WTO)
        # iterate the weight estimator with Brent's method until WTO converges (robust bracketing)
        self.WTO = self._solve_wto(func, 10000, 60000, xtol=0.1)
        self._warn_gt_rating_not_converged()
