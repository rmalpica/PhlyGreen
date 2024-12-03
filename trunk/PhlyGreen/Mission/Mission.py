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
        self.aircraft.battery.SOC_min = self.aircraft.MissionInput['Minimum SOC']

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

        def model(t,y):
            if not self.valid_solution:
                return [0,0,0,0]

            #aircraft mass fraction
            Beta = y[2]
            Ppropulsive = PowerPropulsive(Beta,t)
            PRatio = self.aircraft.powertrain.Hybrid(self.aircraft.mission.profile.SuppliedPowerRatio(t),self.profile.Altitude(t),self.profile.Velocity(t),Ppropulsive) #takes in all the mission segments and finds the required power ratio for the current time of the mission

            dEFdt = Ppropulsive * PRatio[0] #fuel power output
            dbetadt = - dEFdt/(self.ef*self.WTO) #change in mass due to fuel consumption

            PElectric = Ppropulsive * PRatio[5] #propulsive power required for the electric motors

            #current drawn to meet power demands
            try:
                self.aircraft.battery.T = y[4]
                self.aircraft.battery.it = y[3]
                self.aircraft.battery.i  = self.aircraft.battery.Power_2_current(PElectric) #convert output power to volts and amps
                dEdt_bat = self.aircraft.battery.i * self.aircraft.battery.Vout
                dTdt = self.aircraft.battery.heatLoss(300)
            except Exception as err:
                print(err)
                self.valid_solution = False
                return [0,0,0,0]
            return [dEFdt,dEdt_bat,dbetadt,self.aircraft.battery.i,dTdt]


        def evaluate_P_nr(P_number):
            print(f"pnumber {P_number}")
            self.valid_solution = True
            #no maths needed to know nothing will work without a battery
            if P_number == 0:
                self.valid_solution = False
                return self.valid_solution

            self.aircraft.battery.Configure(P_number) #changes the configuration every cycle
            try:
                self.aircraft.battery.it = 0
                self.aircraft.battery.i  = self.aircraft.battery.Power_2_current(self.TO_PBat) #convert output power to volts and amps
                self.aircraft.battery.Vout
            except Exception as err:
                print(err)
                self.valid_solution = False
                return self.valid_solution
            
            # integrate sequentially
            self.integral_solution = []
            self.CurrentvsTime = [] #for the heat calculations. maybe this can be moved elsewhere?
            self.plottingVars=[]
            times = np.append(self.profile.Breaks,self.profile.MissionTime2)
            rtol = 1e-5
            method= 'BDF'
            y0 = [0,0,self.beta0,0] #initial fuel energy, battery energy, mass fraction, and spent charge
            for i in range(len(times)-1):
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
                    model(sol.t[k],yy0)

                    self.CurrentvsTime.append([sol.t[k],self.outBatCurr])
                    self.plottingVars.append([sol.t[k],
                                                self.outBatVolt,
                                                self.outBatVolt,
                                                self.outBatCurr])
                self.Ef = sol.y[0]
                self.EBat = sol.y[1]
                self.Beta = sol.y[2]
                y0 = [sol.y[0][-1],sol.y[1][-1],sol.y[2][-1],sol.y[3][-1],sol.y[4][-1]]


            return self.valid_solution


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

        # as the brent search converges the binary search algorithm needs to do more pointless iterations to reach the same value
        # the old method used a simplified model to initialize a first guess of the p number
        # this proved slow and cumbersome, so i came up with a new method that uses the previous result to initialize the search
        # it grabs the n value from the previous iteration and tries to find an nmax and nmin from there 
        optimal = False
        try:
            n_max = self.optimal_n
            n_min = self.optimal_n-1
            #print(f'using {n_max} and {n_min} from optimal {self.optimal_n}')
        except Exception as err:
            #print(f'optimal not found because of:\n {err}')
            n_max = 128  # hardcoding a value that is anecdotally known to be ok for a first guess
            n_min = 0

        #lower the min p number until its valid
        while all(evaluate_P_nr(n_min)): 
            print("n_min overestimated:",n_min, "; halving.")
            n_max = n_min   #if the n_min guess is too large it can be the new n_max to save iterations since it has already been tried
            n_min = math.floor(n_min/2) #half n_min until it fails

        #raise the max p number until its valid
        while not all(evaluate_P_nr(n_max)): 
            #print(evaluate_P_nr(n_max))
            print("n_max underestimated:",n_max, "; doubling.")
            n_min = n_max   #if the nmax guess is too small it can be the new nmin to save iterations since it has already been tried
            n_max = n_max*2 #double n_max until it works

        # if nmax and nmin are just 1 apart then the optimal n is nmax
        # all checks can be skipped and we jump right into evaluating n to configure the flight
        # print(f"nmax ({n_max}) validity is {all(evaluate_P_nr(n_max))} and nmin ({n_min}) validity is {all(evaluate_P_nr(n_min))}") # debug only
        if n_max - n_min == 1: 
            optimal = True
            n = n_max
            output = evaluate_P_nr(n)
            valid_result = all(output)
            if not valid_result:
                raise Exception("Impossible n value somehow")
            print("Optimal P: ",n)
            self.optimal_n = n

        n=math.ceil((n_max+n_min)/2) #start from the middle to make it one iteration shorter
        #j=0

        #find optimal P number using bisection search
        while not optimal:
            #j=j+1
            output = evaluate_P_nr(n)
            valid_result = all(output)
            # print("[iter",j,"] [P",n,"] [min",n_min,"] [max",n_max,"] valid?",valid_result) #uncomment for debug

            if valid_result and (n-n_min)==1: #n is optimal
                print("Optimal P: ",n)
                self.optimal_n = n
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