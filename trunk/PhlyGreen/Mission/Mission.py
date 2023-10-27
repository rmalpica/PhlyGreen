import numpy as np
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed
import scipy.integrate as integrate
from .Profile import Profile

class Mission:
  
    def __init__(self, aircraft):
        self.aircraft = aircraft
        self.WTO = None



    def EvaluateMission(self,WTO):
        self.WTO = WTO
        
        self.profile = Profile(self.aircraft)
        
        self.profile.ReadInput()
        # self.profile.DefineMission()
        self.profile.DefineMission2()
        
        def PF(Beta,t):

            PPoWTO = self.aircraft.performance.PoWTO(self.aircraft.constraint.DesignWTOoS,Beta,self.profile.PowerExcess2(t),1,self.profile.Altitude2(t),self.profile.DISA,self.profile.Velocity2(t),'TAS')
          
            return PPoWTO * self.aircraft.powertrain.Traditional()[0] * WTO


        
        def model(z,t):
            Beta = z[1]
            dEdt = PF(Beta,t)
            dbetadt = - PF(Beta,t)/(self.aircraft.ef*self.WTO)
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
        
    