import numpy as np
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed
import scipy.integrate as integrate


class Mission:
  
    def __init__(self, aircraft):
        self.aircraft = aircraft
        self.WTO = None

    def ReadInput(self):
        
        self.H1 = self.aircraft.ConstraintsAltitude[2]
        self.H2 = self.aircraft.ConstraintsAltitude[0]
        self.H3 = self.aircraft.DiversionAltitude
        self.DISA = self.aircraft.DISA
        self.VClimb = self.aircraft.ConstraintsSpeed[2]
        self.VDescent = self.VClimb
        self.VCruise =  Speed.Mach2TAS(self.aircraft.ConstraintsSpeed[0], self.H2, self.DISA)
        self.DiversionMach = self.aircraft.DiversionMach
        self.DiversionVCruise = Speed.Mach2TAS(self.DiversionMach, self.H3,self.DISA)
        self.CB = self.aircraft.CB
        NMtoM = 1825 #Da spostare dentro Units.py
        self.MissionRange = self.aircraft.MissionRange*NMtoM    
        self.DiversionRange = self.aircraft.DiversionRange*NMtoM
        self.beta0 = self.aircraft.beta0
        self.ef = self.aircraft.ef
        
        
        
        return None
        
    def DefineMission(self):
                
        # Climb     
        self.HTClimb = self.CB * self.VClimb
        DHClimb = self.H2 - self.H1
        self.DTClimb = np.ceil(DHClimb/self.HTClimb)
        DRClimb = self.VClimb * self.DTClimb

        # Descent (Same of Climb, with negative PS)
        self.HTDescent = - self.CB * self.VDescent
        DHDescent = DHClimb
        self.DTDescent = np.ceil(np.abs(DHDescent/self.HTDescent))
        DRDescent = self.VDescent * self.DTDescent

        # Cruise
        DRCruise = self.MissionRange - DRClimb - DRDescent
        self.DTCruise = np.ceil(DRCruise/self.VCruise)
        
        # Diversion Climb
        DiversionDHClimb = self.H3 - self.H1
        self.DiversionDTClimb = np.ceil(DiversionDHClimb/self.HTClimb)
        DiversionDRClimb = self.VClimb * self.DiversionDTClimb
        
        # Diversion Descent
        DiversionDHDescent = DiversionDHClimb
        self.DiversionDTDescent = np.ceil(np.abs(DiversionDHDescent/self.HTDescent))
        DiversionDRDescent = self.VDescent * self.DiversionDTDescent
        
        # Diversion Cruise
        
        DiversionDRCruise = self.DiversionRange - DiversionDRClimb - DiversionDRDescent
        self.DiversionDTCruise = np.ceil(DiversionDRCruise/self.DiversionVCruise)
        
        
        self.T1 = self.DTClimb + self.DTCruise
        self.T2 = self.T1 + self.DTDescent
        self.T3 = self.T2 + self.DiversionDTClimb
        self.T4 = self.T3 + self.DiversionDTCruise
        self.TotalTime = self.T4 + self.DiversionDTDescent
        
        return None
    
    def Altitude(self,t):
        return np.piecewise(t, [t < self.DTClimb, ((t >= self.DTClimb) & (t < self.T1)), ((t >= self.T1) & (t < self.T2)), 
                                ((t >= self.T2) & (t < self.T3)), ((t >= self.T3) & (t < self.T4)), t >= self.T4], 
                            [lambda t : (self.H1+self.HTClimb*t), self.H2, lambda t : (self.H2+self.HTDescent*(t-self.T1)), 
                             lambda t : (self.H1+self.HTClimb*(t-self.T2)), self.H3, lambda t : (self.H3+self.HTDescent*(t-self.T4))])
    
    def PowerExcess(self,t):
        return np.piecewise(t, [t < self.DTClimb, ((t >= self.DTClimb) & (t < self.T1)), ((t >= self.T1) & (t < self.T2)), 
                                ((t >= self.T2) & (t < self.T3)), ((t >= self.T3) & (t < self.T4)), t >= self.T4], 
                            [self.HTClimb, 0, self.HTDescent, self.HTClimb, 0, self.HTDescent])

    def Velocity(self,t):
        return np.piecewise(t, [t < self.DTClimb, ((t >= self.DTClimb) & (t < self.T1)), ((t >= self.T1) & (t < self.T2)), 
                                ((t >= self.T2) & (t < self.T3)), ((t >= self.T3) & (t < self.T4)), t >= self.T4], 
                            [self.VClimb, self.VCruise, self.VDescent, self.VClimb, self.DiversionVCruise, self.VDescent])

    def EvaluateMission(self,WTO):
        self.WTO = WTO
        
        self.ReadInput()
        self.DefineMission()
        
        def PF(Beta,t):

            PPoWTO = self.aircraft.performance.PoWTO(self.aircraft.performance.DesignWTOoS,Beta,self.PowerExcess(t),1,self.Altitude(t),self.DISA,self.Velocity(t),'TAS')
          
            return PPoWTO * self.aircraft.powertrain.Traditional()[0] * WTO


        
        def model(z,t):
            Beta = z[1]
            dEdt = PF(Beta,t)
            dbetadt = - PF(Beta,t)/(self.ef*self.WTO)
            dzdt = [dEdt,dbetadt]
            return dzdt

        # initial condition
        z0 = [0,self.beta0]

        self.t = np.linspace(0,self.TotalTime,num=1000)
        

        # z = integrate.solve_ivp(model,[0, self.TotalTime],z0)
        z = integrate.odeint(model,z0,self.t)
        
        # Ef, Beta = integrate.odeint(model,z0,self.TotalTime)
 
        self.Ef = z[:,0]
        self.Beta = z[:,1]
        

        return self.Ef[-1]
        
    