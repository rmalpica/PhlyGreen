import numpy as np
import numbers
import math
import warnings
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed
import PhlyGreen.Utilities.Units as Units
import scipy.integrate as integrate
from .Profile import Profile
from PhlyGreen.Systems.Battery.Battery import BatteryError

class Mission:
    """
    Mission-level performance and energy simulation.

    This class defines and evaluates the complete mission simulation of a point-mass aircraft,
    including the time history of propulsive power, fuel burn, electric power
    usage, battery consumption, aircraft mass fraction evolution, and peak subsystem
    loads.

    It supports:
    - Traditional thermal propulsion configurations
    - Hybrid-electric configurations (Class I and Class II battery models)
    - Time-dependent integration of the governing ODEs across mission segments
    - Peak power analysis and altitude at which peak power occurs
    - Battery sizing (for Class II missions using iterative Parallel cells number `P-number` search)

    Parameters
    ----------
    aircraft : Aircraft
        Parent aircraft object containing propulsion, performance, constraint,
        and battery models.

    Notes
    -----
    - `Beta` is the instantaneous mass fraction (`W/W_TO`).
    - Fuel energy `Ef` and battery energy `EBat` are integrated over time.
    - Hybrid Class II missions rely on iterative sizing of a battery P-number,
      ensuring voltage, SOC, current, and thermal constraints are satisfied.
    """
  
    def __init__(self, aircraft):
        self.aircraft = aircraft

        self.beta0 = None 
        self.DISA = 0
        self.WTO = None
        self.Max_PBat = -1
        self.Max_PEng = -1
        self.Max_PEng_alt = 0
        self.TO_PBat = 0
        self.TO_PP = 0
        # peak in-flight battery waste heat [W] (Class-II battery), for TMS sizing
        self.Max_Bat_Thermal_Pwr = -1.0
        # hydrogen fuel-cell mission tracking
        self.Max_FC_Thermal_Pwr = 0.0
        self.Max_FC_Thermal_Pwr_alt = 0.0
        self.TO_P_H2_Thermal = 0.0
        # when True (and aircraft.tank is set) the LH2 tank thermodynamic state is
        # advanced through the mission; off by default so the weight loop stays fast.
        self.track_tank = False

        self.ef = None
        self.profile = None
        self.t = None
        self.Ef = None
        self.EBat = None
        self.Beta = None
        self.startT = 25
        self.T_battery_limit = 40. # Celsius

        self.Past_P_n=[]
        self.P_n_arr =[]
        self.last_weight=None
        self.optimal_n=None

        self.size_battery_pack = True

    """ Properties """

    @property
    def beta0(self):
        """Initial mass fraction W/W_TO at start of mission. Note that mission profile does not include taxi and take-off, 
           so beta0 is used to account for mass depletion in such phases"""
        if self._beta0 is None:
            raise ValueError("Initial weight fraction beta0 unset. Exiting")
        return self._beta0
      
    @beta0.setter
    def beta0(self,value):
        self._beta0 = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal weight fraction beta0: %e. Exiting" %value)

    @property
    def ef(self):
        """Fuel specific energy [J/kg]."""
        if self._ef is None:
            raise ValueError("Fuel specific energy unset. Exiting")
        return self._ef
      
    @ef.setter
    def ef(self,value):
        self._ef = value
        if(isinstance(value, numbers.Number) and (value <= 0)):
            raise ValueError("Error: Illegal fuel specific energy: %e. Exiting" %value)

    """Methods """

    def check_PP(self,PP):
        """
        Ensure propulsive power is non-negative. This can happen if the mission profile 
        is badly designed in the descent phase (e.g. excessive rate of descent)

        Parameters
        ----------
        PP : float
            Propulsive power.

        Returns
        -------
        float
            PP clipped to a minimum of zero, with a warning if clipping occurs.
        """
        if PP < 0:
            warnings.warn(". Setting Propulsive power to 0.", RuntimeWarning)
            PP = 0
        return PP


    def SetInput(self):
        """
        Read mission input parameters from the aircraft object.

        Must be called before mission evaluation.
        """

        self.beta0 = self.aircraft.MissionInput['Beta start']
        self.ef = self.aircraft.EnergyInput['Ef']

    def InitializeProfile(self):
        """
        Construct and initialize the mission profile. Requires the Profile class to be already initialized.

        Creates the flight profile and generates a time grid.
        """
        
        self.profile = Profile(self.aircraft)
        
        self.profile.DefineMission()
        
        self.t = np.linspace(0,self.profile.MissionTime2,num=1000)


    def EvaluateMission(self,WTO):
        """
        Evaluates and returns mission energy consumption for the chosen configuration.

        Parameters
        ----------
        WTO : float
            Takeoff weight [kg].

        Returns
        -------
        float or tuple
            Traditional: (cumulative fuel energy [J])
            Hybrid Class I: (cumulative fuel energy [J], cumulative battery energy [J])
            Hybrid Class II: same, after battery sizing
        """
        
        if self.aircraft.Configuration == 'Traditional':     
            return self.TraditionalConfiguration(WTO)
            
        elif self.aircraft.Configuration == 'Hybrid':
            # Serial "range-extender" strategy: a constant-power gas turbine with the battery
            # buffering surplus/deficit (so it recharges in flight). Triggered by a 'GT Rated
            # Power' input on a Serial hybrid; otherwise the standard phi-split path runs.
            if (self.aircraft.HybridType == 'Serial'
                    and self.aircraft.EnergyInput.get('GT Rated Power')):
                return self.SerialRangeExtenderConfiguration(WTO)
            if self.aircraft.battery.BatteryClass == 'II':
                return self.HybridConfigurationClassII(WTO)
            elif self.aircraft.battery.BatteryClass == 'I':
                return self.HybridConfigurationClassI(WTO)

        elif self.aircraft.Configuration == 'Hydrogen':
            return self.HydrogenConfiguration(WTO)

        elif self.aircraft.Configuration == 'FuelCellBattery':
            if getattr(self.aircraft.battery, 'BatteryClass', None) == 'II':
                return self.FuelCellBatteryConfigurationClassII(WTO)
            return self.FuelCellBatteryConfiguration(WTO)

        else:
            raise Exception("Unknown aircraft configuration: %s" %self.aircraft.Configuration)


    # --- shared off-mission power requirements ------------------------------------------
    # The take-off field-length and one-engine-inoperative climb conditions are not flown by
    # the mission profile, but every powertrain must still be able to supply their power.
    # Each configuration method computes the same worst case and then splits it between its
    # energy sources, so the computation lives here once (identical for all configurations).

    def _takeoff_power(self, WTO):
        """Propulsive power required by the take-off field-length constraint [W]."""
        c = self.aircraft.constraint
        to = c.TakeOffConstraints
        return WTO * self.aircraft.performance.TakeOff(
            self.aircraft.DesignWTOoS, to['Beta'], to['Altitude'], to['kTO'],
            to['sTO'], c.DISA, to['Speed'], to['Speed Type'])

    def _oei_climb_power(self, WTO):
        """Propulsive power required by the one-engine-inoperative climb constraint [W]."""
        c = self.aircraft.constraint
        oei = c.OEIClimbConstraints
        return WTO * self.aircraft.performance.OEIClimb(
            self.aircraft.DesignWTOoS, oei['Beta'],
            oei['Speed'] * oei['Climb Gradient'], 1., oei['Altitude'],
            c.DISA, oei['Speed'], oei['Speed Type'])

    def _worst_case_propulsive_power(self, WTO):
        """Worst-case off-mission propulsive power = max(take-off, OEI climb) [W]."""
        return max(self._takeoff_power(WTO), self._oei_climb_power(WTO))


    def HydrogenConfiguration(self, WTO):
        """Evaluate the full mission for a hydrogen fuel-cell (electric) propulsion system.

        Integrates two states over the mission: cumulative hydrogen *chemical* energy and
        the mass fraction Beta. At each instant the fuel cell converts the required
        propulsive shaft power into a hydrogen chemical-power demand via
        ``fuelcell.ComputePRatio`` (whose first entry is 1 / system efficiency). Tracks the
        peak fuel-cell thermal load for sizing the thermal-management system.

        Returns:
            float: total hydrogen chemical energy consumed over the mission [J].
        """
        self.WTO = WTO

        def PowerPropulsive(Beta, t):
            PPoWTO = self.aircraft.performance.PoWTO(
                self.aircraft.DesignWTOoS, Beta, self.profile.PowerExcess(t), 1,
                self.profile.Altitude(t), self.DISA, self.profile.Velocity(t), 'TAS')
            return PPoWTO * WTO

        def model(t, y):
            Beta = y[1]
            PP = PowerPropulsive(Beta, t)
            self.check_PP(PP)
            PRatio = self.aircraft.fuelcell.ComputePRatio(
                self.profile.Altitude(t), self.profile.Velocity(t), PP)
            dEdt_chem = PP * PRatio[0]                 # hydrogen chemical power [W]
            dbetadt = - dEdt_chem / (self.ef * self.WTO)
            q = self.aircraft.fuelcell.Q_thermal
            if q > self.Max_FC_Thermal_Pwr:
                self.Max_FC_Thermal_Pwr = q
                self.Max_FC_Thermal_Pwr_alt = self.profile.Altitude(t)
            return [dEdt_chem, dbetadt]

        # Worst-case off-mission propulsive power for fuel-cell sizing: the take-off field
        # length and the one-engine-inoperative climb, evaluated at the *constraint* conditions
        # (these scenarios are not flown by the mission profile, but the fuel cell must supply
        # their power). Taken as the worst case.
        self.TO_PP = self._worst_case_propulsive_power(WTO)
        PRatio_TO = self.aircraft.fuelcell.ComputePRatio(
            self.aircraft.constraint.TakeOffConstraints['Altitude'],
            self.aircraft.constraint.TakeOffConstraints['Speed'], self.TO_PP)
        self.TO_P_H2_Thermal = self.TO_PP * PRatio_TO[0]
        self.Max_FC_Thermal_Pwr = -1.0

        # Optionally advance the LH2 tank thermodynamic state through the mission.
        track = self.track_tank and getattr(self.aircraft, 'tank', None) is not None
        if track:
            tank = self.aircraft.tank
            tank.m_curr = tank.capacity_single        # start full
            tank.P_curr = tank.P_min
            tank.history = {'t': [], 'P': [], 'm_tot': [], 'Vent': [], 'Q_in': [],
                            'Alt': [], 'Q_heater': [], 'm_vent_cum': [], 'Consumption': []}
            tank.cum_vented_mass = 0.0

        y0 = [0, self.beta0]
        self.integral_solution = []
        times = np.append(self.profile.Breaks, self.profile.MissionTime2)
        for i in range(len(times) - 1):
            sol = integrate.solve_ivp(model, [times[i], times[i + 1]], y0,
                                      method='BDF', rtol=1e-5, max_step=60.0)
            self.integral_solution.append(sol)
            if track:
                # Drive the tank with the hydrogen mass flow over each solver micro-step.
                for k in range(1, len(sol.t)):
                    dt_mini = sol.t[k] - sol.t[k - 1]
                    dE = max(sol.y[0][k] - sol.y[0][k - 1], 0.0)
                    m_dot = (dE / self.ef) / dt_mini if dt_mini > 0 else 0.0
                    t_mid = 0.5 * (sol.t[k] + sol.t[k - 1])
                    tank.time_step(dt_mini, m_dot, float(self.profile.Altitude(t_mid)))
            y0 = [sol.y[0][-1], sol.y[1][-1]]

        self.Ef = sol.y[0]
        self.Beta = sol.y[1]

        # Peak mission propulsive power (no hidden margin — the sizing margin and the
        # take-off/OEI floor are applied by the weight loop / FuelCell sizing).
        pp_peak = 0.0
        for arr in self.integral_solution:
            for k in range(len(arr.t)):
                pp_peak = max(pp_peak, PowerPropulsive(arr.y[1][k], arr.t[k]))
        self.Max_PEng = pp_peak
        self.Max_PEng_alt = 0.0
        return self.Ef[-1]


    def FuelCellBatteryConfiguration(self, WTO):
        """Evaluate the full mission for a fuel-cell + battery hybrid (electric) system.

        The propulsive power at each instant is split between a hydrogen fuel cell and a
        battery according to the profile's supplied-power ratio phi (the battery fraction):
        the battery covers ``phi`` of the propulsive power and the fuel cell the remaining
        ``1 - phi``. The fuel-cell branch uses the physics-based fuel-cell efficiency
        (``fuelcell.ComputePRatio``); the battery branch uses the electric chain efficiency.

        Integrates three states: hydrogen chemical energy, battery (electrical) energy, and
        the mass fraction Beta (only hydrogen burn changes the aircraft mass).

        Returns:
            tuple(float, float): (hydrogen chemical energy [J], battery energy [J]).
        """
        self.WTO = WTO
        fc = self.aircraft.fuelcell

        # Battery electrical -> shaft efficiency. Constant by default; when the Class-II
        # ('Smart') d-q motor model is selected, the electric-motor term varies with the
        # operating point.
        em_smart = self.aircraft.EnergyInput.get('Eta Electric Motor Model') == 'Smart'

        def eta_elec_at(alt, vel, P):
            em = self.aircraft.powertrain.eta('electric_motor', alt, vel, P) if em_smart else fc.EtaEM
            return em * fc.EtaPM * fc.EtaGB

        def PowerPropulsive(Beta, t):
            PPoWTO = self.aircraft.performance.PoWTO(
                self.aircraft.DesignWTOoS, Beta, self.profile.PowerExcess(t), 1,
                self.profile.Altitude(t), self.DISA, self.profile.Velocity(t), 'TAS')
            return PPoWTO * WTO

        def fuel_cell_share(t, PP):
            phi = float(self.profile.SuppliedPowerRatio(t))   # battery fraction of PP
            return (1.0 - phi) * PP

        # Two-state ODE (hydrogen chemical energy, mass fraction) — identical in form to the
        # pure-hydrogen mission, so a battery-free (phi=0) design reproduces it exactly. The
        # battery energy is a passive integral computed afterwards (it does not burn mass).
        def model(t, y):
            Beta = y[1]
            PP = PowerPropulsive(Beta, t)
            self.check_PP(PP)
            P_fc = fuel_cell_share(t, PP)
            alt, vel = self.profile.Altitude(t), self.profile.Velocity(t)
            dEh2 = P_fc * fc.ComputePRatio(alt, vel, P_fc)[0] if P_fc > 0 else 0.0
            dbetadt = - dEh2 / (self.ef * self.WTO)
            q = fc.Q_thermal
            if q > self.Max_FC_Thermal_Pwr:
                self.Max_FC_Thermal_Pwr = q
                self.Max_FC_Thermal_Pwr_alt = alt
            return [dEh2, dbetadt]

        # Worst-case off-mission propulsive power (take-off field length / OEI climb) at the
        # constraint conditions, split between the fuel cell and the battery by the take-off phi.
        P_total_TO = self._worst_case_propulsive_power(WTO)
        phi_TO = float(self.profile.SPW[0][0]) if self.profile.SPW is not None else 0.0
        self.TO_PP = (1.0 - phi_TO) * P_total_TO    # fuel-cell propulsive share at take-off/OEI
        self.TO_PBat = phi_TO * P_total_TO          # battery propulsive share at take-off/OEI
        self.Max_FC_Thermal_Pwr = -1.0

        y0 = [0.0, self.beta0]
        self.integral_solution = []
        times = np.append(self.profile.Breaks, self.profile.MissionTime2)
        for i in range(len(times) - 1):
            sol = integrate.solve_ivp(model, [times[i], times[i + 1]], y0,
                                      method='BDF', rtol=1e-5, max_step=60.0)
            self.integral_solution.append(sol)
            y0 = [sol.y[0][-1], sol.y[1][-1]]

        self.Ef = sol.y[0]
        self.Beta = sol.y[1]

        # Post-process the battery: electrical energy drawn and peak battery shaft power.
        E_bat = 0.0
        pp_fc_peak, pp_bat_peak = 0.0, 0.0
        for arr in self.integral_solution:
            p_bat = np.array([float(self.profile.SuppliedPowerRatio(t)) *
                              PowerPropulsive(b, t) for t, b in zip(arr.t, arr.y[1])])
            p_fc = np.array([PowerPropulsive(b, t) for t, b in zip(arr.t, arr.y[1])]) - p_bat
            if len(arr.t) > 1:
                eta_arr = np.array([eta_elec_at(self.profile.Altitude(t), self.profile.Velocity(t), pb)
                                    for t, pb in zip(arr.t, p_bat)])
                E_bat += float(np.trapezoid(p_bat / eta_arr, arr.t))
            pp_bat_peak = max(pp_bat_peak, float(p_bat.max()) if len(p_bat) else 0.0)
            pp_fc_peak = max(pp_fc_peak, float(p_fc.max()) if len(p_fc) else 0.0)
        self.EBat = E_bat
        self.Max_PEng = pp_fc_peak           # fuel-cell propulsive peak (no hidden margin)
        self.Max_PEng_alt = 0.0
        self.Max_PBat = max(pp_bat_peak, self.TO_PBat)
        return self.Ef[-1], self.EBat


    def FuelCellBatteryConfigurationClassII(self, WTO):
        """Fuel-cell + battery mission with a **Class-II** (cell-level electro-thermal) battery.

        Same propulsive split as :meth:`FuelCellBatteryConfiguration` — the battery covers
        ``phi`` of the propulsive power and the fuel cell the remaining ``1 - phi`` — but the
        battery is the physics cell model: the mission integrates the pack state (charge and
        temperature) and the pack is **P-number sized** so the SOC / voltage / current limits
        hold over the real mission current profile, exactly as :meth:`HybridConfigurationClassII`
        does for the gas-turbine hybrid. Five ODE states are carried:
        ``[E_h2, E_bat, Beta, it (As), T (K)]``. Returns ``(hydrogen chemical energy, battery
        energy)`` and leaves ``aircraft.battery.pack_weight`` and ``Max_Bat_Thermal_Pwr`` for the
        weight loop.
        """
        self.WTO = WTO
        fc = self.aircraft.fuelcell

        # Battery electrical -> shaft efficiency. Constant by default; the electric-motor term
        # becomes operating-point dependent when the Class-II ('Smart') d-q model is selected.
        em_smart = self.aircraft.EnergyInput.get('Eta Electric Motor Model') == 'Smart'

        def eta_elec_at(alt, vel, P):
            em = self.aircraft.powertrain.eta('electric_motor', alt, vel, P) if em_smart else fc.EtaEM
            return em * fc.EtaPM * fc.EtaGB

        def PowerPropulsive(Beta, t):
            return WTO * self.aircraft.performance.PoWTO(
                self.aircraft.DesignWTOoS, Beta, self.profile.PowerExcess(t), 1,
                self.profile.Altitude(t), self.DISA, self.profile.Velocity(t), 'TAS')

        def model(t, y):
            # states: y = [E_h2, E_bat, Beta, it (As), T (K)]
            Beta = y[2]
            PP = self.check_PP(PowerPropulsive(Beta, t))
            phi = float(self.profile.SuppliedPowerRatio(t))     # battery fraction of PP
            alt, vel = self.profile.Altitude(t), self.profile.Velocity(t)

            # fuel-cell (hydrogen) branch — the fuel cell supplies (1 - phi) of the power
            P_fc = (1.0 - phi) * PP
            dEh2 = P_fc * fc.ComputePRatio(alt, vel, P_fc)[0] if P_fc > 0 else 0.0
            q = fc.Q_thermal
            if q > self.Max_FC_Thermal_Pwr:
                self.Max_FC_Thermal_Pwr = q
                self.Max_FC_Thermal_Pwr_alt = alt
            dbetadt = - dEh2 / (self.ef * self.WTO)             # only hydrogen burn changes mass

            # battery branch — Class-II cell model. The pack must deliver phi*PP of shaft power,
            # i.e. phi*PP/eta_elec of electrical power at its terminals.
            PElectric = (phi * PP) / eta_elec_at(alt, vel, phi * PP)
            b = self.aircraft.battery
            b.T = y[4]
            b.phi = phi
            b.it = y[3] / 3600                                 # spent charge -> SOC (validated)
            b.i = b.Power_2_current(PElectric)                 # current (validated)
            dEdt_bat = b.i * b.Vout                             # Vout generated + validated

            Mach = Speed.TAS2Mach(vel, alt, DISA=self.DISA)
            Tamb = ISA.atmosphere.T0std(alt, Mach)
            rho = ISA.atmosphere.RHO0std(alt, Mach, self.DISA)
            dTdt, _ = b.heatLoss(Tamb, rho)
            if phi > 0.:                                        # bang-bang thermostat at the ceiling
                dTdt = max(dTdt, 0.) if y[4] < 273.15 + self.T_battery_limit else 0.
            else:
                dTdt = min(dTdt, 0.)
            return [dEh2, dEdt_bat, dbetadt, b.i, dTdt]

        # Worst-case off-mission propulsive power (take-off field length / OEI climb) and its
        # battery / fuel-cell shares, at the constraint conditions.
        P_total_TO = self._worst_case_propulsive_power(WTO)
        phi_TO = float(self.profile.SPW[0][0]) if self.profile.SPW is not None else 0.0
        self.TO_PP = (1.0 - phi_TO) * P_total_TO            # fuel-cell propulsive share at TO/OEI
        self.TO_PBat = phi_TO * P_total_TO                 # battery propulsive share at TO/OEI

        def evaluate_mission_given_P(P_number):
            """Fly the whole mission for a given parallel-cell count; (feasible, error_code)."""
            self.P_n_arr.append(P_number)
            if P_number == 0:
                return False, None
            self.aircraft.battery.Configure(P_number)
            # Take-off battery feasibility (independent of the integration).
            try:
                self.aircraft.battery.T = self.startT + 273.15
                self.aircraft.battery.it = 0
                _to_alt = self.aircraft.constraint.TakeOffConstraints['Altitude']
                _to_spd = self.aircraft.constraint.TakeOffConstraints['Speed']
                self.aircraft.battery.i = self.aircraft.battery.Power_2_current(
                    self.TO_PBat / eta_elec_at(_to_alt, _to_spd, self.TO_PBat))
                self.aircraft.battery.Vout
            except BatteryError as err:
                if not self.size_battery_pack:
                    print(err)
                return False, err.code

            np.seterr(over="raise")
            times = np.append(self.profile.Breaks, self.profile.MissionTime2)
            self.integral_solution = []
            self.Max_FC_Thermal_Pwr = -1.0
            y0 = [0, 0, self.beta0, 0, self.startT + 273.15]
            for i in range(len(times) - 1):
                try:
                    sol = integrate.solve_ivp(model, [times[i], times[i + 1]], y0,
                                              method="BDF", rtol=1e-6)
                    self.integral_solution.append(sol)
                except BatteryError as err:
                    if not self.size_battery_pack:
                        print(err)
                    return False, err.code
                self.Ef = sol.y[0]
                self.EBat = sol.y[1]
                self.Beta = sol.y[2]
                y0 = [sol.y[0][-1], sol.y[1][-1], sol.y[2][-1], sol.y[3][-1], sol.y[4][-1]]
            return True, None

        def find_P_nr(n_guess, wto_ratio):
            """Minimal feasible parallel-cell count via doubling/halving brackets + bisection."""
            if wto_ratio is not None:
                n_max = math.ceil(n_guess * wto_ratio)
                n_min = n_max - 1
            else:
                n_max = n_guess
                n_min = math.floor(n_max / 2)
            nmax_is_bounded = False
            while evaluate_mission_given_P(n_min)[0]:
                n_max = n_min
                n_min = math.floor(n_min / 2)
                nmax_is_bounded = True
            if not nmax_is_bounded:
                while not evaluate_mission_given_P(n_max)[0]:
                    n_min = n_max
                    n_max = n_max * 2
            n = math.ceil((n_max + n_min) / 2)
            optimal = False
            while not optimal:
                valid = evaluate_mission_given_P(n)[0]
                if valid and (n - n_min) == 1:
                    optimal = True
                elif valid:
                    n_max = n
                    n = math.floor((n_max + n_min) / 2)
                else:
                    n_min = n
                    n = math.ceil((n_max + n_min) / 2)
            return n

        if self.size_battery_pack:
            ratio = None if self.last_weight is None else self.WTO / self.last_weight
            P_n_guess = 128 if self.optimal_n is None else self.optimal_n
            self.optimal_n = find_P_nr(P_n_guess, ratio)
            self.last_weight = self.WTO
            self.Past_P_n.append(self.P_n_arr)
            self.P_n_arr = []
        else:
            success, code = evaluate_mission_given_P(self.aircraft.battery.P_number)
            if not success:
                return 0, code

        # Peak fuel-cell / battery propulsive power and the battery TMS heat over the sized mission.
        times, beta, it_arr, T_arr = [], [], [], []
        for arr in self.integral_solution:
            times = np.concatenate([times, arr.t])
            beta = np.concatenate([beta, arr.y[2]])
            it_arr = np.concatenate([it_arr, arr.y[3]])
            T_arr = np.concatenate([T_arr, arr.y[4]])
        self.MissionTimes = times
        PP = np.array([WTO * self.aircraft.performance.PoWTO(
            self.aircraft.DesignWTOoS, beta[i], self.profile.PowerExcess(times[i]), 1,
            self.profile.Altitude(times[i]), self.DISA, self.profile.Velocity(times[i]), 'TAS')
            for i in range(len(times))])
        phis = np.array([float(self.profile.SuppliedPowerRatio(times[i])) for i in range(len(times))])
        p_fc, p_bat = (1.0 - phis) * PP, phis * PP
        self.Max_PEng = float(np.max(p_fc)) if len(p_fc) else 0.0
        self.Max_PEng_alt = self.profile.Altitude(times[int(np.argmax(p_fc))]) if len(p_fc) else 0.0
        self.Max_PBat = max(float(np.max(p_bat)) if len(p_bat) else 0.0, self.TO_PBat)

        ceiling = 273.15 + self.T_battery_limit
        b = self.aircraft.battery
        q_pack_peak = 0.0
        for i in range(len(times)):
            if T_arr[i] < ceiling - 0.5:                   # cooling acts only at the ceiling
                continue
            try:
                b.T = T_arr[i]
                b.it = it_arr[i] / 3600
                alt = self.profile.Altitude(times[i])
                vel = self.profile.Velocity(times[i])
                b.i = b.Power_2_current(p_bat[i] / eta_elec_at(alt, vel, p_bat[i]))
                Mach = Speed.TAS2Mach(vel, alt, DISA=self.DISA)
                Tamb = ISA.atmosphere.T0std(alt, Mach)
                rho = ISA.atmosphere.RHO0std(alt, Mach, self.DISA)
                _, q_cell = b.heatLoss(Tamb, rho)
                q_pack_peak = max(q_pack_peak, q_cell * b.cells_total)
            except Exception:
                continue
        self.Max_Bat_Thermal_Pwr = q_pack_peak

        return self.Ef[-1], self.EBat[-1]


    def TraditionalConfiguration(self,WTO):
        """
        Evaluate the complete mission for a traditional (non-hybrid) propulsion system.

        Includes:
        - instantaneous propulsive power calculation
        - fuel-burn ODE integration
        - peak thermal shaft power evaluation

        Parameters
        ----------
        WTO : float
            Takeoff weight [kg].

        Returns
        -------
        float
            Final cumulative fuel energy [J].
        """
 
        self.WTO = WTO
        
        
        def PowerPropulsive(Beta,t):
            """Return required propulsive power = PP/WTO · WTO."""

            PPoWTO = self.aircraft.performance.PoWTO(
                self.aircraft.DesignWTOoS,
                Beta,
                self.profile.PowerExcess(t),
                1,
                self.profile.Altitude(t),
                self.DISA,
                self.profile.Velocity(t),
                'TAS'
                )

            return PPoWTO * WTO

        
        def model(t,y):
            """
            System ODE:
            y[0] = fuel energy consumed
            y[1] = Beta (mass fraction)

            Returns RHS:
            dy/dt = [dE/dt, dbeta/dt]
            """
            Beta = y[1]
            PP = PowerPropulsive(Beta,t)
            self.check_PP(PP)
            PRatio = self.aircraft.powertrain.Traditional(
                self.profile.Altitude(t),
                self.profile.Velocity(t),
                PP
                )
            dEdt = PP * PRatio[0]
            dbetadt = - dEdt/(self.ef*self.WTO)

            return [dEdt,dbetadt]

        # Takeoff / OEI-climb worst case (see _worst_case_propulsive_power)
        Ppropulsive = self._worst_case_propulsive_power(self.WTO)

        PRatio = self.aircraft.powertrain.Traditional(
            self.aircraft.constraint.TakeOffConstraints['Altitude'],
            self.aircraft.constraint.TakeOffConstraints['Speed'],
            Ppropulsive
            )
        self.TO_PP = Ppropulsive * PRatio[1] #shaft power 

        #set/reset max values
        self.Max_Peng = -1
   

        # initial condition
        y0 = [0,self.beta0]  #here y0[0] should be the TakeOff energy consumed: WTO * self.TO_PFoW * deltat 

        rtol = 1e-5
        method= 'BDF'

        # integrate all phases together
        # sol = integrate.solve_ivp(model,[0, self.profile.MissionTime2],y0,method='BDF',rtol=1e-6)
        
        # integrate sequentially
        self.integral_solution = []
        times = np.append(self.profile.Breaks,self.profile.MissionTime2)
        for i in range(len(times)-1):
            sol = integrate.solve_ivp(model,[times[i], times[i+1]],y0,method=method,rtol=rtol) 
            self.integral_solution.append(sol) 
            y0 = [sol.y[0][-1],sol.y[1][-1]]
        
        self.Ef = sol.y[0]
        self.Beta = sol.y[1]
        
        # compute peak Propulsive power along mission
        times = []
        beta = []
        for array in self.integral_solution:
            times = np.concatenate([times, array.t])
            beta = np.concatenate([beta, array.y[1]])

    

        PP = [WTO * self.aircraft.performance.PoWTO(
            self.aircraft.DesignWTOoS,
            beta[i],
            self.profile.PowerExcess(times[i]),
            1,
            self.profile.Altitude(times[i]),
            self.DISA,
            self.profile.Velocity(times[i]),
            'TAS') for i in range(len(times))]

        PRatio = np.array([self.aircraft.powertrain.Traditional(self.profile.Altitude(times[i]),self.profile.Velocity(times[i]),PP[i]) for i in range(len(times))] )
        self.Max_PEng = np.max(np.multiply(PP,PRatio[:,1])) #shaft power
        self.Max_PEng_alt = self.profile.Altitude(times[np.argmax(np.multiply(PP,PRatio[:,1]))]) #altitude at which peak power occurs 

        return self.Ef[-1]
    
    
    def HybridConfigurationClassI(self,WTO):
            """
            Evaluate the mission for a Hybrid-Electric aircraft using a Class I battery model.

            Class I battery:
                - Does NOT enforce electrochemical or thermal limits.
                - Battery energy is updated simply from power * efficiency relationships.
                - No P-number sizing loop is used.

            Output:
                - Fuel consumption (Ef)
                - Battery energy consumption (EBat)
                - Mission-level peak thermal and electric power

            Parameters
            ----------
            WTO : float
                Takeoff weight [kg].

            Returns
            -------
            tuple
                (final cumulative fuel energy [J], final cumulative battery energy [J])
            """
            
            self.WTO = WTO
            
            def PowerPropulsive(Beta,t):
                """Return required propulsive power = PP/WTO · WTO."""

                PPoWTO = self.aircraft.performance.PoWTO(
                    self.aircraft.DesignWTOoS,
                    Beta,
                    self.profile.PowerExcess(t),
                    1,
                    self.profile.Altitude(t),
                    self.DISA,
                    self.profile.Velocity(t),
                    'TAS'
                    )
            
                return PPoWTO * WTO

            
            def model(t,y):
                """
                Governing ODEs. State vector:
                y[0] = cumulative fuel energy Ef
                y[1] = cumulative battery energy EBat
                y[2] = mass fraction Beta

                Returns RHS dy/dy = [dEFdt,dEBatdt,dbetadt]
                """
                
                Beta = y[2]
                Ppropulsive = PowerPropulsive(Beta,t)
                self.check_PP(Ppropulsive)
                PRatio = self.aircraft.powertrain.Hybrid(
                    self.aircraft.mission.profile.SuppliedPowerRatio(t),
                    self.profile.Altitude(t),
                    self.profile.Velocity(t),
                    Ppropulsive
                    )

                # if self.aircraft.mission.profile.SuppliedPowerRatio(t) > 0.:
                    # print(self.aircraft.mission.profile.SuppliedPowerRatio(t))
                    # print(self.profile.Velocity(t))
                    # print(Ppropulsive)
                dEFdt = Ppropulsive * PRatio[0]
                dEBatdt = Ppropulsive * PRatio[5]

                dbetadt = - dEFdt/(self.ef*self.WTO)  
                return [dEFdt,dEBatdt,dbetadt]

            # Takeoff / OEI-climb worst case (see _worst_case_propulsive_power)
            Ppropulsive = self._worst_case_propulsive_power(self.WTO)

            PRatio = self.aircraft.powertrain.Hybrid(self.aircraft.mission.profile.SPW[0][0],self.aircraft.constraint.TakeOffConstraints['Altitude'],self.aircraft.constraint.TakeOffConstraints['Speed'],Ppropulsive)
            self.TO_PBat = Ppropulsive * PRatio[5]
            self.TO_PP = Ppropulsive * PRatio[1]  

            #set/reset max values
            self.Max_PBat = -1
            self.Max_PEng = -1

            y0 = [0,0,self.beta0]
            
            rtol = 1e-5
            atol = 1e-7
            method= 'BDF'

            # integrate all phases together
            # sol = integrate.solve_ivp(model,[0, self.profile.MissionTime2],y0,method='BDF',rtol=1e-6)
            # print(sol)

            # integrate sequentially
            self.integral_solution = []
            times = np.append(self.profile.Breaks,self.profile.MissionTime2)
            for i in range(len(times)-1):
                sol = integrate.solve_ivp(model,[times[i], times[i+1]],y0,method=method,rtol=rtol, dense_output=True)
                self.integral_solution.append(sol) 
                y0 = [sol.y[0][-1],sol.y[1][-1],sol.y[2][-1]]
                if times[i+1] == self.aircraft.mission.profile.BreaksDescent:
                    self.Ef_mission = sol.y[0][-1]
    
            self.Ef = sol.y[0]
            self.EBat = sol.y[1]
            self.Beta = sol.y[2]
    
            self.Ef_diversion = self.Ef[-1] - self.Ef_mission

            # compute peak Propulsive power along mission
            times = []
            beta = []
            for array in self.integral_solution:
                times = np.concatenate([times, array.t])
                beta = np.concatenate([beta, array.y[2]])

            self.MissionTimes = times 
            
            PP = np.array([WTO * self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,beta[i],self.profile.PowerExcess(times[i]),1,self.profile.Altitude(times[i]),self.DISA,self.profile.Velocity(times[i]),'TAS') for i in range(len(times))])
            PRatio = np.array([self.aircraft.powertrain.Hybrid(self.aircraft.mission.profile.SuppliedPowerRatio(times[i]),self.profile.Altitude(times[i]),self.profile.Velocity(times[i]),PP[i]) for i in range(len(times))] )

            self.Max_PEng = np.max(np.multiply(PP,PRatio[:,1]))
            self.Max_PEng_alt = self.profile.Altitude(times[np.argmax(np.multiply(PP,PRatio[:,1]))]) #altitude at which peak power occurs 

            self.Max_PBat = np.max(np.multiply(PP,PRatio[:,5]))

            return self.Ef[-1], self.EBat[-1]


    def SerialRangeExtenderConfiguration(self, WTO):
        """Serial hybrid flown as a **range extender**: the gas turbine runs at a constant shaft
        power (``'GT Rated Power'``) for the whole mission while the battery buffers the mismatch
        with the propulsive demand — discharging when demand exceeds the turbine output and
        **recharging** (from the turbine surplus) when it is lower.

        Because the turbine is decoupled from the propeller it stays at its rated load, so its
        Class-II efficiency is read at that (near-design) shaft power and only the altitude/velocity
        lapse moves it — the part-load penalty a propeller-coupled (parallel) turbine pays at low
        demand is avoided. The battery is sized for the *swing* of its state of charge (the buffer
        capacity) rather than a one-way discharge.

        State vector ``y = [E_fuel_chem, E_batt_removed, Beta]`` (battery energy removed is signed:
        positive when discharging, negative when the surplus recharges it). Returns
        ``(fuel chemical energy [J], battery buffer capacity [J])``.
        """
        self.WTO = WTO
        pt = self.aircraft.powertrain
        import PhlyGreen.Utilities.Units as Units
        from PhlyGreen.Systems.Powertrain.gas_turbine_surrogate import _isa_pressure_ratio
        P_gt_rated = float(self.aircraft.EnergyInput['GT Rated Power'])   # sea-level rated shaft power [W]
        # The turbine is sized (for its efficiency map) by 'GT Design Power'; default it to the
        # rated power so the range-extender turbine runs at ~full load (its sweet spot).
        gt_design = self.aircraft.EnergyInput.get('GT Design Power') or P_gt_rated
        eta_charge = self.aircraft.EnergyInput.get('Battery Charge Efficiency', 1.0) or 1.0

        def gt_shaft_power(alt):
            """Turbine shaft power at full throttle: the rated power lapsed for altitude (ISA),
            i.e. only the altitude lapse reduces it (the turbine is otherwise always at full power)."""
            available = gt_design * _isa_pressure_ratio(Units.mToft(alt))
            return min(P_gt_rated, available)

        def PowerPropulsive(Beta, t):
            return WTO * self.aircraft.performance.PoWTO(
                self.aircraft.DesignWTOoS, Beta, self.profile.PowerExcess(t), 1,
                self.profile.Altitude(t), self.DISA, self.profile.Velocity(t), 'TAS')

        def flows(t, Beta):
            """Fuel chemical power and battery terminal power at one instant.

            Forward serial chain (turbine -> generator -> bus + battery -> motor -> gearbox ->
            propeller); the battery makes up the difference between the bus demand and the
            generator output. ``Pbat > 0`` discharging, ``Pbat < 0`` recharging.
            """
            alt, vel = self.profile.Altitude(t), self.profile.Velocity(t)
            P_prop = PowerPropulsive(Beta, t)
            self.check_PP(P_prop)
            P_gt = gt_shaft_power(alt)                                 # full throttle, lapsed
            eta_pp = pt.eta('propeller', alt, vel, P_prop)
            eta_gb = pt.eta('gearbox', alt, vel, P_prop)
            eta_pm = pt.eta('pmad', alt, vel, P_prop)
            eta_gt = pt.eta('gas_turbine', alt, vel, P_gt)            # at the delivered shaft load
            Pe1 = P_prop / (eta_pp * eta_gb * pt.EtaEM2)              # electrical bus -> motor
            Ps1 = P_gt * pt.EtaEM1                                     # generator electrical output
            Pbat = Pe1 / eta_pm - Ps1                                 # battery into the bus combiner
            Pf = P_gt / eta_gt                                        # fuel chemical power
            return Pf, Pbat

        def model(t, y):
            Pf, Pbat = flows(t, y[2])
            dErem = Pbat if Pbat > 0 else Pbat * eta_charge          # recharge pays a charge loss
            return [Pf, dErem, -Pf / (self.ef * self.WTO)]

        # Off-mission worst case (take-off / OEI): turbine still at rated, battery covers the rest.
        P_total_TO = self._worst_case_propulsive_power(WTO)
        to = self.aircraft.constraint.TakeOffConstraints
        alt_TO, vel_TO = to['Altitude'], to['Speed']
        eta_pp = pt.eta('propeller', alt_TO, vel_TO, P_total_TO)
        eta_gb = pt.eta('gearbox', alt_TO, vel_TO, P_total_TO)
        eta_pm = pt.eta('pmad', alt_TO, vel_TO, P_total_TO)
        P_gt_TO = gt_shaft_power(alt_TO)
        Pbat_TO = (P_total_TO / (eta_pp * eta_gb * pt.EtaEM2)) / eta_pm - P_gt_TO * pt.EtaEM1
        self.TO_PP = P_gt_TO
        self.TO_PBat = max(Pbat_TO, 0.0)

        # Integrate sequentially over the profile breakpoints.
        y0 = [0.0, 0.0, self.beta0]
        self.integral_solution = []
        times = np.append(self.profile.Breaks, self.profile.MissionTime2)
        self.Ef_mission = None
        for i in range(len(times) - 1):
            sol = integrate.solve_ivp(model, [times[i], times[i + 1]], y0,
                                      method='BDF', rtol=1e-5, dense_output=True)
            self.integral_solution.append(sol)
            y0 = [sol.y[0][-1], sol.y[1][-1], sol.y[2][-1]]
            if times[i + 1] == self.profile.BreaksDescent:
                self.Ef_mission = sol.y[0][-1]

        self.Ef = sol.y[0]
        self.Beta = sol.y[2]
        if self.Ef_mission is None:
            self.Ef_mission = self.Ef[-1]
        self.Ef_diversion = self.Ef[-1] - self.Ef_mission

        # Battery state-of-charge swing (the buffer capacity it must hold) and peak powers.
        t_all = np.concatenate([a.t for a in self.integral_solution])
        erem_all = np.concatenate([a.y[1] for a in self.integral_solution])
        beta_all = np.concatenate([a.y[2] for a in self.integral_solution])
        self.MissionTimes = t_all
        self.EBat = erem_all                                          # signed cumulative (for plots)
        swing = float(erem_all.max() - erem_all.min())               # usable buffer energy [J]
        pbat_all = np.array([flows(t_all[k], beta_all[k])[1] for k in range(len(t_all))])
        self.Max_PBat = max(float(pbat_all.max()) if len(pbat_all) else 0.0, self.TO_PBat)
        self.Max_PEng = P_gt_rated                                    # turbine sized for its rated power
        self.Max_PEng_alt = 0.0
        return self.Ef[-1], swing



    def HybridConfigurationClassII(self,WTO):
        """
        Evaluate the mission for a Hybrid-Electric aircraft using a Class II battery model.

        Class II battery:
            - Enforces current, voltage, SOC, and thermal constraints.
            - Requires P-number sizing (battery discretization).
            - Mission evaluation is repeatedly performed until a feasible P-number
              (battery size) is found.

        Outputs:
            - Fuel energy (Ef)
            - Battery energy (EBat)
            - Peak thermal and electric power
            - Updated optimal P-number

        Parameters
        ----------
        WTO : float
            Takeoff weight [kg].

        Returns
        -------
        tuple
            (final cumulative fuel energy [J], final cumulative battery energy [J])

        Notes
        -----
        The algorithm:
            1. Uses a P-number guess (or previous optimal).
            2. Scales P-number based on weight from previous iteration (if available).
            3. Evaluates mission for that P-number:
                - battery thermal model
                - battery electrochemical model
                - SOC/voltage/current limits
            4. If infeasible, P-number is adjusted using a bounded search.
            5. Continues until a feasible P-number is found.    
        """
 
        self.WTO = WTO

        def PowerPropulsive(Beta,t):
            PPoWTO = self.aircraft.performance.PoWTO(
                self.aircraft.DesignWTOoS,
                Beta,
                self.profile.PowerExcess(t),
                1,
                self.profile.Altitude(t),
                self.DISA,
                self.profile.Velocity(t),
                'TAS'
                )
          
            return PPoWTO * WTO

        def model(t, y):
            """
            Governing ODEs. State vector:
            y[0] = Ef     (fuel energy)
            y[1] = EBat   (battery energy)
            y[2] = Beta   (mass fraction)
            y[3] = it     (Ampere-seconds, i.e. charge throughput)
            y[4] = T      (battery temperature, K)

            Return RHS dy/dt = [dEFdt, dEdt_bat, dbetadt, i, dTdt] 
        """
            # aircraft mass fraction
            Beta = y[2]
            Ppropulsive = PowerPropulsive(Beta, t)
            # takes in all the mission segments and finds the required power ratio for the current time of the mission
            PRatio = self.aircraft.powertrain.Hybrid(
                self.aircraft.mission.profile.SuppliedPowerRatio(t),
                self.profile.Altitude(t),
                self.profile.Velocity(t),
                Ppropulsive,
            )
            dEFdt = Ppropulsive * PRatio[0]  # fuel power output
            dbetadt = -dEFdt / (self.ef * self.WTO)  # change in mass due to fuel consumption
            PElectric = Ppropulsive * PRatio[5]  # propulsive power required for the electric motors

            # Finds the battery state for the requested power. The battery class raises an
            # exception if any of its parameters exceed the allowed limits or there are
            # unphysical values. This is taken as a sign that the P number is invalid. The
            # exception may be caught into a global variable so that the last constraint
            # driving the battery sizing may be printed to the user. Temperature limits
            # are not validated because T depends on the cooling sizing, not the P number.

            # assign a temperature, battery class validates temp
            self.aircraft.battery.T = y[4]
            self.aircraft.battery.phi = self.aircraft.mission.profile.SuppliedPowerRatio(t) 

            # assign spent charge, battery validates SOC
            self.aircraft.battery.it = y[3] / 3600

            # assign current, also validated here by the class
            self.aircraft.battery.i = self.aircraft.battery.Power_2_current(PElectric)

            # calculate power, this causes Vout to be generated and validated
            dEdt_bat = self.aircraft.battery.i * self.aircraft.battery.Vout

            alt = self.profile.Altitude(t)
            Mach = Speed.TAS2Mach(self.profile.Velocity(t), alt, DISA=self.DISA)
            Tamb = ISA.atmosphere.T0std(alt, Mach)
            rho = ISA.atmosphere.RHO0std(alt, Mach, self.DISA)

            dTdt, _ = self.aircraft.battery.heatLoss(Tamb, rho)

            if self.aircraft.mission.profile.SuppliedPowerRatio(t) > 0.:
                if y[4] < 273.15 + self.aircraft.mission.T_battery_limit: 
                    dTdt = max(dTdt,0.)
                else:
                    dTdt = 0.
            else:
                dTdt = min(dTdt,0)


            # print('Altitude: ', alt)
            # print('Time: ', t)
            # print('dTdt: ', dTdt)
            # print([dEFdt, dEdt_bat, dbetadt, self.aircraft.battery.i, dTdt])

            return [dEFdt, dEdt_bat, dbetadt, self.aircraft.battery.i, dTdt]

        def evaluate_mission_given_P(P_number):
            """
            Evaluate the full mission for a given battery discretization P-number.

            Returns
            -------
            bool, int or None
                (True, None) if feasible
                (False, error_code) if battery constraint failed
            """
            # print(f"evaluating pnumber {P_number}")
            self.P_n_arr.append(P_number)
            # no maths needed to know nothing will work without a battery
            if P_number == 0:
                # print(f"{P_number} is False")
                return False

            self.aircraft.battery.Configure(P_number)

            # Takeoff condition, calculated before anything else as
            # it does not depend on the battery size, just the aircraft.
            # Takeoff / OEI-climb worst case (see _worst_case_propulsive_power)
            Ppropulsive_TO = self._worst_case_propulsive_power(self.WTO)


            # hybrid power ratio for takeoff
            PRatio = self.aircraft.powertrain.Hybrid(
                self.aircraft.mission.profile.SPW[0][0],
                self.aircraft.constraint.TakeOffConstraints["Altitude"],
                self.aircraft.constraint.TakeOffConstraints["Speed"],
                Ppropulsive_TO,
            )

            self.TO_PP = Ppropulsive_TO * PRatio[1]  # combustion engine power during takeoff
            self.TO_PBat = Ppropulsive_TO * PRatio[5]  # electric motor power during takeoff

            try:
                # print(f"P num during try: {P_number}")
                self.aircraft.battery.T = self.startT + 273.15 # battery T TODO FIX THIS
                self.aircraft.battery.it = 0
                self.aircraft.battery.i = self.aircraft.battery.Power_2_current(
                    self.TO_PBat
                )  # convert output power to volts and amps
                self.aircraft.battery.Vout  # necessary statement for the battery class to validate Vout
            except BatteryError as err:
                # print(f"P num at error: {P_number}")
                if not self.size_battery_pack: print(err)
                # print(f"{P_number} is False")
                return False, err.code
            except Exception as err:
                print(f"Unexpected error: {err}")
                raise

            # integrate the rest of the flight sequentially
            np.seterr(over="raise")
            times = np.append(self.profile.Breaks, self.profile.MissionTime2)
            rtol = 1e-6
            method = "BDF"
            self.integral_solution = []
            self.plottingVars = []
            # initial fuel energy, battery energy, mass fraction, spent charge, and battery T
            y0 = [0, 0, self.beta0, 0, self.startT + 273.15]
            for i in range(len(times) - 1):
                try:
                    sol = integrate.solve_ivp(
                        model, [times[i], times[i + 1]], y0, method=method, rtol=rtol
                    )
                    self.integral_solution.append(sol)
                except BatteryError as err:
                    # print(f"P num at error: {self.aircraft.battery.P_number}")
                    if not self.size_battery_pack: print(err)
                    # print(f"{P_number} is False")
                    return False, err.code
                except Exception as e:
                    print(f"Unexpected error:\n{e}")
                    raise

                # The solution given by solve ivp isnt actually valid for all cases when you
                # try it on every point. This is because of the tolerance that it allows itself.
                # It will accurately solve the problem for the time it was given but if you
                # actually try to calculate the outputs at every time point, some of them cause
                # the model to fail. To avoid having to use a super small rtol to make the
                # time step of the integration smaller and therefore taking forever to
                # integrate, the better solution is to simply ignore any battery errors that
                # the model throws during plotting of the full flight profile. Its already
                # been validated in the integration, whatever deviations happen at this
                # stage are minuscule errors of fractions of percent
                for k in range(len(sol.t) - 0):
                    try:
                        yy0 = [sol.y[0][k], sol.y[1][k], sol.y[2][k], sol.y[3][k], sol.y[4][k]]
                        model(sol.t[k], yy0)
                        alt = self.profile.Altitude(sol.t[k])
                        Mach = Speed.TAS2Mach(self.profile.Velocity(sol.t[k]), alt, DISA=self.DISA)
                        Tamb = ISA.atmosphere.T0std(alt, Mach)
                        self.plottingVars.append(
                            [
                                sol.t[k],
                                self.aircraft.battery.SOC,
                                self.aircraft.battery.Voc,
                                self.aircraft.battery.Vout,
                                self.aircraft.battery.i,
                                self.aircraft.battery.T,
                                Tamb,
                                alt,
                                self.aircraft.battery.mdot,
                            ],
                        )
                    except BatteryError:
                        # Print warning and just keep saving the data, this sometimes happens if rtol is too loose
                        print(
                            "WARNING: evaluate_P_number integration rtol may be too loose, consider lowering it"
                        )
                self.Ef = sol.y[0]
                self.EBat = sol.y[1]
                self.Beta = sol.y[2]
                y0 = [sol.y[0][-1], sol.y[1][-1], sol.y[2][-1], sol.y[3][-1], sol.y[4][-1]]
            # print(f"{P_number} is True")
            return True, None

        def find_P_nr(n_guess, wto_ratio,bypass=True):
            """
            Find the feasible P-number using a bounded search (bisection-like).
            Efficient and robust for large battery discretizations.

            Returns
            -------
            int
                Optimal feasible P-number.
            """
            # Flags used to prevent double checking the boundaries
            nmin_is_bounded = False
            nmax_is_bounded = False
            if not bypass: # for debugging
                if wto_ratio is not None:
                    n = round(n_guess * wto_ratio)
                    # check that the value below the initial guess is invalid
                    if not evaluate_mission_given_P(n - 1)[0]:
                        n_min = n - 1
                        if evaluate_mission_given_P(n)[0]:  # check that the guess is valid
                            # print(f"max={n} and min={n_min}")
                            # print(f"Optimal n {n}")
                            return n  # Optimal found
                        else:
                            n_min = n  # if the guess is invalid, its the new minimum
                            n_max = max(n_min + 1, math.ceil((n_guess + 1) * wto_ratio))
                            # nmin is a known invalid value, no need to reevaluate it
                            nmin_is_bounded = True
                    else:
                        n_max = n - 1
                        n_min = min(n_max - 1, math.floor((n_guess - 1) * wto_ratio))
                        # nmax is a known valid value, no need to reevaluate it
                        nmax_is_bounded = True

                else:  # If its the first iteration theres no prev weight to scale off of yet
                    n_max = n_guess
                    n_min = math.floor(n_max / 2)
            else:
                if wto_ratio is not None:
                    n_max = math.ceil(n_guess*wto_ratio)
                    n_min = n_max-1
                else:
                    n_max = n_guess
                    n_min = math.floor(n_max / 2)

            # If its the weight scaling fails (or is the first iteration), boundaries
            # need to be calculated with the doubling and halving method

            # lower the min p number until it is invalid
            if not nmin_is_bounded:
                while evaluate_mission_given_P(n_min)[0]:
                    n_max = n_min  # if the n_min guess is too large it can be the new n_max to save iterations since it has already been tried
                    n_min = math.floor(n_min / 2)  # halve n_min until it fails
                    nmax_is_bounded = True  # nmax is set to a known valid value and does not need to be reevaluated

            # raise the max p number until its valid
            if not nmax_is_bounded:
                while not evaluate_mission_given_P(n_max)[0]:
                    n_min = n_max  # if the nmax guess is too small it can be the new nmin to save iterations since it has already been tried
                    n_max = n_max * 2  # double n_max until it works

            # start from the middle
            n = math.ceil((n_max + n_min) / 2)

            # find optimal P number using bisection search
            optimal = False
            while not optimal:
                valid_result = evaluate_mission_given_P(n)[0]

                if valid_result and (n - n_min) == 1:
                    optimal = True

                elif valid_result:  # n is too big
                    n_max = n
                    n = math.floor((n_max + n_min) / 2)

                else:  # n is too small
                    n_min = n
                    n = math.ceil((n_max + n_min) / 2)


            print(f"max={n_max} and min={n_min}")
            print(f"Optimal n {n}")
            return n


        if self.size_battery_pack:
            if self.last_weight is None:
                ratio = None
            else:
                ratio = self.WTO / self.last_weight

            if self.optimal_n is None:
                P_n_guess = 128  # Hardcoded first guess
            else:
                P_n_guess = self.optimal_n


            self.optimal_n = find_P_nr(P_n_guess, ratio, bypass=True)  # algorithm D
            # alg = "D"
            # if alg == "D":
            #     self.optimal_n = find_P_nr(P_n_guess, ratio, bypass=False)  # algorithm D
            # if alg == "C":
            #     self.optimal_n = find_P_nr(P_n_guess, ratio)  # algorithm C
            # if alg == "B":
            #     self.optimal_n = find_P_nr(P_n_guess, 1)  # algorithm B
            # if alg == "A":
            #     self.optimal_n = find_P_nr(128, None) # algorithm A



            # save weight across iterations
            self.last_weight = self.WTO

            # Save history for performance profiling
            self.Past_P_n.append(self.P_n_arr)
            self.P_n_arr = []
        
        else:
            success, code = evaluate_mission_given_P(self.aircraft.battery.P_number) 
            if not success:
                return 0, code


        # compute peak Propulsive power along mission
        times = []
        beta = []
        it_arr = []
        T_arr = []
        for array in self.integral_solution:
            times = np.concatenate([times, array.t])
            beta = np.concatenate([beta, array.y[2]])
            it_arr = np.concatenate([it_arr, array.y[3]])
            T_arr = np.concatenate([T_arr, array.y[4]])

        self.MissionTimes = times

        PP = np.array([WTO * self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,beta[i],self.profile.PowerExcess(times[i]),1,self.profile.Altitude(times[i]),self.DISA,self.profile.Velocity(times[i]),'TAS') for i in range(len(times))])
        PRatio = np.array([self.aircraft.powertrain.Hybrid(self.aircraft.mission.profile.SuppliedPowerRatio(times[i]),self.profile.Altitude(times[i]),self.profile.Velocity(times[i]),PP[i]) for i in range(len(times))] )
        self.Max_PEng = np.max(np.multiply(PP,PRatio[:,1]))
        self.Max_PEng_alt = self.profile.Altitude(times[np.argmax(np.multiply(PP,PRatio[:,1]))]) #altitude at which peak power occurs
        self.Max_PBat = np.max(np.multiply(PP,PRatio[:,5]))

        # Peak battery heat the thermal-management system actually has to reject, for TMS
        # sizing. With the bang-bang thermostat the cooling only acts when the pack is held at
        # its maximum operating temperature (T = ceiling, dT/dt = 0); below the ceiling the
        # heat is absorbed adiabatically by the thermal mass and nothing is rejected. So we
        # take the peak generated heat *only over the points clamped at the ceiling* (reusing
        # the propulsive-power split computed above). If the pack never reaches the ceiling,
        # no cooling is required and the TMS heat is zero.
        ceiling = 273.15 + self.T_battery_limit
        b = self.aircraft.battery
        q_pack_peak = 0.0
        for i in range(len(times)):
            if T_arr[i] < ceiling - 0.5:        # cooling is active only at the ceiling
                continue
            try:
                b.T = T_arr[i]
                b.it = it_arr[i] / 3600
                b.i = b.Power_2_current(PP[i] * PRatio[i, 5])
                alt = self.profile.Altitude(times[i])
                Mach = Speed.TAS2Mach(self.profile.Velocity(times[i]), alt, DISA=self.DISA)
                Tamb = ISA.atmosphere.T0std(alt, Mach)
                rho = ISA.atmosphere.RHO0std(alt, Mach, self.DISA)
                _, q_cell = b.heatLoss(Tamb, rho)
                q_pack_peak = max(q_pack_peak, q_cell * b.cells_total)
            except Exception:
                continue
        self.Max_Bat_Thermal_Pwr = q_pack_peak

        return self.Ef[-1], self.EBat[-1]