import numpy as np
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed
import scipy.integrate as integrate
from .Profile import Profile

class Mission:
  
    def __init__(self, aircraft):
        self.aircraft = aircraft
        self.WTO = None
        self.Max_PBatoW = -1
        self.Max_PFoW = -1

    def ReadInput(self):
        
        self.ef = self.aircraft.TechnologyInput['Ef']

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
                return "Try a different configuration..."
  
  
    def TraditionalConfiguration(self,WTO):
 
        self.WTO = WTO
        
        
        def PF(Beta,t):

            PPoWTO = self.aircraft.performance.PoWTO(self.aircraft.constraint.DesignWTOoS,Beta,self.profile.PowerExcess(t),1,self.profile.Altitude(t),self.profile.DISA,self.profile.Velocity(t),'TAS')
          
            return PPoWTO * self.aircraft.powertrain.Traditional()[0] * WTO


        
        def model(t,y):
            Beta = y[1]
            dEdt = PF(Beta,t)
            # dbetadt = - PF(Beta,t)/(self.aircraft.ef*self.WTO)
            dbetadt = - dEdt/(self.ef*self.WTO)

            return [dEdt,dbetadt]

        # initial condition
        y0 = [0,self.profile.beta0]

        

        sol = integrate.solve_ivp(model,[0, self.profile.MissionTime2],y0)
        # z = integrate.odeint(model,z0,self.t)
        
        # Ef, Beta = integrate.odeint(model,z0,self.TotalTime)
 
        self.Ef = sol.y[0]
        self.Beta = sol.y[1]
        

        return self.Ef[-1]
    
    
    
    def HybridConfiguration(self,WTO):
        
        self.WTO = WTO
        
        
        def PP(Beta,t):

            PPoWTO = self.aircraft.performance.PoWTO(self.aircraft.constraint.DesignWTOoS,Beta,self.profile.PowerExcess(t),1,self.profile.Altitude(t),self.profile.DISA,self.profile.Velocity(t),'TAS')
          
            return PPoWTO * WTO

        
        def model(t,y):
            
            PRatio = self.aircraft.powertrain.Hybrid(self.aircraft.mission.profile.SuppliedPowerRatio(t))
            Beta = y[2]
            Ppropulsive = PP(Beta,t)
            # print(self.aircraft.mission.profile.SuppliedPowerRatio(t), t)
            dEFdt = Ppropulsive * PRatio[0]
            dEBatdt = Ppropulsive * PRatio[5]
            self.Max_PBatoW = np.max([self.Max_PBatoW,dEBatdt])
            self.Max_PFoW = np.max([self.Max_PFoW,dEFdt])
            dbetadt = - dEFdt/(self.ef*self.WTO)            
            return [dEFdt,dEBatdt,dbetadt]

        # initial condition
        self.Max_PBatoW = -1
        self.Max_PFoW = -1


        y0 = [0,0,self.profile.beta0]
        # z0 = [0,0,self.profile.beta0]
        
        # time = np.linspace(0,self.profile.MissionTime2,num=1000)
        rtol = 1e-5
        method= 'BDF'

        # sol = integrate.solve_ivp(model,[0, self.profile.MissionTime2],y0,method='BDF',rtol=1e-6)
        sol1 = integrate.solve_ivp(model,[0, self.profile.Breaks[1]],y0,method=method,rtol=rtol)
        sol2 = integrate.solve_ivp(model,[self.profile.Breaks[1], self.profile.Breaks[2]],[sol1.y[0][-1],sol1.y[1][-1],sol1.y[2][-1]],method=method,rtol=rtol)
        sol3 = integrate.solve_ivp(model,[self.profile.Breaks[2], self.profile.Breaks[3]],[sol2.y[0][-1],sol2.y[1][-1],sol2.y[2][-1]],method=method,rtol=rtol)
        sol4 = integrate.solve_ivp(model,[self.profile.Breaks[3], self.profile.Breaks[4]],[sol3.y[0][-1],sol3.y[1][-1],sol3.y[2][-1]],method=method,rtol=rtol)
        sol5 = integrate.solve_ivp(model,[self.profile.Breaks[4], self.profile.Breaks[5]],[sol4.y[0][-1],sol4.y[1][-1],sol4.y[2][-1]],method=method,rtol=rtol)
        sol6 = integrate.solve_ivp(model,[self.profile.Breaks[5], self.profile.MissionTime2],[sol5.y[0][-1],sol5.y[1][-1],sol5.y[2][-1]],method=method,rtol=rtol)


        # z = integrate.odeint(model,z0,self.t)
        # print(len(sol1.t)+len(sol2.t)+len(sol3.t)+len(sol4.t)+len(sol5.t)+len(sol6.t) )
        # print(sol1.t,sol2.t,sol3.t,sol4.t,sol5.t,sol6.t)

        # Ef, Beta = integrate.odeint(model,z0,time)
        
        # self.Ef = Ef[-1]
        # self.Beta = Beta[-1]
        self.Ef = sol6.y[0]
        self.EBat = sol6.y[1]
        self.Beta = sol6.y[2]

        return self.Ef[-1], self.EBat[-1]
        
        
