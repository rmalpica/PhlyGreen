import numpy as np
import numbers
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
        """TODO remember to add here an input for SOC_0"""
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
            #print("AAAAAAAAAAAAAAAAAAAAAAA",self.aircraft.DesignWTOoS,Beta,self.profile.PowerExcess(t),1,self.profile.Altitude(t),self.DISA,self.profile.Velocity(t),'TAS')
            PPoWTO = self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,Beta,self.profile.PowerExcess(t),1,self.profile.Altitude(t),self.DISA,self.profile.Velocity(t),'TAS')
          
            return PPoWTO * WTO

        
        def model(t,y):
            #if self.aircraft.battery.P_number > 180:
            #print("time",t," and inputs",y, " and pack number",self.aircraft.battery.P_number)
            Beta = y[2] #aircraft mass fraction

            #battery state of charge
            SOC = y[3]
            if (SOC<0):
                self.constraint_low_SOC = False
                return [0,0,0,0]
            Ppropulsive = PowerPropulsive(Beta,t)
            PRatio = self.aircraft.powertrain.Hybrid(self.aircraft.mission.profile.SuppliedPowerRatio(t),self.profile.Altitude(t),self.profile.Velocity(t),Ppropulsive) #takes in all the mission segments and finds the required power ratio for the current time of the mission

            dEFdt = Ppropulsive * PRatio[0] #fuel power output
            dbetadt = - dEFdt/(self.ef*self.WTO) #change in mass due to fuel consumption

            PElectric = Ppropulsive * PRatio[5] #propulsive power required for the electric motors

            #open circuit voltage of the battery at the current SOC
            BatVolt = self.aircraft.battery.SOC_2_OC_Voltage(SOC)
            if (BatVolt < self.aircraft.battery.controller_Vmin or BatVolt < self.aircraft.battery.pack_Vmin):
                self.constraint_low_voltage = False
                return [0,0,0,0]

            #current drawn to meet power demands
            BatCurr = self.aircraft.battery.Power_2_Current(SOC, PElectric)
            if (BatCurr == None):
                self.constraint_underpowered = False
                return [0,0,0,0]
            if (BatCurr > self.aircraft.battery.pack_current):
                self.constraint_overcurrent = False
                return [0,0,0,0]

            dEBatdt = BatVolt * BatCurr #actual power drawn from the battery, losses included
            dSOCdt = -dEBatdt/self.aircraft.battery.pack_energy #gives the rate of change of SOC over time
            #print("batcurr",BatCurr)
            #print("BBBBBBBBBBBBBBBBBB",dEFdt,dEBatdt,dbetadt,dSOCdt)
            return [dEFdt,dEBatdt,dbetadt,dSOCdt]


        def model_simplified(t,y): #simplified model for initializing the calculations with a known upper bound on requirements

            Beta = y[2] #aircraft mass fraction

            Ppropulsive = PowerPropulsive(Beta,t)
            PRatio = self.aircraft.powertrain.Hybrid(self.aircraft.mission.profile.SuppliedPowerRatio(t),self.profile.Altitude(t),self.profile.Velocity(t),Ppropulsive) #takes in all the mission segments and finds the required power ratio for the current time of the mission

            dEFdt = Ppropulsive * PRatio[0] #fuel power output
            dEBatdt = Ppropulsive * PRatio[5] #electric power required for the electric motors
            dbetadt = - dEFdt/(self.ef*self.WTO) #change in mass due to fuel consumption
            return [dEFdt,dEBatdt,dbetadt]


        def evaluate_P_nr(self,P_number):
            # resetting the constraint booleans
            #self.constraints_met = True
            self.constraint_low_SOC = True
            self.constraint_low_voltage = True
            self.constraint_overcurrent = True
            self.constraint_TO_underpowered = True
            self.constraint_underpowered = True

            self.aircraft.battery.Configure(P_number) #changes the configuration every cycle
            #print("pnum of the pack",self.aircraft.battery.P_number)
            self.TO_current = self.aircraft.battery.Power_2_Current(1,self.TO_PBat)

            if (self.TO_current == None):
                self.constraint_TO_underpowered = False
            elif (self.aircraft.battery.pack_current < self.TO_current ):
                self.constraint_TO_underpowered = False
            else:
                # integrate sequentially
                self.integral_solution = []
                times = np.append(self.profile.Breaks,self.profile.MissionTime2)
                rtol = 1e-5
                method= 'BDF'
                y0 = [0,0,self.beta0,1] #initial fuel energy, battery energy, mass fraction, and SOC
                for i in range(len(times)-1):
                    sol = integrate.solve_ivp(model,[times[i], times[i+1]], y0, method=method, rtol=rtol)
                    if not sol:
                        break
                    self.integral_solution.append(sol) 
                    y0 = [sol.y[0][-1],sol.y[1][-1],sol.y[2][-1],sol.y[3][-1]]

            return [self.constraint_low_SOC,
                    self.constraint_low_voltage,
                    self.constraint_overcurrent,
                    self.constraint_underpowered,
                    self.constraint_TO_underpowered]


        # Takeoff condition
        Ppropulsive_TO = self.WTO * self.aircraft.performance.TakeOff(self.aircraft.DesignWTOoS,self.aircraft.constraint.TakeOffConstraints['Beta'], self.aircraft.constraint.TakeOffConstraints['Altitude'], self.aircraft.constraint.TakeOffConstraints['kTO'], self.aircraft.constraint.TakeOffConstraints['sTO'], self.aircraft.constraint.DISA, self.aircraft.constraint.TakeOffConstraints['Speed'], self.aircraft.constraint.TakeOffConstraints['Speed Type']) #calculates the propulsive power required for takeoff

        PRatio = self.aircraft.powertrain.Hybrid(self.aircraft.mission.profile.SPW[0][0],self.aircraft.constraint.TakeOffConstraints['Altitude'],self.aircraft.constraint.TakeOffConstraints['Speed'],Ppropulsive_TO) #hybrid power ratio for takeoff
        self.TO_PP = Ppropulsive_TO * PRatio[1] #combustion engine power during takeoff
        self.TO_PBat = Ppropulsive_TO * PRatio[5] #electric motor power during takeoff


