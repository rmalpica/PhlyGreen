import numpy as np
import numbers
import math
import warnings
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed
import PhlyGreen.Utilities.Units as Units
import scipy.integrate as integrate
from .Profile import Profile
from PhlyGreen.Systems.Battery.Battery import BatteryError, find_parallel_cells

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
        # Ground segments (not in the flown profile): taxi-out + take-off before the climb,
        # taxi-in after landing. Defaults: ICAO Annex 16 LTO reference times (take-off 0.7 min
        # at 100 % power; 26 min of taxi/ground idle at 7 %, split equally out/in).
        self.taxi_out_time = 13.0          # [min]
        self.taxi_in_time = 13.0           # [min]
        self.taxi_power_fraction = 0.07    # [-] of the take-off propulsive power
        self.takeoff_time = 0.7            # [min]
        self.takeoff_power_fraction = 1.0  # [-] of the take-off propulsive power, over takeoff_time
        # Battery fraction of the propulsive power on the ground. The take-off split is the
        # 'Takeoff' stage phi of the mission profile; the taxi split defaults to it.
        self.taxi_phi = None               # [-] None = the take-off phi
        self.E_ground = 0.0                # fuel chemical energy of the ground segments [J]
        self.E_taxi_out_takeoff = 0.0      # ... of which before the climb [J]
        self.EBat_ground = 0.0             # battery energy of the ground segments [J]
        self.EBat_taxi_out_takeoff = 0.0   # ... of which before the climb [J]
        self.Taxi_PBat = 0.0               # battery power while taxiing [W]
        self.Takeoff_PBat = 0.0            # battery power over the take-off run [W]
        self._ground_battery_legs_out = [] # Class-II pack legs before the climb
        self._ground_battery_legs_in = []  # ... and after landing
        self.DISA = 0
        self.WTO = None
        self.Max_PBat = -1
        self.Max_PEng = -1
        self.Max_PEng_alt = 0
        self.TO_PBat = 0
        self.TO_PP = 0
        # Hybrid electric machines: peak motor shaft power and peak bus (motor input) power,
        # over the mission and at take-off/OEI. They size the serial hybrid's motor and PMAD.
        self.Max_PMotor = 0.0
        self.TO_PMotor = 0.0
        self.Max_PBus = 0.0
        self.TO_PBus = 0.0
        # Sizing-critical mission thrust and the condition it occurs at (for a Turbofan,
        # the largest thrust/lapse -- see TraditionalConfiguration).
        self.Max_Thrust = -1.0
        self.Max_Thrust_alt = 0.0
        self.Max_Thrust_mach = 0.0
        self.TO_Thrust = 0.0
        self.TO_Thrust_mach = 0.0
        # peak in-flight battery waste heat [W] (Class-II battery), for TMS sizing
        self.Max_Bat_Thermal_Pwr = -1.0
        # hydrogen fuel-cell mission tracking
        self.Max_FC_Thermal_Pwr = 0.0
        self.Max_FC_Thermal_Pwr_alt = 0.0
        self.Max_FC_Thermal_Pwr_V = 0.0
        # hydrogen chemical power [W] (HHV basis) of the stack at the take-off/OEI power
        self.TO_P_H2_Thermal = 0.0
        # fuel-cell heat [W] at the worst-case take-off/OEI power (not flown by the profile)
        self.TO_FC_Thermal_Pwr = 0.0
        # Fuel-cell heat-load points for the thermal-management system: the take-off point
        # plus the peak of every flown segment, each a dict {name, Q_fc [W], altitude [m],
        # V_inf [m/s TAS], mdot_h2 [kg/s]}. Filled by the fuel-cell configurations.
        self.thermal_profile = []
        # The same quantities at every accepted integration point of the flown mission
        # (name '<phase>/<segment> t=<s>', plus the time 't' [s]), for the continuous check
        # of the TMS hardware.
        self.thermal_history = []
        self._phase_peak = None
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
        # Class-II pack state after the taxi-in of the last feasible flight: (spent charge
        # [A s], cell temperature [K]). Read by Battery.thermal_degradation_analysis.
        self.battery_end_state = None

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

        mi = self.aircraft.MissionInput
        if 'Beta start' in mi:
            warnings.warn("MissionInput 'Beta start' is ignored: the mass at the start of the "
                          "climb now follows from the computed taxi-out + take-off fuel "
                          "('Taxi Out Time', 'Taxi In Time', 'Taxi Power Fraction', "
                          "'Takeoff Time').", DeprecationWarning, stacklevel=2)
        self.taxi_out_time = mi.get('Taxi Out Time', 13.0)
        self.taxi_in_time = mi.get('Taxi In Time', 13.0)
        self.taxi_power_fraction = mi.get('Taxi Power Fraction', 0.07)
        self.takeoff_time = mi.get('Takeoff Time', 0.7)
        self.takeoff_power_fraction = mi.get('Takeoff Power Fraction', 1.0)
        self.taxi_phi = mi.get('Taxi Supplied Power Ratio', None)
        # ISA temperature deviation [K] of the flown mission (flight performance, fuel-cell
        # ambient state, TMS ram air). The constraint diagram uses ConstraintsInput['DISA'].
        self.DISA = mi.get('DISA', 0.0)
        if self.taxi_phi and not self._has_battery():
            raise ValueError(
                "'Taxi Supplied Power Ratio' is %g, but the %s configuration has no battery."
                % (self.taxi_phi, self.aircraft.Configuration))
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
            The fuel and battery energies include the ground segments (taxi-out, take-off,
            taxi-in), see :meth:`_ground_segments`.
        """
        
        # Ground segments first: they set the mass fraction at the start of the climb.
        self._ground_segments(WTO)
        result = self._fly_configuration(WTO)
        if self._has_battery() and not (isinstance(result, tuple) and result[0] == 0):
            self.Max_PBat = max(self.Max_PBat, self.Takeoff_PBat, self.Taxi_PBat)
        return self._add_ground_energy(result)

    def _fly_configuration(self, WTO):
        """Fly the profile with the configuration's mission method."""
        if self.aircraft.Configuration in ('Traditional', 'Turbofan'):
            # A turbofan is traditional_graph with unit gearbox and fan nodes -- the whole
            # fuel -> thrust-power chain sits in the single overall-efficiency node -- so it
            # flies the same integration. What differs is the sizing quantity: thrust, not
            # shaft power, which TraditionalConfiguration tracks alongside.
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

    # --- ground segments: taxi-out, take-off, taxi-in ------------------------------------

    def _has_battery(self):
        """True for the configurations that carry a battery."""
        return self.aircraft.Configuration in ('Hybrid', 'FuelCellBattery')

    def _is_range_extender(self):
        """True for a Serial hybrid flown as a range extender (see
        :meth:`SerialRangeExtenderConfiguration`)."""
        return (self.aircraft.Configuration == 'Hybrid'
                and self.aircraft.HybridType == 'Serial'
                and bool(self.aircraft.EnergyInput.get('GT Rated Power')))

    def _takeoff_phi(self):
        """Battery fraction of the propulsive power at take-off: the phi of the profile's
        'Takeoff' stage (0 without a battery)."""
        if not self._has_battery() or getattr(self.profile, 'SPW', None) is None:
            return 0.0
        return float(self.profile.SPW[0][0])

    def _taxi_phi(self):
        """Battery fraction of the propulsive power while taxiing ('Taxi Supplied Power
        Ratio'; defaults to the take-off phi)."""
        if not self._has_battery():
            return 0.0
        return self._takeoff_phi() if self.taxi_phi is None else float(self.taxi_phi)

    def _fc_battery_eta_elec(self, alt, vel, P):
        """Battery terminal -> propulsive (thrust) power efficiency of the fuel-cell + battery
        architecture: PMAD, electric motor, gearbox and propeller, the same chain the fuel-cell
        branch uses in ``FuelCell.ComputePRatio``. ``P`` is the battery propulsive power. The
        electric-motor term varies with the operating point when the Class-II ('Smart') d-q
        motor model is selected; the propeller term when a propeller model is attached."""
        fc = self.aircraft.fuelcell
        pt = self.aircraft.powertrain
        if self.aircraft.EnergyInput.get('Eta Electric Motor Model') == 'Smart':
            em = pt.eta('electric_motor', alt, vel, P)
        else:
            em = fc.EtaEM
        if hasattr(pt, 'Propeller'):
            eta_prop = pt.Propeller.ComputePropEfficiency(alt, vel, P)
        else:
            eta_prop = fc.EtaProp
        return em * fc.EtaPM * fc.EtaGB * eta_prop

    def _fc_battery_terminal_power(self, alt, vel, P_bat):
        """Battery terminal power [W] for the battery propulsive power ``P_bat`` [W] of the
        fuel-cell + battery architecture (0 when the battery is idle)."""
        return P_bat / self._fc_battery_eta_elec(alt, vel, P_bat) if P_bat > 0 else 0.0

    def _fuel_cell_chemical_power(self, alt, vel, P_fc):
        """Hydrogen chemical power [W] (HHV basis) of the running fuel cell when it delivers
        the propulsive power ``P_fc`` >= 0: the hydrogen flow of the stack, which also feeds
        the air system, the fixed auxiliaries and the TMS pump, so it is not zero at zero
        propulsive power."""
        fc = self.aircraft.fuelcell
        fc.ComputePRatio(alt, vel, P_fc)
        return fc.mdot_h2 * fc.HHV_H2

    def _track_fc_heat_on_solution(self, sol, beta_row, fc_power):
        """Record the fuel-cell heat at the accepted points of one segment solution ``sol``
        (not at the trial evaluations of the integrator). ``fc_power(t, Beta)`` returns the
        fuel-cell propulsive power, or None when the fuel cell is off."""
        fc = self.aircraft.fuelcell
        for t, beta in zip(sol.t, sol.y[beta_row]):
            P_fc = fc_power(t, beta)
            if P_fc is None:
                continue
            alt, vel = self.profile.Altitude(t), self.profile.Velocity(t)
            fc.ComputePRatio(alt, vel, P_fc)
            self._track_fc_heat(t, alt, vel)

    def _range_extender_gt_power(self, alt):
        """Range-extender turbine shaft power at full throttle: the rated power, lapsed for
        altitude (ISA)."""
        import PhlyGreen.Utilities.Units as Units
        from PhlyGreen.Systems.Powertrain.gas_turbine_surrogate import _isa_pressure_ratio
        P_gt_rated = float(self.aircraft.EnergyInput['GT Rated Power'])
        gt_design = self.aircraft.EnergyInput.get('GT Design Power') or P_gt_rated
        return min(P_gt_rated, gt_design * _isa_pressure_ratio(Units.mToft(alt)))

    def _serial_motor_shaft_power(self, P_prop, alt, vel):
        """Shaft power [W] of the serial hybrid's electric motor for the propulsive power
        ``P_prop``: the motor drives the propeller through the gearbox."""
        pt = self.aircraft.powertrain
        return P_prop / (pt.eta('propeller', alt, vel, P_prop) * pt.eta('gearbox', alt, vel, P_prop))

    def _range_extender_flows(self, P_prop, alt, vel):
        """Fuel chemical power and battery terminal power of the range extender at one point.

        Forward serial chain (turbine -> generator -> bus + battery -> motor -> gearbox ->
        propeller); the turbine runs at full throttle and the battery makes up the difference
        between the bus demand and the generator output. ``Pbat > 0`` discharging,
        ``Pbat < 0`` recharging.
        """
        pt = self.aircraft.powertrain
        P_gt = self._range_extender_gt_power(alt)
        eta_pp = pt.eta('propeller', alt, vel, P_prop)
        eta_gb = pt.eta('gearbox', alt, vel, P_prop)
        eta_pm = pt.eta('pmad', alt, vel, P_prop)
        eta_gt = pt.eta('gas_turbine', alt, vel, P_gt)
        Pe1 = P_prop / (eta_pp * eta_gb * pt.EtaEM2)             # electrical bus -> motor
        Ps1 = P_gt * pt.EtaEM1                                    # generator electrical output
        return P_gt / eta_gt, Pe1 / eta_pm - Ps1

    def _ground_condition(self):
        """Altitude [m] and TAS [m/s] at which the ground segments are evaluated: the
        take-off constraint condition."""
        to = self.aircraft.constraint.TakeOffConstraints
        perf = self.aircraft.performance
        perf.set_speed(to['Altitude'], to['Speed'], to['Speed Type'], self.aircraft.constraint.DISA)
        return to['Altitude'], float(perf.TAS)

    def _ground_power_split(self, P, phi, takeoff=False):
        """Split the ground propulsive power ``P`` [W] between the energy sources, through
        the configuration's own powertrain at the take-off condition (so part-load
        efficiencies apply).

        ``phi`` is the battery fraction of ``P``. The range extender ignores it at take-off:
        its turbine runs at full throttle and the battery covers the rest, the rule that sizes
        it for take-off (see :meth:`SerialRangeExtenderConfiguration`).

        Returns ``(fuel chemical power, battery terminal power, battery sizing power)`` [W].
        The sizing power is in the convention of ``Max_PBat``: the battery terminal power
        (the range extender counts only discharge).
        """
        if P <= 0:
            return 0.0, 0.0, 0.0
        alt, vel = self._ground_condition()
        cfg = self.aircraft.Configuration
        if cfg in ('Traditional', 'Turbofan'):
            return P * self.aircraft.powertrain.Traditional(alt, vel, P)[0], 0.0, 0.0
        if cfg == 'Hybrid':
            if takeoff and self._is_range_extender():
                Pf, Pbat = self._range_extender_flows(P, alt, vel)
                return Pf, Pbat, max(Pbat, 0.0)
            PRatio = self.aircraft.powertrain.Hybrid(phi, alt, vel, P)
            return P * PRatio[0], P * PRatio[5], P * PRatio[5]
        if cfg in ('Hydrogen', 'FuelCellBattery'):
            P_bat = phi * P if cfg == 'FuelCellBattery' else 0.0
            fuel_cell_on = cfg == 'Hydrogen' or phi < 1.0
            Pf = self._fuel_cell_chemical_power(alt, vel, P - P_bat) if fuel_cell_on else 0.0
            P_el = self._fc_battery_terminal_power(alt, vel, P_bat)
            return Pf, P_el, P_el
        raise Exception("Unknown aircraft configuration: %s" % cfg)

    def _ground_segments(self, WTO):
        """Fuel and battery energy of the ground segments, which the flown profile does not
        include.

        Take-off at ``takeoff_power_fraction`` of the take-off-field propulsive power for
        ``takeoff_time``; taxi-out and taxi-in at ``taxi_power_fraction`` of it (defaults:
        ICAO LTO cycle). The battery supplies the take-off phi (the profile's 'Takeoff' stage)
        of the take-off power and ``taxi_phi`` of the taxi power; the rest comes from the
        primary fuel.

        The taxi-out and take-off fuel is burnt before the climb, so the mission starts at
        ``beta0 = 1 - m_(taxi-out + take-off) / WTO``. The ground fuel and battery energy are
        added to the mission energies (:meth:`_add_ground_energy`), and the taxi / take-off
        battery powers to the battery peak power. A Class-II pack is flown through the same
        legs, so the climb starts from the pack state after taxi-out and take-off, and taxi-in
        must fit in what is left after landing.
        """
        P_TO = self._takeoff_power(WTO)
        P_takeoff = self.takeoff_power_fraction * P_TO
        P_taxi = self.taxi_power_fraction * P_TO
        phi_takeoff, phi_taxi = self._takeoff_phi(), self._taxi_phi()
        Pf_to, Pel_to, Pbat_to = self._ground_power_split(P_takeoff, phi_takeoff, takeoff=True)
        Pf_tx, Pel_tx, Pbat_tx = self._ground_power_split(P_taxi, phi_taxi)

        t_to, t_out, t_in = (60.0 * self.takeoff_time, 60.0 * self.taxi_out_time,
                             60.0 * self.taxi_in_time)
        E_out = t_to * Pf_to + t_out * Pf_tx
        E_in = t_in * Pf_tx
        self.E_taxi_out_takeoff = E_out
        self.E_ground = E_out + E_in
        self.beta0 = 1.0 - E_out / (self.ef * WTO)

        self.EBat_taxi_out_takeoff = t_to * Pel_to + t_out * Pel_tx
        self.EBat_ground = self.EBat_taxi_out_takeoff + t_in * Pel_tx
        self.Takeoff_PBat = Pbat_to
        self.Taxi_PBat = Pbat_tx
        # (name, duration [s], battery terminal power [W], phi, speed [m/s TAS] for the
        # ambient cooling of a Class-II pack)
        _, vel = self._ground_condition()
        self._ground_battery_legs_out = [('Taxi-out', t_out, Pel_tx, phi_taxi, 0.0),
                                         ('Takeoff', t_to, Pel_to, phi_takeoff, vel)]
        self._ground_battery_legs_in = [('Taxi-in', t_in, Pel_tx, phi_taxi, 0.0)]

    def _add_ground_energy(self, result):
        """Add the ground-segment energies to what a mission method returns: a float (fuel
        energy) or a tuple ``(fuel energy, battery energy)``. ``(0, code)`` signals a failed
        Class-II battery mission and is passed through. The range extender returns its
        battery buffer swing, which already includes the ground legs."""
        if isinstance(result, tuple):
            if result[0] == 0:
                return result
            fuel = result[0] + self.E_ground
            if len(result) > 1 and not self._is_range_extender():
                return (fuel, result[1] + self.EBat_ground) + tuple(result[2:])
            return (fuel,) + tuple(result[1:])
        return result + self.E_ground

    def _pack_through_ground_legs(self, legs, it, T):
        """Fly a Class-II pack through ground legs at constant terminal power.

        ``it`` is the spent charge [A s] and ``T`` the pack temperature [K] at the start;
        returns them at the end. Uses the in-flight thermal logic (heats up to the
        temperature ceiling while discharging, cools otherwise) with the ambient air at the
        take-off altitude. A leg without battery power leaves the pack state unchanged.
        Raises ``BatteryError`` if the pack cannot supply a leg.
        """
        b = self.aircraft.battery
        alt = self.aircraft.constraint.TakeOffConstraints['Altitude']
        ceiling = 273.15 + self.T_battery_limit
        for _name, dt, P_el, phi, vel in legs:
            if dt <= 0 or P_el <= 0:
                continue
            Mach = Speed.TAS2Mach(vel, alt, DISA=self.DISA)
            Tamb = ISA.atmosphere.T0std(alt, Mach)
            rho = ISA.atmosphere.RHO0std(alt, Mach, self.DISA)

            def rhs(t, y, P_el=P_el, phi=phi, Tamb=Tamb, rho=rho):
                b.T = y[1]
                b.phi = phi
                b.it = y[0] / 3600
                b.i = b.Power_2_current(P_el)
                b.Vout                                   # validates the terminal voltage
                dTdt, _ = b.heatLoss(Tamb, rho)
                if phi > 0.:
                    dTdt = max(dTdt, 0.) if y[1] < ceiling else 0.
                else:
                    dTdt = min(dTdt, 0.)
                return [b.i, dTdt]

            sol = integrate.solve_ivp(rhs, [0.0, dt], [it, T], method='BDF', rtol=1e-6)
            it, T = float(sol.y[0][-1]), float(sol.y[1][-1])
        return it, T

    def _pack_before_climb(self, P_el_takeoff_check):
        """Class-II pack state at the start of the climb: taxi-out, then a check that the pack
        can deliver the worst-case take-off/OEI terminal power ``P_el_takeoff_check``, then
        the take-off run. Starts full at ``startT``. Returns ``(it [A s], T [K])``; raises
        ``BatteryError`` if the pack cannot do it."""
        b = self.aircraft.battery
        legs = self._ground_battery_legs_out
        it, T = self._pack_through_ground_legs(legs[:1], 0.0, self.startT + 273.15)
        b.T = T
        b.it = it / 3600
        b.i = b.Power_2_current(P_el_takeoff_check)
        b.Vout                                           # validates the terminal voltage
        return self._pack_through_ground_legs(legs[1:], it, T)


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

    def _worst_case_thrust(self, WTO):
        """Worst-case off-mission thrust [N] and the Mach it occurs at.

        The thrust-rated counterpart of :meth:`_worst_case_propulsive_power`. Each case is
        converted from power to thrust at the speed that case is flown at, then compared --
        take-off and OEI climb are separate flight conditions and a shared speed cannot be
        assumed.
        """
        c = self.aircraft.constraint
        cases = []
        for power, spec in ((self._takeoff_power(WTO), c.TakeOffConstraints),
                            (self._oei_climb_power(WTO), c.OEIClimbConstraints)):
            if not spec:
                continue
            self.aircraft.performance.set_speed(
                spec['Altitude'], spec['Speed'], spec['Speed Type'], c.DISA)
            cases.append((power / self.aircraft.performance.TAS,
                          self.aircraft.performance.Mach))
        if not cases:
            return 0.0, 0.0
        return max(cases, key=lambda tm: tm[0])


    # --- fuel-cell heat tracking (thermal-management sizing) ----------------------------

    def _takeoff_fc_heat(self, P_fc_TO):
        """Fly the fuel cell at the take-off/OEI propulsive power ``P_fc_TO`` (at the take-off
        constraint conditions) and start the thermal profile with that point.

        Stores the heat (``TO_FC_Thermal_Pwr``) and the hydrogen chemical power of the stack,
        ``mdot_h2 * HHV`` (``TO_P_H2_Thermal``), at that point. Resets the mission heat peak.
        """
        c = self.aircraft.constraint
        to = c.TakeOffConstraints
        perf = self.aircraft.performance
        perf.set_speed(to['Altitude'], to['Speed'], to['Speed Type'], c.DISA)
        V_TO = float(perf.TAS)
        fc = self.aircraft.fuelcell
        self.Max_FC_Thermal_Pwr = -1.0
        self.thermal_history = []
        if P_fc_TO <= 0:                  # battery-only take-off: no fuel-cell heat there
            self.TO_FC_Thermal_Pwr = 0.0
            self.TO_P_H2_Thermal = 0.0
            self.thermal_profile = []
            return
        fc.ComputePRatio(to['Altitude'], V_TO, P_fc_TO)
        self.TO_FC_Thermal_Pwr = fc.Q_thermal
        self.TO_P_H2_Thermal = fc.mdot_h2 * fc.HHV_H2
        self.thermal_profile = [{'name': 'Takeoff', 'Q_fc': fc.Q_thermal,
                                 'altitude': to['Altitude'], 'V_inf': V_TO,
                                 'mdot_h2': fc.mdot_h2, 'takeoff': True}]
        self.Max_FC_Thermal_Pwr_alt = 0.0
        self.Max_FC_Thermal_Pwr_V = 0.0

    def _begin_thermal_phase(self, i):
        """Start tracking the fuel-cell heat peak of segment ``i`` of the profile."""
        seg = self.profile._segments[i]
        self._phase_peak = {'name': f"{seg.phase}/{seg.name}", 'Q_fc': -1.0, 'altitude': 0.0,
                            'V_inf': 0.0, 'mdot_h2': 0.0,
                            't_start': seg.start_time, 't_end': seg.end_time}

    def _end_thermal_phase(self):
        """Append the peak of the segment just flown to ``thermal_profile``."""
        ph = self._phase_peak
        if ph is not None and ph['Q_fc'] > 0:
            self.thermal_profile.append({k: ph[k] for k in
                                         ('name', 'Q_fc', 'altitude', 'V_inf', 'mdot_h2')})
        self._phase_peak = None

    def _track_fc_heat(self, t, alt, vel):
        """Record the fuel-cell heat of the last ``ComputePRatio`` call at time ``t``: the
        mission peak and the peak of the current segment (the segment's end instant is left
        to the next segment, which starts there)."""
        fc = self.aircraft.fuelcell
        q = fc.Q_thermal
        if q > self.Max_FC_Thermal_Pwr:
            self.Max_FC_Thermal_Pwr = q
            self.Max_FC_Thermal_Pwr_alt = alt
            self.Max_FC_Thermal_Pwr_V = vel
        ph = self._phase_peak
        if ph is not None and ph['t_start'] <= t < ph['t_end'] and q > ph['Q_fc']:
            ph.update(Q_fc=q, altitude=float(alt), V_inf=float(vel), mdot_h2=fc.mdot_h2)
        segment = ph['name'] if ph is not None else 'mission'
        self.thermal_history.append({'name': f"{segment} t={float(t):.0f}s", 'Q_fc': q,
                                     'altitude': float(alt), 'V_inf': float(vel),
                                     'mdot_h2': fc.mdot_h2, 't': float(t)})

    def HydrogenConfiguration(self, WTO):
        """Evaluate the full mission for a hydrogen fuel-cell (electric) propulsion system.

        Integrates two states over the mission: cumulative hydrogen *chemical* energy and
        the mass fraction Beta. At each instant the fuel cell converts the required
        propulsive shaft power into a hydrogen chemical-power demand, the stack hydrogen flow
        times the HHV (``_fuel_cell_chemical_power``). Tracks the
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
            PP = self.check_PP(PowerPropulsive(Beta, t))
            dEdt_chem = self._fuel_cell_chemical_power(           # hydrogen chemical power [W]
                self.profile.Altitude(t), self.profile.Velocity(t), PP)
            dbetadt = - dEdt_chem / (self.ef * self.WTO)
            return [dEdt_chem, dbetadt]

        # Worst-case off-mission propulsive power for fuel-cell sizing: the take-off field
        # length and the one-engine-inoperative climb, evaluated at the *constraint* conditions
        # (these scenarios are not flown by the mission profile, but the fuel cell must supply
        # their power). Taken as the worst case.
        self.TO_PP = self._worst_case_propulsive_power(WTO)
        self._takeoff_fc_heat(self.TO_PP)

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
            self._begin_thermal_phase(i)
            sol = integrate.solve_ivp(model, [times[i], times[i + 1]], y0,
                                      method='BDF', rtol=1e-5, max_step=60.0)
            self._track_fc_heat_on_solution(
                sol, 1, lambda t, b: self.check_PP(PowerPropulsive(b, t)))
            self._end_thermal_phase()
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
        def fuel_cell_power(t, Beta):
            """Fuel-cell propulsive power, or None when the battery supplies all of it (fuel
            cell off)."""
            phi = float(self.profile.SuppliedPowerRatio(t))
            if phi >= 1.0:
                return None
            return fuel_cell_share(t, self.check_PP(PowerPropulsive(Beta, t)))

        def model(t, y):
            P_fc = fuel_cell_power(t, y[1])
            dEh2 = 0.0
            if P_fc is not None:
                dEh2 = self._fuel_cell_chemical_power(
                    self.profile.Altitude(t), self.profile.Velocity(t), P_fc)
            dbetadt = - dEh2 / (self.ef * self.WTO)
            return [dEh2, dbetadt]

        # Worst-case off-mission propulsive power (take-off field length / OEI climb) at the
        # constraint conditions, split between the fuel cell and the battery by the take-off phi.
        P_total_TO = self._worst_case_propulsive_power(WTO)
        phi_TO = self._takeoff_phi()
        to_alt, to_vel = self._ground_condition()
        self.TO_PP = (1.0 - phi_TO) * P_total_TO    # fuel-cell propulsive share at take-off/OEI
        self.TO_PBat = self._fc_battery_terminal_power(   # battery terminal power at take-off/OEI
            to_alt, to_vel, phi_TO * P_total_TO)
        self._takeoff_fc_heat(self.TO_PP)

        y0 = [0.0, self.beta0]
        self.integral_solution = []
        times = np.append(self.profile.Breaks, self.profile.MissionTime2)
        for i in range(len(times) - 1):
            self._begin_thermal_phase(i)
            sol = integrate.solve_ivp(model, [times[i], times[i + 1]], y0,
                                      method='BDF', rtol=1e-5, max_step=60.0)
            self._track_fc_heat_on_solution(sol, 1, fuel_cell_power)
            self._end_thermal_phase()
            self.integral_solution.append(sol)
            y0 = [sol.y[0][-1], sol.y[1][-1]]

        self.Ef = sol.y[0]
        self.Beta = sol.y[1]

        # Post-process the battery: electrical energy drawn and peak battery terminal power.
        E_bat = 0.0
        pp_fc_peak, p_el_peak = 0.0, 0.0
        for arr in self.integral_solution:
            pp = np.array([self.check_PP(PowerPropulsive(b, t)) for t, b in zip(arr.t, arr.y[1])])
            p_bat = np.array([float(self.profile.SuppliedPowerRatio(t)) for t in arr.t]) * pp
            p_fc = pp - p_bat
            p_el = np.array([self._fc_battery_terminal_power(
                self.profile.Altitude(t), self.profile.Velocity(t), pb)
                for t, pb in zip(arr.t, p_bat)])
            if len(arr.t) > 1:
                E_bat += float(np.trapezoid(p_el, arr.t))
            p_el_peak = max(p_el_peak, float(p_el.max()) if len(p_el) else 0.0)
            pp_fc_peak = max(pp_fc_peak, float(p_fc.max()) if len(p_fc) else 0.0)
        self.EBat = E_bat
        self.Max_PEng = pp_fc_peak           # fuel-cell propulsive peak (no hidden margin)
        self.Max_PEng_alt = 0.0
        self.Max_PBat = max(p_el_peak, self.TO_PBat)
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

            # fuel-cell (hydrogen) branch — the fuel cell supplies (1 - phi) of the power and is
            # off when the battery supplies all of it
            dEh2 = 0.0
            if phi < 1.0:
                dEh2 = self._fuel_cell_chemical_power(alt, vel, (1.0 - phi) * PP)
            dbetadt = - dEh2 / (self.ef * self.WTO)             # only hydrogen burn changes mass

            # battery branch — Class-II cell model. The pack must deliver phi*PP of shaft power,
            # i.e. phi*PP/eta_elec of electrical power at its terminals.
            PElectric = self._fc_battery_terminal_power(alt, vel, phi * PP)
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
        phi_TO = self._takeoff_phi()
        to_alt, to_vel = self._ground_condition()
        self.TO_PP = (1.0 - phi_TO) * P_total_TO            # fuel-cell propulsive share at TO/OEI
        self.TO_PBat = self._fc_battery_terminal_power(     # battery terminal power at TO/OEI
            to_alt, to_vel, phi_TO * P_total_TO)

        def fuel_cell_power(t, Beta):
            """Fuel-cell propulsive power, or None when the fuel cell is off (phi = 1)."""
            phi = float(self.profile.SuppliedPowerRatio(t))
            if phi >= 1.0:
                return None
            return (1.0 - phi) * self.check_PP(PowerPropulsive(Beta, t))

        def evaluate_mission_given_P(P_number):
            """Fly the whole mission for a given parallel-cell count; (feasible, error_code)."""
            self.P_n_arr.append(P_number)
            if P_number == 0:
                return False, None
            self.aircraft.battery.Configure(P_number)
            # Taxi-out, take-off/OEI power feasibility and take-off run: the pack state at the
            # start of the climb.
            try:
                it0, T0 = self._pack_before_climb(self.TO_PBat)
            except BatteryError as err:
                if not self.size_battery_pack:
                    print(err)
                return False, err.code

            np.seterr(over="raise")
            times = np.append(self.profile.Breaks, self.profile.MissionTime2)
            self.integral_solution = []
            self._takeoff_fc_heat(self.TO_PP)
            y0 = [0, 0, self.beta0, it0, T0]
            for i in range(len(times) - 1):
                try:
                    self._begin_thermal_phase(i)
                    sol = integrate.solve_ivp(model, [times[i], times[i + 1]], y0,
                                              method="BDF", rtol=1e-6)
                    self._track_fc_heat_on_solution(sol, 2, fuel_cell_power)
                    self._end_thermal_phase()
                    self.integral_solution.append(sol)
                except BatteryError as err:
                    self._phase_peak = None
                    if not self.size_battery_pack:
                        print(err)
                    return False, err.code
                self.Ef = sol.y[0]
                self.EBat = sol.y[1]
                self.Beta = sol.y[2]
                y0 = [sol.y[0][-1], sol.y[1][-1], sol.y[2][-1], sol.y[3][-1], sol.y[4][-1]]
            # taxi-in after landing must fit in what is left of the pack
            try:
                self.battery_end_state = self._pack_through_ground_legs(
                    self._ground_battery_legs_in, y0[3], y0[4])
            except BatteryError as err:
                if not self.size_battery_pack:
                    print(err)
                return False, err.code
            return True, None

        def find_P_nr(n_guess, wto_ratio):
            """Minimal feasible parallel-cell count (see Battery.find_parallel_cells); the
            pack may not be heavier than the aircraft."""
            b = self.aircraft.battery
            n_limit = math.floor(self.WTO / (b.cell_mass * b.S_number))
            return find_parallel_cells(evaluate_mission_given_P, n_guess, wto_ratio, n_limit)

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

        # Peak fuel-cell propulsive power, peak battery terminal power and the battery TMS heat
        # over the sized mission.
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
        PP = np.maximum(PP, 0.0)
        phis = np.array([float(self.profile.SuppliedPowerRatio(times[i])) for i in range(len(times))])
        p_fc, p_bat = (1.0 - phis) * PP, phis * PP
        p_el = np.array([self._fc_battery_terminal_power(
            self.profile.Altitude(times[i]), self.profile.Velocity(times[i]), p_bat[i])
            for i in range(len(times))])
        self.Max_PEng = float(np.max(p_fc)) if len(p_fc) else 0.0
        self.Max_PEng_alt = self.profile.Altitude(times[int(np.argmax(p_fc))]) if len(p_fc) else 0.0
        self.Max_PBat = max(float(np.max(p_el)) if len(p_el) else 0.0, self.TO_PBat)

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
                b.i = b.Power_2_current(p_el[i])
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
            PP = self.check_PP(PowerPropulsive(Beta,t))
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

        to_alt, to_vel = self._ground_condition()      # take-off altitude and TAS
        PRatio = self.aircraft.powertrain.Traditional(to_alt, to_vel, Ppropulsive)
        self.TO_PP = Ppropulsive * PRatio[1] #shaft power 

        # Off-mission thrust requirement. Each case is converted at *its own* speed: the
        # take-off and OEI-climb conditions need not be flown at the same speed, and thrust
        # is power/speed, so converting the worse power at the other case's speed would be
        # wrong. Evaluated at flight speed, never at a standstill -- propulsive power is
        # thrust x speed, so a static point carries no thrust information at all.
        self.TO_Thrust, self.TO_Thrust_mach = self._worst_case_thrust(WTO)

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

        # Peak THRUST over the mission. A thrust-rated engine cannot be sized from a peak
        # shaft power, and the two peaks need not even coincide: thrust is PP/V, so a
        # high-power point flown fast can demand less thrust than a slower one.
        # Recorded for every configuration (it is cheap, and informative for a turboprop too).
        velocities = np.array([self.profile.Velocity(t) for t in times])
        altitudes = np.array([self.profile.Altitude(t) for t in times])
        thrust = np.array(PP) / velocities

        if self.aircraft.Configuration == 'Turbofan':
            # Size on the worst demand *referred back to sea level*, not on the largest raw
            # thrust. Available thrust lapses with altitude and Mach, so the point that
            # stresses the engine hardest is the one with the largest thrust/lapse -- often
            # top of climb rather than the peak-thrust point low down.
            machs = velocities / np.array(
                [Speed.soundspeed(a, self.DISA) for a in altitudes])
            lapse = np.array([self.aircraft.powertrain.ThrustLapse(a, m, self.DISA)
                              for a, m in zip(altitudes, machs)])
            i_peak = int(np.argmax(thrust / lapse))
            self.Max_Thrust_mach = float(machs[i_peak])
        else:
            i_peak = int(np.argmax(thrust))
            self.Max_Thrust_mach = float(
                velocities[i_peak] / Speed.soundspeed(float(altitudes[i_peak]), self.DISA))

        self.Max_Thrust = float(thrust[i_peak])
        self.Max_Thrust_alt = float(altitudes[i_peak])

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
                Ppropulsive = self.check_PP(PowerPropulsive(Beta,t))
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

            to_alt, to_vel = self._ground_condition()      # take-off altitude and TAS
            PRatio = self.aircraft.powertrain.Hybrid(self._takeoff_phi(), to_alt, to_vel, Ppropulsive)
            self.TO_PBat = Ppropulsive * PRatio[5]
            self.TO_PMotor = Ppropulsive * PRatio[2]     # electric-motor shaft power
            self.TO_PBus = Ppropulsive * PRatio[4]       # electric power into the motor
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
            self.Max_PMotor = np.max(np.multiply(PP,PRatio[:,2]))
            self.Max_PBus = np.max(np.multiply(PP,PRatio[:,4]))

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
        P_gt_rated = float(self.aircraft.EnergyInput['GT Rated Power'])   # sea-level rated shaft power [W]
        eta_charge = self.aircraft.EnergyInput.get('Battery Charge Efficiency', 1.0) or 1.0

        def PowerPropulsive(Beta, t):
            return WTO * self.aircraft.performance.PoWTO(
                self.aircraft.DesignWTOoS, Beta, self.profile.PowerExcess(t), 1,
                self.profile.Altitude(t), self.DISA, self.profile.Velocity(t), 'TAS')

        def flows(t, Beta):
            """Fuel chemical power and battery terminal power at one instant (see
            :meth:`_range_extender_flows`)."""
            P_prop = self.check_PP(PowerPropulsive(Beta, t))
            return self._range_extender_flows(P_prop, self.profile.Altitude(t),
                                              self.profile.Velocity(t))

        def model(t, y):
            Pf, Pbat = flows(t, y[2])
            dErem = Pbat if Pbat > 0 else Pbat * eta_charge          # recharge pays a charge loss
            return [Pf, dErem, -Pf / (self.ef * self.WTO)]

        # Off-mission worst case (take-off / OEI): turbine still at rated, battery covers the rest.
        P_total_TO = self._worst_case_propulsive_power(WTO)
        alt_TO, vel_TO = self._ground_condition()      # take-off altitude and TAS
        Pbat_TO = self._range_extender_flows(P_total_TO, alt_TO, vel_TO)[1]
        self.TO_PMotor = self._serial_motor_shaft_power(P_total_TO, alt_TO, vel_TO)
        self.TO_PBus = self.TO_PMotor / pt.EtaEM2
        self.TO_PP = self._range_extender_gt_power(alt_TO)
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
        # Battery energy removed along the ground legs: taxi-out and take-off before the
        # climb, taxi-in after landing (constant power, so the extremes are the leg ends).
        def removed(P_el, dt):
            return P_el * dt if P_el > 0 else P_el * eta_charge * dt
        (_, dt_out, P_out, _, _), (_, dt_to, P_to, _, _) = self._ground_battery_legs_out
        (_, dt_in, P_in, _, _), = self._ground_battery_legs_in
        e_out = removed(P_out, dt_out)
        e_climb = e_out + removed(P_to, dt_to)                       # at the start of the climb
        e_end = e_climb + float(erem_all[-1]) + removed(P_in, dt_in)
        levels = np.concatenate([[0.0, e_out], e_climb + erem_all, [e_end]])
        swing = float(levels.max() - levels.min())                   # usable buffer energy [J]
        pbat_all = np.array([flows(t_all[k], beta_all[k])[1] for k in range(len(t_all))])
        self.Max_PBat = max(float(pbat_all.max()) if len(pbat_all) else 0.0, self.TO_PBat)
        p_motor = np.array([self._serial_motor_shaft_power(
            self.check_PP(PowerPropulsive(beta_all[k], t_all[k])),
            self.profile.Altitude(t_all[k]), self.profile.Velocity(t_all[k]))
            for k in range(len(t_all))])
        self.Max_PMotor = float(p_motor.max()) if len(p_motor) else 0.0
        self.Max_PBus = self.Max_PMotor / pt.EtaEM2
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
            Ppropulsive = self.check_PP(PowerPropulsive(Beta, t))
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
                return False, None

            self.aircraft.battery.Configure(P_number)

            # Takeoff condition, calculated before anything else as
            # it does not depend on the battery size, just the aircraft.
            # Takeoff / OEI-climb worst case (see _worst_case_propulsive_power)
            Ppropulsive_TO = self._worst_case_propulsive_power(self.WTO)


            # hybrid power ratio for takeoff
            to_alt, to_vel = self._ground_condition()      # take-off altitude and TAS
            PRatio = self.aircraft.powertrain.Hybrid(
                self._takeoff_phi(), to_alt, to_vel, Ppropulsive_TO)

            self.TO_PP = Ppropulsive_TO * PRatio[1]  # combustion engine power during takeoff
            self.TO_PBat = Ppropulsive_TO * PRatio[5]  # battery power during takeoff
            self.TO_PMotor = Ppropulsive_TO * PRatio[2]  # electric-motor shaft power
            self.TO_PBus = Ppropulsive_TO * PRatio[4]    # electric power into the motor

            try:
                # Taxi-out, take-off/OEI power feasibility and take-off run: the pack state
                # (spent charge, temperature) at the start of the climb.
                it0, T0 = self._pack_before_climb(self.TO_PBat)
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
            y0 = [0, 0, self.beta0, it0, T0]
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
            # taxi-in after landing must fit in what is left of the pack
            try:
                self.battery_end_state = self._pack_through_ground_legs(
                    self._ground_battery_legs_in, y0[3], y0[4])
            except BatteryError as err:
                if not self.size_battery_pack: print(err)
                return False, err.code
            return True, None

        def find_P_nr(n_guess, wto_ratio):
            """Smallest feasible P-number (see Battery.find_parallel_cells). The search may not
            go beyond the pack that is as heavy as the aircraft."""
            b = self.aircraft.battery
            n_limit = math.floor(self.WTO / (b.cell_mass * b.S_number))
            n = find_parallel_cells(evaluate_mission_given_P, n_guess, wto_ratio, n_limit)
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


            self.optimal_n = find_P_nr(P_n_guess, ratio)



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
        self.Max_PMotor = np.max(np.multiply(PP,PRatio[:,2]))
        self.Max_PBus = np.max(np.multiply(PP,PRatio[:,4]))

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