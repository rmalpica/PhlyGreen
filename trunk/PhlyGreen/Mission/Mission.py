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
        self.Max_PF = -1  
        self.TO_PBat = 0  
        self.TO_PF = 0 

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
        
        
        def PF(Beta,t):

            PPoWTO = self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,Beta,self.profile.PowerExcess(t),1,self.profile.Altitude(t),self.DISA,self.profile.Velocity(t),'TAS')
            
            PFoPP = self.aircraft.powertrain.Traditional(self.profile.Altitude(t),self.profile.Velocity(t),PPoWTO*WTO)[0]

            return PPoWTO * PFoPP * WTO


        
        def model(t,y):
            Beta = y[1]
            dEdt = PF(Beta,t)
            # dbetadt = - PF(Beta,t)/(self.aircraft.ef*self.WTO)
            dbetadt = - dEdt/(self.ef*self.WTO)
            self.Max_PF = np.max([self.Max_PF,dEdt])

            return [dEdt,dbetadt]

        # Takeoff condition
        Ppropulsive = self.WTO * self.aircraft.performance.TakeOff(self.aircraft.DesignWTOoS,self.aircraft.constraint.ConstraintsBeta[1], self.aircraft.constraint.ConstraintsAltitude[1], self.aircraft.constraint.kTO, self.aircraft.constraint.sTO, self.aircraft.constraint.DISA, self.aircraft.constraint.ConstraintsSpeed[1], self.aircraft.constraint.ConstraintsSpeedtype[1])
        self.TO_PFoW = Ppropulsive * self.aircraft.powertrain.Traditional(self.aircraft.constraint.ConstraintsAltitude[1],self.aircraft.constraint.ConstraintsSpeed[1],Ppropulsive)[0] 

        #set/reset max values
        self.Max_PBat = -1
        self.Max_PF = -1
   

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
        

        return self.Ef[-1]
    
    
    
    def HybridConfiguration(self,WTO):
        
        self.WTO = WTO
        
        
        def PP(Beta,t):

            PPoWTO = self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,Beta,self.profile.PowerExcess(t),1,self.profile.Altitude(t),self.DISA,self.profile.Velocity(t),'TAS')
          
            return PPoWTO * WTO

        
        def model(t,y):
            
            Beta = y[2]
            Ppropulsive = PP(Beta,t)
            PRatio = self.aircraft.powertrain.Hybrid(self.aircraft.mission.profile.SuppliedPowerRatio(t),self.profile.Altitude(t),self.profile.Velocity(t),Ppropulsive)
            # print(self.aircraft.mission.profile.SuppliedPowerRatio(t), t)
            dEFdt = Ppropulsive * PRatio[0]
            dEBatdt = Ppropulsive * PRatio[5]
            self.Max_PBat = np.max([self.Max_PBat,dEBatdt])
            self.Max_PF = np.max([self.Max_PF,dEFdt])
            dbetadt = - dEFdt/(self.ef*self.WTO)            
            return [dEFdt,dEBatdt,dbetadt]

        # Takeoff condition
        Ppropulsive = self.WTO * self.aircraft.performance.TakeOff(self.aircraft.DesignWTOoS,self.aircraft.constraint.ConstraintsBeta[1], self.aircraft.constraint.ConstraintsAltitude[1], self.aircraft.constraint.kTO, self.aircraft.constraint.sTO, self.aircraft.constraint.DISA, self.aircraft.constraint.ConstraintsSpeed[1], self.aircraft.constraint.ConstraintsSpeedtype[1])
        PRatio = self.aircraft.powertrain.Hybrid(self.aircraft.mission.profile.SPW[0][0],self.aircraft.constraint.ConstraintsAltitude[1],self.aircraft.constraint.ConstraintsSpeed[1],Ppropulsive)
        self.TO_PBatoW = Ppropulsive * PRatio[5]
        self.TO_PFoW = Ppropulsive * PRatio[0]

        #set/reset max values
        self.Max_PBat = -1
        self.Max_PF = -1

        y0 = [0,0,self.beta0]
        
        # time = np.linspace(0,self.profile.MissionTime2,num=1000)
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
            y0 = [sol.y[0][-1],sol.y[1][-1],sol.y[2][-1]]
   
        # old tests
        # z = integrate.odeint(model,y0,self.t)
        # Ef, Beta = integrate.odeint(model,y0,time)
        
        # self.Ef = Ef[-1]
        # self.Beta = Beta[-1]
        self.Ef = sol.y[0]
        self.EBat = sol.y[1]
        self.Beta = sol.y[2]

        return self.Ef[-1], self.EBat[-1]
        
        
