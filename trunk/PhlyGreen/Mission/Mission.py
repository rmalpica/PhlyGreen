import numpy as np
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed
import scipy.integrate as integrate
from .Profile import Profile

class Mission:
  
    def __init__(self, aircraft):
        self.aircraft = aircraft
        self.WTO = None

    def ReadInput(self):
        
        self.ef = self.aircraft.TechnologyInput['Ef']

    def InitializeProfile(self):
        
        self.profile = Profile(self.aircraft)
        
        self.profile.DefineMission()

    def EvaluateMission(self,WTO):
        
        match self.aircraft.Configuration:     # DA PYTHON 3.10 IN POI.......
            
            case 'Traditional':
                
                return self.TraditionalConfiguration(WTO)
            
            
            case 'Hybrid':
                
                return self.HybridConfiguration(WTO)

            case _:
                return "Try a different configuration..."
  
    def TraditionalConfiguration(self,WTO):
        
        self.WTO = WTO
  
    def TraditionalConfiguration(self,WTO):
 
        self.WTO = WTO
        
        
        def PF(Beta,t):

            PPoWTO = self.aircraft.performance.PoWTO(self.aircraft.constraint.DesignWTOoS,Beta,self.profile.PowerExcess(t),1,self.profile.Altitude(t),self.profile.DISA,self.profile.Velocity(t),'TAS')
          
            return PPoWTO * self.aircraft.powertrain.Traditional()[0] * WTO


        
        def model(z,t):
            Beta = z[1]
            dEdt = PF(Beta,t)
            # dbetadt = - PF(Beta,t)/(self.aircraft.ef*self.WTO)
            dbetadt = - dEdt/(self.ef*self.WTO)

            dzdt = [dEdt,dbetadt]
            return dzdt

        # initial condition
        z0 = [0,self.profile.beta0]

        self.t = np.linspace(0,self.profile.MissionTime2,num=1000)
        

        # z = integrate.solve_ivp(model,[0, self.TotalTime],z0)
        z = integrate.odeint(model,z0,self.t)
        
        # Ef, Beta = integrate.odeint(model,z0,self.TotalTime)
 
        self.Ef = z[:,0]
        self.Beta = z[:,1]
        

        return self.Ef[-1]
    
    
    
    def HybridConfiguration(self,WTO):
        
        self.WTO = WTO
        
        
        def PP(Beta,t):

            PPoWTO = self.aircraft.performance.PoWTO(self.aircraft.constraint.DesignWTOoS,Beta,self.profile.PowerExcess(t),1,self.profile.Altitude(t),self.profile.DISA,self.profile.Velocity(t),'TAS')
          
            return PPoWTO * WTO

        
        def model(z,t):
            
            PRatio = self.aircraft.powertrain.Hybrid(t)
            Beta = z[2]
            Ppropulsive = PP(Beta,t)
            dEFdt = Ppropulsive * PRatio[0]
            dEBatdt = Ppropulsive * PRatio[5]
            # dbetadt = - PF(Beta,t)/(self.aircraft.ef*self.WTO)
            dbetadt = - dEFdt/(self.ef*self.WTO)
            dzdt = [dEFdt,dEBatdt,dbetadt]
            return dzdt

        # initial condition
        z0 = [0,0,self.profile.beta0]

        self.t = np.linspace(0,self.profile.MissionTime2,num=1000)
        

        # z = integrate.solve_ivp(model,[0, self.TotalTime],z0)
        z = integrate.odeint(model,z0,self.t)
        
        # Ef, Beta = integrate.odeint(model,z0,self.TotalTime)
 
        self.Ef = z[:,0]
        self.EBat = z[:,1]
        self.Beta = z[:,2]
        

        return self.Ef[-1], self.EBat[-1]
        
        
    
    def SerialHybridConfiguration(self,WTO):
        
        return None