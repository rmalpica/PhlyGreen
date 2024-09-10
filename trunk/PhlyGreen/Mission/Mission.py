import numpy as np
import numbers
import math
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed
import scipy.integrate as integrate
from .Profile import Profile

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

    """ Properties """

    @property
    def beta0(self):
        if self._beta0 == None:
            raise ValueError("Initial weight fraction beta0 unset. Exiting")
        return self._beta0
      
    @beta0.setter
    def beta0(self,value):
        self._beta0 = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal weight fraction beta0: %e. Exiting" %value)

    @property
    def ef(self):
        if self._ef == None:
            raise ValueError("Fuel specific energy unset. Exiting")
        return self._ef
      
    @ef.setter
    def ef(self,value):
        self._ef = value
        if(isinstance(value, numbers.Number) and (value <= 0)):
            raise ValueError("Error: Illegal fuel specific energy: %e. Exiting" %value)

    """Methods """

    def SetInput(self):

        self.beta0 = self.aircraft.MissionInput['Beta start']
        self.ef = self.aircraft.EnergyInput['Ef']
        self.SOC_min = self.aircraft.MissionInput['Minimum SOC']

    def InitializeProfile(self):
        
        self.profile = Profile(self.aircraft)
        
        self.profile.DefineMission()
        
        self.t = np.linspace(0,self.profile.MissionTime2,num=1000)


    def EvaluateMission(self,WTO):
        
        if self.aircraft.Configuration == 'Traditional':     
            return self.TraditionalConfiguration(WTO)
            
        elif self.aircraft.Configuration == 'Hybrid':     
            return self.HybridConfiguration(WTO)

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
    
    
    
    def HybridConfiguration(self,WTO):
        
        self.WTO = WTO
        
        
        def PowerPropulsive(Beta,t):
            PPoWTO = self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,Beta,self.profile.PowerExcess(t),1,self.profile.Altitude(t),self.DISA,self.profile.Velocity(t),'TAS')
          
            return PPoWTO * WTO


        def model_simplified(t,y): #simplified model for initializing the calculations with a known upper bound on requirements

            Beta = y[2] #aircraft mass fraction

            Ppropulsive = PowerPropulsive(Beta,t)
            PRatio = self.aircraft.powertrain.Hybrid(self.aircraft.mission.profile.SuppliedPowerRatio(t),self.profile.Altitude(t),self.profile.Velocity(t),Ppropulsive) #takes in all the mission segments and finds the required power ratio for the current time of the mission

            dEFdt = Ppropulsive * PRatio[0] #fuel power output
            dEBatdt = Ppropulsive * PRatio[5] #electric power required for the electric motors
            dbetadt = - dEFdt/(self.ef*self.WTO) #change in mass due to fuel consumption
            return [dEFdt,dEBatdt,dbetadt]


        def model(t,y):
            if not self.valid_solution:
                return [0,0,0,0]

            #battery state of charge
            SOC = y[3]
            if (SOC<self.SOC_min):
                self.constraint_low_SOC = False
                self.valid_solution = False
                return [0,0,0,0]

            #aircraft mass fraction
            Beta = y[2]
            Ppropulsive = PowerPropulsive(Beta,t)
            PRatio = self.aircraft.powertrain.Hybrid(self.aircraft.mission.profile.SuppliedPowerRatio(t),self.profile.Altitude(t),self.profile.Velocity(t),Ppropulsive) #takes in all the mission segments and finds the required power ratio for the current time of the mission

            dEFdt = Ppropulsive * PRatio[0] #fuel power output
            dbetadt = - dEFdt/(self.ef*self.WTO) #change in mass due to fuel consumption

            PElectric = Ppropulsive * PRatio[5] #propulsive power required for the electric motors

            #open circuit voltage of the battery at the current SOC
            BatVoltOC = self.aircraft.battery.SOC_2_OC_Voltage(SOC)
            if (BatVoltOC < self.aircraft.battery.pack_Vmin):
                self.constraint_low_voltage = False
                self.valid_solution = False
                return [0,0,0,0]

            #current drawn to meet power demands
            BatVolt, BatCurr  = self.aircraft.battery.Power_2_V_A(SOC, PElectric) #convert output power to volts and amps
            if (BatCurr == None):
                self.constraint_underpowered = False
                self.valid_solution = False
                return [0,0,0,0]
            if (BatCurr > self.aircraft.battery.pack_current):
                self.constraint_overcurrent = False
                self.valid_solution = False
                return [0,0,0,0]
            if (BatVolt < self.aircraft.battery.controller_Vmin):
                self.constraint_low_voltage = False
                self.valid_solution = False
                return [0,0,0,0]

            dSOCdt = -BatCurr/self.aircraft.battery.pack_charge #gives the rate of change of SOC
            dEdt_bat = BatVoltOC * BatCurr #gives the watts spent by the battery
            return [dEFdt,dEdt_bat,dbetadt,dSOCdt]


        def evaluate_P_nr(P_number):

            #no maths needed to know nothing will work without a battery
            if P_number == 0:
                return [False,False,False,False,False]

            # resetting the constraint booleans
            self.constraint_low_SOC = True
            self.constraint_low_voltage = True
            self.constraint_overcurrent = True
            self.constraint_TO_underpowered = True
            self.constraint_underpowered = True

            self.aircraft.battery.Configure(P_number) #changes the configuration every cycle
            self.TO_Voltage , self.TO_current = self.aircraft.battery.Power_2_V_A(1,self.TO_PBat)
            if (self.TO_Voltage == None):
                self.constraint_low_voltage = False
            elif (self.TO_Voltage < self.aircraft.battery.controller_Vmin):
                self.constraint_low_voltage = False
            elif (self.TO_current == None):
                self.constraint_TO_underpowered = False
            elif (self.aircraft.battery.pack_current < self.TO_current ):
                self.constraint_TO_underpowered = False
            else:
                # integrate sequentially
                self.integral_solution = []
                self.CurrentvsTime = [] #for the heat calculations. maybe this can be moved elsewhere?
                times = np.append(self.profile.Breaks,self.profile.MissionTime2)
                rtol = 1e-5
                method= 'BDF'
                y0 = [0,0,self.beta0,1] #initial fuel energy, battery energy, mass fraction, and SOC

                for i in range(len(times)-1):
                    self.valid_solution = True
                    sol = integrate.solve_ivp(model,[times[i], times[i+1]], y0, method=method, rtol=rtol) #"model" returns d
                    if not self.valid_solution:
                        break
                    self.integral_solution.append(sol)

                    # make array of the calculated time points and battery current 
                    # in order to calculate the heat. Possibly change this so that
                    # it feeds directly into a function instead of making an array
                    # to enable calculating the battery heating in the integration
                    for k in range(len(sol.t)):
                        yy0 = [sol.y[0][k],sol.y[1][k],sol.y[2][k],sol.y[3][k]]
                        self.CurrentvsTime.append([sol.t[k],model(sol.t[k],yy0)[1]])

                    y0 = [sol.y[0][-1],sol.y[1][-1],sol.y[2][-1],sol.y[3][-1]]
                    # watch out: the simplified model returns battery energy in joules,
                    # but the complete model returns battery CHARGE in coulombs instead

            return [self.constraint_low_SOC,
                    self.constraint_low_voltage,
                    self.constraint_overcurrent,
                    self.constraint_underpowered,
                    self.constraint_TO_underpowered]


        # Takeoff condition, calculated before anything else as it does not depend on the battery size, just the aircraft

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


