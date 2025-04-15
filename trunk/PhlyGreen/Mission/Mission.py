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
        self.TO_PBat = 0  
        self.TO_PP = 0 

        self.ef = None
        self.profile = None
        self.t = None
        self.Ef = None
        self.EBat = None
        self.Beta = None

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
        Ppropulsive = self.WTO * self.aircraft.performance.TakeOff(self.aircraft.DesignWTOoS,self.aircraft.constraint.TakeOffConstraints['Beta'], self.aircraft.constraint.TakeOffConstraints['Altitude'], self.aircraft.constraint.TakeOffConstraints['kTO'], self.aircraft.constraint.TakeOffConstraints['sTO'], self.aircraft.constraint.DISA, self.aircraft.constraint.TakeOffConstraints['Speed'], self.aircraft.constraint.TakeOffConstraints['Speed Type'])
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
            Ppropulsive = self.WTO * self.aircraft.performance.TakeOff(self.aircraft.DesignWTOoS,self.aircraft.constraint.TakeOffConstraints['Beta'], self.aircraft.constraint.TakeOffConstraints['Altitude'], self.aircraft.constraint.TakeOffConstraints['kTO'], self.aircraft.constraint.TakeOffConstraints['sTO'], self.aircraft.constraint.DISA, self.aircraft.constraint.TakeOffConstraints['Speed'], self.aircraft.constraint.TakeOffConstraints['Speed Type'])
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
            self.Max_PBat = np.max(np.multiply(PP,PRatio[:,5]))

            return self.Ef[-1], self.EBat[-1]
        

    
    def HybridConfigurationClassII(self,WTO):
 
        self.WTO = WTO

        def PowerPropulsive(Beta,t):
            PPoWTO = self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,Beta,self.profile.PowerExcess(t),1,self.profile.Altitude(t),self.DISA,self.profile.Velocity(t),'TAS')
          
            return PPoWTO * WTO

        def model(t,y):

            #aircraft mass fraction
            Beta = y[2]
            Ppropulsive = PowerPropulsive(Beta,t)
            #takes in all the mission segments and finds the required power ratio for the current time of the mission
            PRatio = self.aircraft.powertrain.Hybrid(self.aircraft.mission.profile.SuppliedPowerRatio(t),
                                                     self.profile.Altitude(t),
                                                     self.profile.Velocity(t),
                                                     Ppropulsive) 
            dEFdt = Ppropulsive * PRatio[0] #fuel power output
            dbetadt = - dEFdt/(self.ef*self.WTO) #change in mass due to fuel consumption
            PElectric = Ppropulsive * PRatio[5] #propulsive power required for the electric motors

            # Finds the battery state for the requested power. The battery class raises an
            # exception if any of its parameters exceed the allowed limits or there are
            # unphysical values. This is taken as a sign that the P number is invalid. The
            # exception may be caught into a global variable so that the last constraint
            # driving the battery sizing may be printed to the user. Temperature limits
            # are not validated because T depends on the cooling sizing, not the P number.
            
            self.aircraft.battery.T = y[4] # assign a temperature, battery class validates temp
            self.aircraft.battery.it = y[3]/3600 # assign spent charge, battery validates SOC
            self.aircraft.battery.i  = self.aircraft.battery.Power_2_current(PElectric) # assign current, also validated here by the class
            dEdt_bat = self.aircraft.battery.i * self.aircraft.battery.Vout # calculate power, this causes Vout to be generated and validated
            
            alt = self.profile.Altitude(t)
            Mach = Speed.TAS2Mach(self.profile.Velocity(t),alt,DISA=self.DISA)
            Tamb = ISA.atmosphere.T0std(alt,Mach)
            rho = ISA.atmosphere.RHO0std(alt,Mach,self.DISA)
            dTdt, _ = self.aircraft.battery.heatLoss(Tamb,rho)

            return [dEFdt,dEdt_bat,dbetadt,self.aircraft.battery.i,dTdt]


        def evaluate_P_nr(P_number):
            
            # print(f"pnumber {P_number}")
            self.P_n_arr.append(P_number)
            #no maths needed to know nothing will work without a battery
            if P_number == 0:
                return False

            self.aircraft.battery.Configure(P_number)

            # short verification step to validate the takeoff power
            # uses it = 0 and constant T.  Takeoff is considered to
            # be too short to matter, and there's no good model for
            # the takeoff dynamics anyway.
            try:
                #print(f"P num during try: {P_number}")
                self.aircraft.battery.T = 300 # battery T TODO FIX THIS
                self.aircraft.battery.it = 0
                self.aircraft.battery.i  = self.aircraft.battery.Power_2_current(self.TO_PBat) #convert output power to volts and amps
                self.aircraft.battery.Vout # necessary statement for the battery class to validate Vout
            except BatteryError as err:
                #print(f"P num at error: {P_number}")
                #print(err)
                return False
            except Exception as err:
                print(f"Unexpected error: {err}")
                raise
            
            # integrate sequentially
            np.seterr(over="raise")
            times = np.append(self.profile.Breaks,self.profile.MissionTime2)
            rtol = 1e-6
            method= 'BDF'
            self.integral_solution = []
            self.plottingVars=[]
            #initial fuel energy, battery energy, mass fraction, spent charge, and battery T
            y0 = [0,0,self.beta0,0,300]
            for i in range(len(times)-1):

                try:
                    sol = integrate.solve_ivp(model,[times[i], times[i+1]], y0, method=method, rtol=rtol)
                    self.integral_solution.append(sol)
                except BatteryError as err:
                    # print(f"P num at error: {self.aircraft.battery.P_number}")
                    # print(err)
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
                for k in range(len(sol.t)-0):
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
                        # Print warning and just keep saving the data
                        print("WARNING: evaluate_P_number integration rtol may be too small, consider increasing it")
                self.Ef = sol.y[0]
                self.EBat = sol.y[1]
                self.Beta = sol.y[2]
                y0 = [sol.y[0][-1], sol.y[1][-1], sol.y[2][-1], sol.y[3][-1], sol.y[4][-1]]

            return True


        # Takeoff condition, calculated before anything else as
        # it does not depend on the battery size, just the aircraft

        #calculates the total propulsive power required for takeoff
        Ppropulsive_TO = self.WTO * self.aircraft.performance.TakeOff(self.aircraft.DesignWTOoS,
                                                                      self.aircraft.constraint.TakeOffConstraints['Beta'],
                                                                      self.aircraft.constraint.TakeOffConstraints['Altitude'],
                                                                      self.aircraft.constraint.TakeOffConstraints['kTO'],
                                                                      self.aircraft.constraint.TakeOffConstraints['sTO'],
                                                                      self.aircraft.constraint.DISA,
                                                                      self.aircraft.constraint.TakeOffConstraints['Speed'],
                                                                      self.aircraft.constraint.TakeOffConstraints['Speed Type'])
        #hybrid power ratio for takeoff
        PRatio = self.aircraft.powertrain.Hybrid(self.aircraft.mission.profile.SPW[0][0],
                                                 self.aircraft.constraint.TakeOffConstraints['Altitude'],
                                                 self.aircraft.constraint.TakeOffConstraints['Speed'],
                                                 Ppropulsive_TO)

        self.TO_PP = Ppropulsive_TO * PRatio[1]   #combustion engine power during takeoff
        self.TO_PBat = Ppropulsive_TO * PRatio[5] #electric motor power during takeoff

        # as the brent search converges the binary search algorithm needs to do more pointless iterations to reach the same value
        # the old method used a simplified model to initialize a first guess of the p number
        # this proved slow and cumbersome, so i came up with a new method that uses the previous result to initialize the search
        # it grabs the n value from the previous iteration and tries to find an nmax and nmin from there
        optimal = False
        nmin_is_bounded = False #used to prevent double checking the boundaries
        nmax_is_bounded = False
        try:
            #ratio = 1  # use this line to disable linear scaling of the P_n for debug purposes
            ratio = self.WTO / self.last_weight
            n = round(self.optimal_n * ratio)
 
            if not evaluate_P_nr(n - 1): # check that the value before the initial guess is invalid
                n_min = n-1
                if evaluate_P_nr(n): # check that the guess is valid
                    n_max=n
                    optimal = True
                else:
                    nmin_is_bounded = True
                    n_min = n #if the guess is invalid, its the new minimum
                    n_max = max(n_min+1,round((self.optimal_n + 1) * ratio)) #scale the guess range by the wto ratio

            else:
                nmax_is_bounded = True
                n_max = n-1 #if the value before the guess is valid its the new max
                n_min = min(n_max - 1, round((self.optimal_n - 1) * ratio))  #scale the guess range by the wto ratio


        except TypeError:# as err:
            # print('**********************************')
            # print(f'optimal not found because of:\n {err}')
            n_max = 128  # hardcoding a value that is anecdotally known to be ok for a first guess
            n_min = n_max-1

        if not nmin_is_bounded and not optimal:
            while evaluate_P_nr(n_min):
                # print(f"22 - nmax {n_max}; nmin {n_min}")
                # print("n_min overestimated:",n_min, "; halving.")
                nmax_is_bounded = True
                n_max = n_min   #if the n_min guess is too large it can be the new n_max to save iterations since it has already been tried
                n_min = math.floor(n_min/2) #halve n_min until it fails
            nmin_is_bounded = True

        #raise the max p number until its valid
        if not nmax_is_bounded and not optimal:
            while not evaluate_P_nr(n_max):
                # print(f"333 - nmax {n_max}; nmin {n_min}")
                #print(evaluate_P_nr(n_max))
                # print("n_max underestimated:",n_max, "; doubling.")
                n_min = n_max   #if the nmax guess is too small it can be the new nmin to save iterations since it has already been tried
                n_max = n_max*2 #double n_max until it works

        # if nmax and nmin are just 1 apart then the optimal n is nmax
        # all checks can be skipped and we jump right into evaluating n to configure the flight
        # print(f"nmax ({n_max}) validity is {all(evaluate_P_nr(n_max))} and nmin ({n_min}) validity is {all(evaluate_P_nr(n_min))}") # debug only
        if n_max - n_min == 1:
            optimal = True
            n = n_max
            self.optimal_n = n

        n=math.ceil((n_max+n_min)/2) #start from the middle to make it one iteration shorter
        #j=0
        # print(f"4444 - nmax {n_max}; n {n}; nmin {n_min}")
        #find optimal P number using bisection search
        while not optimal:
            # print(f"nmax {n_max}; n {n}; nmin {n_min}")
            #j=j+1
            valid_result = evaluate_P_nr(n)
            # print("[iter",j,"] [P",n,"] [min",n_min,"] [max",n_max,"] valid?",valid_result) #uncomment for debug

            if valid_result and (n-n_min)==1: #n is optimal
                # print("Optimal P: ",n)
                self.optimal_n = n
                optimal = True

            elif valid_result:                #n is too big
                n_max=n
                n=math.floor((n_max+n_min)/2)

            elif not valid_result :           #n is too small
                n_min=n
                n=math.ceil((n_max+n_min)/2)
        
        # save weight across iterations
        self.last_weight = self.WTO
        # """
        # Save history for performance profiling
        self.Past_P_n.append(self.P_n_arr)
        self.P_n_arr = []

        return self.Ef[-1], self.EBat[-1]