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
    """ Properties """

    @property
    def beta0(self):
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
        if PP < 0:
            warnings.warn(". Setting Propulsive power to 0.", RuntimeWarning)
            PP = 0
        return PP


    def SetInput(self):

        self.beta0 = self.aircraft.MissionInput['Beta start']
        self.ef = self.aircraft.EnergyInput['Ef']

    def InitializeProfile(self):
        
        self.profile = Profile(self.aircraft)
        
        self.profile.DefineMission()
        
        self.t = np.linspace(0,self.profile.MissionTime2,num=1000)


    def EvaluateMission(self,WTO):
        
        if self.aircraft.Configuration == 'Traditional':     
            return self.TraditionalConfiguration(WTO)
            
        elif self.aircraft.Configuration == 'Hybrid':    
            if self.aircraft.battery.BatteryClass == 'II': 
                return self.HybridConfigurationClassII(WTO)
            elif self.aircraft.battery.BatteryClass == 'I': 
                return self.HybridConfigurationClassI(WTO)

        else:
            raise Exception("Unknown aircraft configuration: %s" %self.aircraft.Configuration)
        
  
  
    def TraditionalConfiguration(self,WTO):
 
        self.WTO = WTO
        
        
        def PowerPropulsive(Beta,t):

            PPoWTO = self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,Beta,self.profile.PowerExcess(t),1,self.profile.Altitude(t),self.DISA,self.profile.Velocity(t),'TAS')

            return PPoWTO * WTO

        
        def model(t,y):
            Beta = y[1]
            PP = PowerPropulsive(Beta,t)
            self.check_PP(PP)
            PRatio = self.aircraft.powertrain.Traditional(self.profile.Altitude(t),self.profile.Velocity(t),PP)
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

        PRatio = self.aircraft.powertrain.Traditional(self.aircraft.constraint.TakeOffConstraints['Altitude'],self.aircraft.constraint.TakeOffConstraints['Speed'],Ppropulsive)
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

    

        PP = [WTO * self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,beta[i],self.profile.PowerExcess(times[i]),1,self.profile.Altitude(times[i]),self.DISA,self.profile.Velocity(times[i]),'TAS') for i in range(len(times))]
        PRatio = np.array([self.aircraft.powertrain.Traditional(self.profile.Altitude(times[i]),self.profile.Velocity(times[i]),PP[i]) for i in range(len(times))] )
        self.Max_PEng = np.max(np.multiply(PP,PRatio[:,1])) #shaft power
        self.Max_PEng_alt = self.profile.Altitude(times[np.argmax(np.multiply(PP,PRatio[:,1]))]) #altitude at which peak power occurs 

        return self.Ef[-1]
    
    
    def HybridConfigurationClassI(self,WTO):
            
            self.WTO = WTO
            
            def PowerPropulsive(Beta,t):

                PPoWTO = self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,Beta,self.profile.PowerExcess(t),1,self.profile.Altitude(t),self.DISA,self.profile.Velocity(t),'TAS')
            
                return PPoWTO * WTO

            
            def model(t,y):
                
                Beta = y[2]
                Ppropulsive = PowerPropulsive(Beta,t)
                self.check_PP(Ppropulsive)
                PRatio = self.aircraft.powertrain.Hybrid(self.aircraft.mission.profile.SuppliedPowerRatio(t),self.profile.Altitude(t),self.profile.Velocity(t),Ppropulsive)

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
 
        self.WTO = WTO

        def PowerPropulsive(Beta,t):
            PPoWTO = self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,Beta,self.profile.PowerExcess(t),1,self.profile.Altitude(t),self.DISA,self.profile.Velocity(t),'TAS')
          
            return PPoWTO * WTO

        def model(t, y):
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

        def evaluate_P_nr(P_number):
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
                # print(err)
                # print(f"{P_number} is False")
                return False
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
                    # print(err)
                    # print(f"{P_number} is False")
                    return False
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
            return True

        def find_P_nr(n_guess, wto_ratio,bypass=True):
            # Flags used to prevent double checking the boundaries
            nmin_is_bounded = False
            nmax_is_bounded = False
            if not bypass: # for debugging
                if wto_ratio is not None:
                    n = round(n_guess * wto_ratio)
                    # check that the value below the initial guess is invalid
                    if not evaluate_P_nr(n - 1):
                        n_min = n - 1
                        if evaluate_P_nr(n):  # check that the guess is valid
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
                while evaluate_P_nr(n_min):
                    n_max = n_min  # if the n_min guess is too large it can be the new n_max to save iterations since it has already been tried
                    n_min = math.floor(n_min / 2)  # halve n_min until it fails
                    nmax_is_bounded = True  # nmax is set to a known valid value and does not need to be reevaluated

            # raise the max p number until its valid
            if not nmax_is_bounded:
                while not evaluate_P_nr(n_max):
                    n_min = n_max  # if the nmax guess is too small it can be the new nmin to save iterations since it has already been tried
                    n_max = n_max * 2  # double n_max until it works

            # start from the middle
            n = math.ceil((n_max + n_min) / 2)

            # find optimal P number using bisection search
            optimal = False
            while not optimal:
                valid_result = evaluate_P_nr(n)

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