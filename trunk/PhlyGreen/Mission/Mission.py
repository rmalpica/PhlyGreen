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

    def InitializeProfile(self):
        
        self.profile = Profile(self.aircraft)
        
        if self.aircraft.MissionType == 'Continue':
            self.profile.DefineMission()
        elif self.aircraft.MissionType == 'Discrete':
            self.profile.DefineDiscreteMission()
        
        # self.t = np.linspace(0,self.profile.MissionTime2,num=1000)


    def EvaluateMission(self,WTO):
        
        if self.aircraft.Configuration == 'Traditional':     
            if self.aircraft.MissionType == 'Continue':
                return self.TraditionalConfiguration(WTO)
            if self.aircraft.MissionType == 'Discrete':
                return self.DiscreteTraditional(WTO)
            
        elif self.aircraft.Configuration == 'Hybrid':     
            if self.aircraft.MissionType == 'Continue':
                return self.HybridConfiguration(WTO)
            if self.aircraft.MissionType == 'Discrete':
                return self.DiscreteHybrid(WTO)

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

        self.MissionTimes = times 

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
            
            Beta = y[2]
            Ppropulsive = PowerPropulsive(Beta,t)
            PRatio = self.aircraft.powertrain.Hybrid(self.aircraft.mission.profile.SuppliedPowerRatio(t),self.profile.Altitude(t),self.profile.Velocity(t),Ppropulsive)
            #print(self.aircraft.mission.profile.SuppliedPowerRatio(t), t)
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
   
        self.Ef = sol.y[0]
        self.EBat = sol.y[1]
        self.Beta = sol.y[2]

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
        
        


    def DiscreteTraditional(self,WTO):
        
        self.WTO = WTO

        def PowerPropulsive(Beta,i):

            PPoWTO = self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,Beta,self.profile.DiscretizedPowerExcess[i],1,self.profile.DiscretizedAltitudes[i],self.DISA,self.profile.DiscretizedVelocities[i],'TAS')

            return PPoWTO * WTO
                    

        def model(i,Beta):
            
            PP = PowerPropulsive(Beta,i) 
            #self.PP_values = np.append(self.PP_values,PP)
            PRatio = self.aircraft.powertrain.Traditional(self.profile.DiscretizedAltitudes[i],self.profile.DiscretizedVelocities[i],PP)
            #self.P_Ratio = np.append(self.P_Ratio,PRatio)
            dEdt = PP * PRatio[0]
            dbetadt = - dEdt/(self.ef*self.WTO)

            return [dEdt,dbetadt] 
        
        y0 = [0,self.beta0]
        

    
        self.E_values = np.array([0])
        self.beta_values = np.array([self.beta0])
        # self.PP_values = np.array([PowerPropulsive(self.beta0,0)])
        # self.P_Ratio = np.array([self.aircraft.powertrain.Traditional(self.profile.DiscretizedAltitudes[0],self.profile.DiscretizedVelocities[0],self.PP_values[0])])
        
        E = 0
        beta = self.beta0

        for i in range(1,len(self.profile.DiscretizedTime)):
            dEdt, dbetadt = model(i,self.beta_values[-1])
            

            dt = self.profile.DiscretizedTime[i] - self.profile.DiscretizedTime[i-1] 

            E += dt * dEdt
            beta += dt * dbetadt 

            self.E_values = np.append(self.E_values,E)
            self.beta_values = np.append(self.beta_values,beta)


        # Takeoff condition
        Ppropulsive = self.WTO * self.aircraft.performance.TakeOff(self.aircraft.DesignWTOoS,self.aircraft.constraint.TakeOffConstraints['Beta'], self.aircraft.constraint.TakeOffConstraints['Altitude'], self.aircraft.constraint.TakeOffConstraints['kTO'], self.aircraft.constraint.TakeOffConstraints['sTO'], self.aircraft.constraint.DISA, self.aircraft.constraint.TakeOffConstraints['Speed'], self.aircraft.constraint.TakeOffConstraints['Speed Type'])
        PRatio = self.aircraft.powertrain.Traditional(self.aircraft.constraint.TakeOffConstraints['Altitude'],self.aircraft.constraint.TakeOffConstraints['Speed'],Ppropulsive)
        self.TO_PP = Ppropulsive * PRatio[1] #shaft power 

        #set/reset max values
        self.Max_Peng = -1


        # compute peak Propulsive power along mission

        self.PP_values = []
        self.P_Ratio = []

        for i in range(len(self.profile.DiscretizedTime)):
            self.PP_values = np.append(self.PP_values,PowerPropulsive(self.beta_values[i],i))
            self.P_Ratio.append(self.aircraft.powertrain.Traditional(self.profile.DiscretizedAltitudes[i],self.profile.DiscretizedVelocities[i],self.PP_values[i])[1])


        self.Max_PEng = np.max(np.multiply(self.PP_values,self.P_Ratio)) #shaft power

        # sol = integrate.solve_ivp(model, [0., self.profile.DiscretizedTime[-1]], y0, t_eval=self.profile.DiscretizedTime)

        # self.Ef = sol.y[0] 
        
        return self.E_values[-1]
    



    def DiscreteHybrid(self,WTO):
        
        self.WTO = WTO
        
        
        def PowerPropulsive(Beta,i):

            PPoWTO = self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,Beta,self.profile.DiscretizedPowerExcess[i],1,self.profile.DiscretizedAltitudes[i],self.DISA,self.profile.DiscretizedVelocities[i],'TAS')

            return PPoWTO * WTO


        def model(i,Beta):
            
            PP = PowerPropulsive(Beta,i) 
            #self.PP_values = np.append(self.PP_values,PP)
            PRatio = self.aircraft.powertrain.Hybrid(self.aircraft.mission.profile.SuppliedPowerRatio(self.profile.DiscretizedTime[i]),self.profile.DiscretizedAltitudes[i],self.profile.DiscretizedVelocities[i],PP)
            #self.P_Ratio = np.append(self.P_Ratio,PRatio)
            dEFdt = PP * PRatio[0]
            dEBatdt = PP * PRatio[5]
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
        method= 'BDF'

        self.EF_values = np.array([0])
        self.EBat_values = np.array([0])
        self.beta_values = np.array([self.beta0])
        # self.PP_values = np.array([PowerPropulsive(self.beta0,0)])
        # self.P_Ratio = np.array([self.aircraft.powertrain.Traditional(self.profile.DiscretizedAltitudes[0],self.profile.DiscretizedVelocities[0],self.PP_values[0])])
        
        EF = 0
        EBat = 0
        beta = self.beta0

        for i in range(1,len(self.profile.DiscretizedTime)):
            dEFdt, dEBatdt, dbetadt = model(i,self.beta_values[-1])


            dt = self.profile.DiscretizedTime[i] - self.profile.DiscretizedTime[i-1] 

            EF += dt * dEFdt
            EBat += dt * dEBatdt
            beta += dt * dbetadt 

            self.EF_values = np.append(self.EF_values,EF)
            self.EBat_values = np.append(self.EBat_values,EBat)
            self.beta_values = np.append(self.beta_values,beta)




        self.PP_values = []
        self.P_RatioFuel = []
        self.P_RatioBattery = []

        for i in range(len(self.profile.DiscretizedTime)):
            self.PP_values = np.append(self.PP_values,PowerPropulsive(self.beta_values[i],i))
            self.P_RatioFuel.append(self.aircraft.powertrain.Hybrid(self.aircraft.mission.profile.SuppliedPowerRatio(self.profile.DiscretizedTime[i]),self.profile.DiscretizedAltitudes[i],self.profile.DiscretizedVelocities[i],self.PP_values[i])[1])
            self.P_RatioBattery.append(self.aircraft.powertrain.Hybrid(self.aircraft.mission.profile.SuppliedPowerRatio(self.profile.DiscretizedTime[i]),self.profile.DiscretizedAltitudes[i],self.profile.DiscretizedVelocities[i],self.PP_values[i])[5])


        self.Max_PEng = np.max(np.multiply(self.PP_values,self.P_RatioFuel)) 
        self.Max_PBat = np.max(np.multiply(self.PP_values,self.P_RatioBattery)) 

        return self.EF_values[-1], self.EBat_values[-1]
        