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
        

        if self.aircraft.Configuration == 'Traditional':     
             
              
                 return self.Traditional()
             
             
        elif self.aircraft.Configuration == 'Hybrid':


                 return self.Hybrid()

        elif self.aircraft.Configuration == 'Hydrogen':

                 return self.Hydrogen()

        elif self.aircraft.Configuration == 'FuelCellBattery':

                 return self.FuelCellBattery()

        else:
                 return "Try a different configuration..."


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
            
                E_fuel = self.aircraft.mission.EvaluateMission(WTO)
                self.Wf = E_fuel/self.ef
                # Energies used over the mission [J] = [fuel, battery]; consumed by the
                # well-to-wake accounting (no battery in a traditional aircraft).
                self.TotalEnergies = [E_fuel, 0.0]
                self.WPT = self.aircraft.powertrain.WeightPowertrain(WTO)

                self.WStructure = self._structural_weight(WTO)


                self.final_reserve = self._contingency if self._contingency else 0.05 * self.Wf

                return (self.Wf + self.final_reserve + self.WPT + self.WStructure + self.WPayload + self.WCrew - WTO)

        self.WTO = self._solve_wto(func, 1000, 300000, xtol=0.1)


    def Hydrogen(self):
        """Solve the take-off-weight equation for a hydrogen fuel-cell aircraft.

            f(WTO) = W_structure + W_fuelcell + W_H2 + W_tank + W_HX
                     + W_payload + W_crew + W_reserve - WTO

        The fuel-cell system mass is sized by ``FuelCell.ComputeAndStoreWeights`` (which
        also sets ``aircraft.weight.WPT``); the mission returns the hydrogen chemical
        energy, converted to usable H2 mass via the hydrogen LHV (``self.ef``) with a 5%
        installation/feed margin. Hydrogen storage mass uses the cryogenic ``LH2_Tank`` if
        available, otherwise a simple gravimetric-index model so the design always closes.
        """
        # Gravimetric index of the H2 storage system (usable H2 / total tank+H2 mass),
        # used as a fallback when the detailed cryogenic tank model is unavailable.
        grav_index = self.aircraft.EnergyInput.get('H2 Gravimetric Index', 0.35)

        # Use the physics-based LH2 tank model when a TankInput is given and CoolProp is
        # installed; otherwise fall back to the simple gravimetric-index model.
        LH2_Tank = None
        if getattr(self.aircraft, 'TankInput', None) is not None:
            try:
                from PhlyGreen.Systems.Tank import LH2_Tank
            except Exception:
                LH2_Tank = None

        def func(WTO):
            # Size the fuel cell self-consistently: seed from the constraints, then
            # fly -> resize to max(mission peak, take-off, OEI) -> re-fly until the required
            # power converges, so the fuel cell that flies the mission is the one that is
            # weighed (the take-off/OEI requirement is a hard floor on its power).
            fc = self.aircraft.fuelcell
            fc.SizeFromConstraint(WTO)
            P_req, converged = None, False
            for _ in range(_FC_RESIZE_ITERS):
                E_h2_chem = self.aircraft.mission.EvaluateMission(WTO)
                demand = max(self.aircraft.mission.TO_PP, self.aircraft.mission.Max_PEng)
                if P_req is not None and abs(demand - P_req) <= 1e-3 * max(P_req, 1.0):
                    converged = True
                    break
                P_req = demand
                fc.SizeForPropulsivePower(P_req)
            if not converged:                 # ensure the final stack size was actually flown
                E_h2_chem = self.aircraft.mission.EvaluateMission(WTO)
            self.WPT = fc.Weight

            self.WH2_Fuel = (E_h2_chem / self.ef) * 1.05
            self.Wf = self.WH2_Fuel
            # Energies used over the mission [J] = [hydrogen, battery]; consumed by the
            # well-to-wake accounting (no battery in a pure fuel-cell aircraft).
            self.TotalEnergies = [E_h2_chem, 0.0]

            # 3. Hydrogen tank (empty) mass.
            if self.WH2_Fuel <= 0:
                self.WTank = 0.0
            elif LH2_Tank is not None:
                self.aircraft.tank = LH2_Tank(capacity_kg=self.WH2_Fuel, aircraft=self.aircraft)
                self.WTank = self.aircraft.tank.mass_system_empty
            else:
                self.WTank = self.WH2_Fuel * (1.0 / grav_index - 1.0)

            # 4. Thermal-management (heat-exchanger) mass from the peak fuel-cell heat load.
            # The cryogenic H2 is an effective heat sink, so the HEX is light per kW of heat
            # rejected (high specific power [W/kg]; user input 'HEX Specific Power H2').
            Q_max = self.aircraft.mission.Max_FC_Thermal_Pwr
            hex_sp_h2 = self.aircraft.EnergyInput.get('HEX Specific Power H2', 5000.0)
            self.WHeat_Exchanger = Q_max / hex_sp_h2 if Q_max > 0 else 0.0

            # 5. Structure.
            self.WStructure = self._structural_weight(WTO)

            # 6. Reserve (fixed input mass, else 5% of the usable H2) and sum.
            self.final_reserve = self._contingency if self._contingency else 0.05 * self.Wf

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
        return self.WTO


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

        LH2_Tank = None
        if getattr(self.aircraft, 'TankInput', None) is not None:
            try:
                from PhlyGreen.Systems.Tank import LH2_Tank
            except Exception:
                LH2_Tank = None

        def func(WTO):
            # Size the fuel cell self-consistently (same rule as the pure-hydrogen path, so a
            # phi=0 design coincides with it): seed from the constraints, then fly -> resize
            # the fuel cell to max(mission FC peak, take-off, OEI) of its propulsive share ->
            # re-fly until converged. The battery offloads the fuel cell (its share is
            # 1 - phi), so a larger phi shrinks the stack — but never below the take-off/OEI
            # share, which is a hard floor.
            fc = self.aircraft.fuelcell
            fc.SizeFromConstraint(WTO)
            P_req, converged = None, False
            for _ in range(_FC_RESIZE_ITERS):
                E_h2_chem, E_bat = self.aircraft.mission.EvaluateMission(WTO)
                demand = max(self.aircraft.mission.TO_PP, self.aircraft.mission.Max_PEng)
                if P_req is not None and abs(demand - P_req) <= 1e-3 * max(P_req, 1.0):
                    converged = True
                    break
                P_req = demand
                fc.SizeForPropulsivePower(P_req)
            if not converged:
                E_h2_chem, E_bat = self.aircraft.mission.EvaluateMission(WTO)
            self.WPT = fc.Weight

            self.WH2_Fuel = (E_h2_chem / self.ef) * 1.05
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
                WBat_energy = (E_bat / 3600.0) / (spec_energy_Wh * usable_soc)
                WBat_power = self.aircraft.mission.Max_PBat / spec_power
                self.WBat = max(WBat_energy, WBat_power)

            # Hydrogen tank (empty) mass.
            if self.WH2_Fuel <= 0:
                self.WTank = 0.0
            elif LH2_Tank is not None:
                self.aircraft.tank = LH2_Tank(capacity_kg=self.WH2_Fuel, aircraft=self.aircraft)
                self.WTank = self.aircraft.tank.mass_system_empty
            else:
                self.WTank = self.WH2_Fuel * (1.0 / grav_index - 1.0)

            # Cooling (heat-exchanger) mass from peak fuel-cell heat — H2-cooled HEX specific
            # power [W/kg] (user input 'HEX Specific Power H2').
            Q_max = self.aircraft.mission.Max_FC_Thermal_Pwr
            hex_sp_h2 = self.aircraft.EnergyInput.get('HEX Specific Power H2', 5000.0)
            self.WHeat_Exchanger = Q_max / hex_sp_h2 if Q_max > 0 else 0.0
            # Class-II battery: add its thermal-management (cooling) mass from the peak in-flight
            # pack waste heat (rejected to ambient — lower specific power than the cryo-H2 HEX).
            if self.aircraft.battery.BatteryClass == 'II':
                Q_bat = self.aircraft.mission.Max_Bat_Thermal_Pwr
                hex_sp_bat = self.aircraft.EnergyInput.get('HEX Specific Power Battery', 1500.0)
                self.WHeat_Exchanger += Q_bat / hex_sp_bat if (Q_bat and Q_bat > 0) else 0.0

            # Structure.
            self.WStructure = self._structural_weight(WTO)

            self.final_reserve = self._contingency if self._contingency else 0.05 * self.Wf

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

                self.TotalEnergies = self.aircraft.mission.EvaluateMission(WTO)
                self.Wf = self.TotalEnergies[0]/self.ef
                if self.aircraft.battery.BatteryClass == 'II':
                    self.WBat=self.aircraft.battery.pack_weight
                elif self.aircraft.battery.BatteryClass == 'I':
                    WBat  = [(self.TotalEnergies[1]/(1-self.aircraft.battery.SOC_min))/self.aircraft.battery.Ebat , self.aircraft.mission.Max_PBat*(1/self.aircraft.battery.pbat), self.aircraft.mission.TO_PBat*(1/self.aircraft.battery.pbat)]
                    self.WBatidx = np.argmax(WBat)
                    self.WBat = WBat[self.WBatidx] 

                self.WPT = self.aircraft.powertrain.WeightPowertrain(WTO)

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

                return (self.Wf + self.final_reserve + self.WBat + self.WPT + self.WStructure
                        + self.WHeat_Exchanger + self.WPayload + self.WCrew - WTO)
        # iterate the weight estimator with Brent's method until WTO converges (robust bracketing)
        self.WTO = self._solve_wto(func, 10000, 60000, xtol=0.1)