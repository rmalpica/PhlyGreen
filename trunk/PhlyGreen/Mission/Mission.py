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

            PPoWTO = self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,Beta,self.profile.PowerExcess(t),1,self.profile.Altitude(t),self.DISA,self.profile.Velocity(t),'TAS')
          
            return PPoWTO * WTO

        
        def model(t,y):

            Beta = y[2] #aircraft mass fraction
            SOC = y[3]  #battery state of charge
            Ppropulsive = PowerPropulsive(Beta,t)
            PRatio = self.aircraft.powertrain.Hybrid(self.aircraft.mission.profile.SuppliedPowerRatio(t),self.profile.Altitude(t),self.profile.Velocity(t),Ppropulsive) #takes in all the mission segments and finds the required power ratio for the current time of the mission

            dEFdt = Ppropulsive * PRatio[0] #fuel power output
            dbetadt = - dEFdt/(self.ef*self.WTO) #change in mass due to fuel consumption

            PElectric = Ppropulsive * PRatio[5] #propulsive power required for the electric motors
            BatVolt = self.aircraft.battery.SOC_2_OC_Voltage(SOC) #open circuit voltage of the battery at the current SOC
            BatCurr = self.aircraft.battery.Power_2_Current(SOC, PElectric, self.aircraft.battery.parallel_stack_number) #current output of the battery at the current motor power draw

            dEBatdt = BatVolt * BatCurr #actual power drawn from the battery, losses included
            dSOCdt = 1-dEBatdt/self.aircraft.battery.pack_energy #gives the rate of change of SOC over time

            return [dEFdt,dEBatdt,dbetadt,dSOCdt]

        # Takeoff condition
        Ppropulsive = self.WTO * self.aircraft.performance.TakeOff(self.aircraft.DesignWTOoS,self.aircraft.constraint.TakeOffConstraints['Beta'], self.aircraft.constraint.TakeOffConstraints['Altitude'], self.aircraft.constraint.TakeOffConstraints['kTO'], self.aircraft.constraint.TakeOffConstraints['sTO'], self.aircraft.constraint.DISA, self.aircraft.constraint.TakeOffConstraints['Speed'], self.aircraft.constraint.TakeOffConstraints['Speed Type']) #calculates the propulsive power required for takeoff

        PRatio = self.aircraft.powertrain.Hybrid(self.aircraft.mission.profile.SPW[0][0],self.aircraft.constraint.TakeOffConstraints['Altitude'],self.aircraft.constraint.TakeOffConstraints['Speed'],Ppropulsive) #hybrid power ratio for takeoff
        self.TO_PP = Ppropulsive * PRatio[1] #combustion engine power during takeoff
        self.TO_PBat = Ppropulsive * PRatio[5] #electric motor power during takeoff
        self.TO_PBat_Cells = self.aircraft.battery.Power_2_Parallel_Cells(1,self.TO_PBat) #1 here is the SOC at takeoff, assumes fully charged batteries TODO CONSIDER CHANGING LATER

        #set/reset max values
        self.Max_PBat = -1
        self.Max_PEng = -1

        y0 = [0,0,self.beta0,1] ##integration starting point for the spent battery and fuel energy as well as mass fraction and SOC

        rtol = 1e-5
        method= 'BDF'

        # integrate all phases together
        # sol = integrate.solve_ivp(model,[0, self.profile.MissionTime2],y0,method='BDF',rtol=1e-6)

        # integrate sequentially
        self.integral_solution = []
        times = np.append(self.profile.Breaks,self.profile.MissionTime2)
        for i in range(len(times)-1):
            sol = integrate.solve_ivp(model,[times[i], times[i+1]], y0, method=method, rtol=rtol) 
            self.integral_solution.append(sol) 
            y0 = [sol.y[0][-1],sol.y[1][-1],sol.y[2][-1],sol.y[3][-1]]
            """
            SOC is y[3] lets hope this works how i think it does because i have not tested it yet
            """

        self.Ef = sol.y[0]
        self.EBat = sol.y[1] 
        self.Beta = sol.y[2]


        # compute peak Propulsive power along mission
        times = []
        beta = []
        SOC = []
        for array in self.integral_solution:
            times = np.concatenate([times, array.t])
            beta = np.concatenate([beta, array.y[2]])
            SOC = np.concatenate([SOC, array.y[3]])

        PP = np.array([WTO * self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,beta[i], self.profile.PowerExcess(times[i]), 1, self.profile.Altitude(times[i]), self.DISA,self.profile.Velocity(times[i]), 'TAS') for i in range(len(times))])

        PRatio = np.array([self.aircraft.powertrain.Hybrid(self.aircraft.mission.profile.SuppliedPowerRatio(times[i]), self.profile.Altitude(times[i]), self.profile.Velocity(times[i]), PP[i]) for i in range(len(times))] )

        self.Max_PEng = np.max(np.multiply(PP,PRatio[:,1]))
        #self.Max_PBat = np.max(np.multiply(PP,PRatio[:,5])) # <- replace with max nr of cells required for power
        self.PwrBatArray = np.multiply(PP,PRatio[:,5])

        self.CellBatArray = []
        #get all the equivalent parallel cells needed for power at each point of the flight and put them all in an array
        for i in range(len(self.PBatArray)):
            instantCells=self.aircraft.battery.Power_2_Parallel_Cells(SOC[i], self.PwrBatArray[i]) 
            self.CellBatArray = np.concatenate([self.CellBatArray, instantCells])
        self.Max_PBat_Cells = np.max(self.CellBatArray)

        #returns the required Fuel Energy & Battery Energy
        return self.Ef[-1], self.EBat[-1]


"""
ok to do: 
line 60
then figure out how to initialize things in the battery.py file - done?
"""