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
            if self.aircraft.battery.BatteryClass == 'II':
                return self.HybridConfigurationClassII(WTO)
            elif self.aircraft.battery.BatteryClass == 'I':
                return self.HybridConfigurationClassI(WTO)

        elif self.aircraft.Configuration == 'Hydrogen':
            return self.HydrogenConfiguration(WTO)

        elif self.aircraft.Configuration == 'FuelCellBattery':
            return self.FuelCellBatteryConfiguration(WTO)

        else:
            raise Exception("Unknown aircraft configuration: %s" %self.aircraft.Configuration)
        
  
  
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

        # Peak (take-off / one-engine-inoperative climb) propulsive power, used to size
        # the fuel-cell rated power and the take-off operating point.
        P_TO = WTO * self.aircraft.performance.TakeOff(
            self.aircraft.DesignWTOoS, self.aircraft.constraint.TakeOffConstraints['Beta'],
            self.aircraft.constraint.TakeOffConstraints['Altitude'],
            self.aircraft.constraint.TakeOffConstraints['kTO'],
            self.aircraft.constraint.TakeOffConstraints['sTO'], self.aircraft.constraint.DISA,
            self.aircraft.constraint.TakeOffConstraints['Speed'],
            self.aircraft.constraint.TakeOffConstraints['Speed Type'])
        PRatio_TO = self.aircraft.fuelcell.ComputePRatio(
            self.aircraft.constraint.TakeOffConstraints['Altitude'],
            self.aircraft.constraint.TakeOffConstraints['Speed'], P_TO)
        self.TO_PP = P_TO
        self.TO_P_H2_Thermal = P_TO * PRatio_TO[0]
        self.Max_FC_Thermal_Pwr = -1.0

        # Optionally advance the LH2 tank thermodynamic state through the mission.
        track = self.track_tank and getattr(self.aircraft, 'tank', None) is not None
        if track:
            tank = self.aircraft.tank
            tank.m_curr = tank.capacity_single        # start full
            tank.P_curr = tank.P_min
            tank.history = {'t': [], 'P': [], 'm_tot': [], 'Vent': [], 'Q_in': [],
                            'Alt': [], 'Q_heater': [], 'm_vent_cum': []}
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

        # Peak mission shaft power (with a small installation margin), for FC mass sizing.
        pp_peak = 0.0
        for arr in self.integral_solution:
            for k in range(len(arr.t)):
                pp_peak = max(pp_peak, PowerPropulsive(arr.y[1][k], arr.t[k]))
        self.Max_PEng = pp_peak / 0.8
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
        eta_elec = fc.EtaEM * fc.EtaPM * fc.EtaGB   # battery electrical -> shaft

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

        P_TO = WTO * self.aircraft.performance.TakeOff(
            self.aircraft.DesignWTOoS, self.aircraft.constraint.TakeOffConstraints['Beta'],
            self.aircraft.constraint.TakeOffConstraints['Altitude'],
            self.aircraft.constraint.TakeOffConstraints['kTO'],
            self.aircraft.constraint.TakeOffConstraints['sTO'], self.aircraft.constraint.DISA,
            self.aircraft.constraint.TakeOffConstraints['Speed'],
            self.aircraft.constraint.TakeOffConstraints['Speed Type'])
        phi_TO = float(self.profile.SPW[0][0]) if self.profile.SPW is not None else 0.0
        self.TO_PP = (1.0 - phi_TO) * P_TO          # fuel-cell shaft power at take-off
        self.TO_PBat = phi_TO * P_TO                # battery shaft power at take-off
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
                E_bat += float(np.trapezoid(p_bat / eta_elec, arr.t))
            pp_bat_peak = max(pp_bat_peak, float(p_bat.max()) if len(p_bat) else 0.0)
            pp_fc_peak = max(pp_fc_peak, float(p_fc.max()) if len(p_fc) else 0.0)
        self.EBat = E_bat
        self.Max_PEng = pp_fc_peak / 0.8
        self.Max_PEng_alt = 0.0
        self.Max_PBat = max(pp_bat_peak, self.TO_PBat)
        return self.Ef[-1], self.EBat


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

        # Takeoff condition
        Ppropulsive = self.WTO * self.aircraft.performance.TakeOff(
            self.aircraft.DesignWTOoS,
            self.aircraft.constraint.TakeOffConstraints['Beta'], 
            self.aircraft.constraint.TakeOffConstraints['Altitude'], 
            self.aircraft.constraint.TakeOffConstraints['kTO'], 
            self.aircraft.constraint.TakeOffConstraints['sTO'], 
            self.aircraft.constraint.DISA, 
            self.aircraft.constraint.TakeOffConstraints['Speed'], 
            self.aircraft.constraint.TakeOffConstraints['Speed Type'])

        # Takeoff One Engine Inop condition 
        PpropulsiveOEI = self.WTO * self.aircraft.performance.OEIClimb(
            self.aircraft.DesignWTOoS, 
            self.aircraft.constraint.OEIClimbConstraints['Beta'], 
            self.aircraft.constraint.OEIClimbConstraints['Speed'] * self.aircraft.constraint.OEIClimbConstraints['Climb Gradient'], 
            1., 
            self.aircraft.constraint.OEIClimbConstraints['Altitude'], 
            self.aircraft.constraint.DISA, 
            self.aircraft.constraint.OEIClimbConstraints['Speed'], 
            self.aircraft.constraint.OEIClimbConstraints['Speed Type'])
        
        Ppropulsive = max(Ppropulsive,PpropulsiveOEI) #consider worst case

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

            # Takeoff condition
            Ppropulsive = self.WTO * self.aircraft.performance.TakeOff(
                self.aircraft.DesignWTOoS,
                self.aircraft.constraint.TakeOffConstraints['Beta'], 
                self.aircraft.constraint.TakeOffConstraints['Altitude'], 
                self.aircraft.constraint.TakeOffConstraints['kTO'], 
                self.aircraft.constraint.TakeOffConstraints['sTO'], 
                self.aircraft.constraint.DISA, 
                self.aircraft.constraint.TakeOffConstraints['Speed'], 
                self.aircraft.constraint.TakeOffConstraints['Speed Type'])
            
            # Takeoff One Engine Inop condition 
            PpropulsiveOEI = self.WTO * self.aircraft.performance.OEIClimb(
                self.aircraft.DesignWTOoS, 
                self.aircraft.constraint.OEIClimbConstraints['Beta'], 
                self.aircraft.constraint.OEIClimbConstraints['Speed'] * self.aircraft.constraint.OEIClimbConstraints['Climb Gradient'], 
                1., 
                self.aircraft.constraint.OEIClimbConstraints['Altitude'], 
                self.aircraft.constraint.DISA, 
                self.aircraft.constraint.OEIClimbConstraints['Speed'], 
                self.aircraft.constraint.OEIClimbConstraints['Speed Type'])
            
            Ppropulsive = max(Ppropulsive,PpropulsiveOEI) #consider worst case

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
            # it does not depend on the battery size, just the aircraft
            # calculates the total propulsive power required for takeoff
            Ppropulsive_TO = self.WTO * self.aircraft.performance.TakeOff(
                self.aircraft.DesignWTOoS,
                self.aircraft.constraint.TakeOffConstraints["Beta"],
                self.aircraft.constraint.TakeOffConstraints["Altitude"],
                self.aircraft.constraint.TakeOffConstraints["kTO"],
                self.aircraft.constraint.TakeOffConstraints["sTO"],
                self.aircraft.constraint.DISA,
                self.aircraft.constraint.TakeOffConstraints["Speed"],
                self.aircraft.constraint.TakeOffConstraints["Speed Type"],
            )

            PpropulsiveOEI = self.WTO * self.aircraft.performance.OEIClimb(
                self.aircraft.DesignWTOoS, 
                self.aircraft.constraint.OEIClimbConstraints['Beta'], 
                self.aircraft.constraint.OEIClimbConstraints['Speed'] * self.aircraft.constraint.OEIClimbConstraints['Climb Gradient'], 
                1., 
                self.aircraft.constraint.OEIClimbConstraints['Altitude'], 
                self.aircraft.constraint.DISA, self.aircraft.constraint.OEIClimbConstraints['Speed'], 
                self.aircraft.constraint.OEIClimbConstraints['Speed Type'])
            
            Ppropulsive_TO = max(Ppropulsive_TO,PpropulsiveOEI) 


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