#initialize with simplified calculations for worst case scenario conditions
        self.Max_PBat = -1
        self.Max_PEng = -1

        y0 = [0,0,self.beta0] ##integration starting point for the spent battery and fuel energy as well as mass fraction and SOC
        rtol = 1e-5
        method= 'BDF'

        # integrate sequentially
        self.integral_solution = []
        times = np.append(self.profile.Breaks,self.profile.MissionTime2)
        for i in range(len(times)-1):
            sol = integrate.solve_ivp(model_simplified,[times[i], times[i+1]], y0, method=method, rtol=rtol) 
            self.integral_solution.append(sol) 
            y0 = [sol.y[0][-1],sol.y[1][-1],sol.y[2][-1],]

        self.Ef = sol.y[0]
        self.EBat = sol.y[1]
        self.Beta = sol.y[2]
        # compute peak Propulsive power along mission
        times = []
        beta = []
        for array in self.integral_solution:
            times = np.concatenate([times, array.t])
            beta = np.concatenate([beta, array.y[2]])

        PP = np.array([WTO * self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,beta[i], self.profile.PowerExcess(times[i]), 1, self.profile.Altitude(times[i]), self.DISA,self.profile.Velocity(times[i]), 'TAS') for i in range(len(times))])

        PRatio = np.array([self.aircraft.powertrain.Hybrid(self.aircraft.mission.profile.SuppliedPowerRatio(times[i]), self.profile.Altitude(times[i]), self.profile.Velocity(times[i]), PP[i]) for i in range(len(times))] )

        self.Max_PEng = np.max(np.multiply(PP,PRatio[:,1]))
        self.Max_PBat = np.max(np.multiply(PP,PRatio[:,5]))

        self.flight_PBat_Cells = self.aircraft.battery.Pwr_2_P_num(0,self.Max_PBat) #finds the P number for flight at minimum SOC
        self.TO_PBat_Cells = self.aircraft.battery.Pwr_2_P_num(1,self.TO_PBat) #finds the P number for takeoff power
        self.energy_P_number = self.aircraft.battery.Energy_2_P_num(self.EBat[-1]*5) #finds the P number for the energy requirements using an exaggerated 20% extra energy just to be safe since the simplified calculations underestimage the energy required

        #print(self.TO_PBat_Cells,self.flight_PBat_Cells,self.energy_P_number)
        self.P_number_ceiling = int(np.ceil(np.max([
                                                    self.TO_PBat_Cells,
                                                    self.flight_PBat_Cells,
                                                    self.energy_P_number
                                                    ]))) #initializes the calculation using the highest P number, picks the maximum value, rounds up, and then converts to int

        #defining some initial constants before the loop
        optimal = False
        evaluation = None
        n = self.P_number_ceiling
        n_max=n
        n_min=1
        j=1
        while not optimal:
            print("iteration number", j)
            j=j+1
            output_a=evaluate_P_nr(self,n)
            output_b=evaluate_P_nr(self,n-1)
            result_a=all(output_a)
            result_b=all(output_b)

            if result_a and result_b: #n is too big
                print("Large: ",n)
                n_max=n
                n=int(np.ceil((n_max+n_min)/2))
            elif not result_a and not result_b: #n is too small
                print("Small: ",n)
                n_min=n
                n=int(np.ceil( (n_max+n_min)/2 ))
            elif result_a and not result_b:
                print("Optimal found: ",n)
                print("Constraints: ", output_b, "SOC; Voltage, Overcurrent, Underpowered, TO_underpowered")
                optimal = True
            else:
                raise Exception("function is not monotonic?????")

        evaluate_P_nr(self,n)

        self.Ef = sol.y[0]
        self.EBat = sol.y[1]

        return self.Ef[-1], self.EBat[-1]