#initialize with simplified calculations for worst case scenario conditions
#this initialization does not concern itself with validating a battery size or calculating its behavior
#it simply finds the max power and energy required for the battery during the flight
#and then uses that value to find the worst case scenario for the battery dimension
#this is faster than trying to iteratively validate larger and larger batteries until one works

        self.Max_PBat = -1
        self.Max_PEng = -1

        y0 = [0,0,self.beta0] #integration starting point for the battery and fuel energy as well as mass fraction
        rtol = 1e-5 #integrator tolerance
        method= 'BDF'

        # integrate the flight sequentially
        self.integral_solution = []
        times = np.append(self.profile.Breaks,self.profile.MissionTime2)
        for i in range(len(times)-1):
            sol = integrate.solve_ivp(model_simplified,[times[i], times[i+1]], y0, method=method, rtol=rtol) 
            self.integral_solution.append(sol) 
            y0 = [sol.y[0][-1],sol.y[1][-1],sol.y[2][-1],]


        # compute peak Propulsive power along mission
        self.Ef = sol.y[0]
        self.EBat = sol.y[1]
        self.Beta = sol.y[2]
        times = []
        beta = []
        for array in self.integral_solution:
            times = np.concatenate([times, array.t])
            beta = np.concatenate([beta, array.y[2]])

        # get the propulsive power along the mission
        PP = np.array([WTO * self.aircraft.performance.PoWTO(
                                                             self.aircraft.DesignWTOoS,beta[i],
                                                             self.profile.PowerExcess(times[i]),
                                                             1,
                                                             self.profile.Altitude(times[i]),
                                                             self.DISA,self.profile.Velocity(times[i]),
                                                             'TAS'
                                                            ) for i in range(len(times))])
        # get the power ratio along the mission
        PRatio = np.array([self.aircraft.powertrain.Hybrid(
                                                           self.aircraft.mission.profile.SuppliedPowerRatio(times[i]),
                                                           self.profile.Altitude(times[i]),
                                                           self.profile.Velocity(times[i]), PP[i]
                                                          ) for i in range(len(times))])

        # find maximum power for both the electrical and thermal powerplants
        self.Max_PEng = np.max(np.multiply(PP,PRatio[:,1]))
        self.Max_PBat = np.max(np.multiply(PP,PRatio[:,5]))

        # find the battery P number for the worst case scenario given by the initializing integration
        self.flight_P_number = self.aircraft.battery.Pwr_2_P_num(0,self.Max_PBat) #finds the P number for flight at zero SOC
        self.TO_P_number     = self.aircraft.battery.Pwr_2_P_num(1,self.TO_PBat)  #finds the P number for takeoff power
        self.energy_P_number = self.aircraft.battery.Nrg_2_P_num(self.EBat[-1])   #finds the P number for the flight energy // TODO figure out why this is usually estimated too low

        #initializes the calculation using the largest expected P number, picks the maximum value, rounds up
        expected_P_n_max = math.ceil(max([
                                          self.TO_P_number,
                                          self.flight_P_number,
                                          self.energy_P_number
                                         ])) 

        #initializing variables before the loop
        optimal = False
        n_max = expected_P_n_max
        n_min = 0

        #used as a quick fix for the initial guess being undersized on some cases for some reason
        while not all(evaluate_P_nr(n_max)): 
            #print("n_max underestimated:",n_max, "; increasing.")
            n_min = n_max   #if the nmax guess is too small it can be the new nmin to save iterations since it has already been tried
            n_max = n_max*2 #increase n_max until it works

        n=math.ceil((n_max+n_min)/2) #start from the middle to make it one iteration shorter
        j=0

        #find optimal P number using bisection search
        while not optimal:
            j=j+1
            output = evaluate_P_nr(n)
            valid_result = all(output)
            # print("[iter",j,"] [P",n,"] [min",n_min,"] [max",n_max,"] valid?",valid_result) #uncomment for debug

            if valid_result and (n-n_min)==1: #n is optimal
                print("Optimal P: ",n)
                optimal = True

            elif valid_result:                #n is too big
                self.driving_constraints=output
                n_max=n
                n=math.floor((n_max+n_min)/2)

            elif not valid_result :           #n is too small
                self.driving_constraints=output
                n_min=n
                n=math.ceil((n_max+n_min)/2)

        return self.Ef[-1], self.EBat[-1]