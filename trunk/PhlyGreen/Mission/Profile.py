import numpy as np
import numbers
import matplotlib.pyplot as plt
import PhlyGreen.Utilities.Speed as Speed
import PhlyGreen.Utilities.Units as Units
import PhlyGreen.Utilities.Atmosphere as ISA
import scipy.integrate as integrate


class Profile:
    
    def __init__(self, aircraft):
        self.aircraft = aircraft
      
        self.MissionRange = None 
        self.DiversionRange = None 
        self.MissionStages = None 
        self.DiversionStages = None
        self.LoiterStages = None
        self.TLoiter = None
        self.AltitudeLoiter = None  
        self.SPW = None 
        self.SPWinterp = None
        self.times = None

        self.Altitudes = []
        self.HTMissionClimb = []
        self.HTMissionDescent = []
        self.HTMission = []
        self.BreaksClimb = [0]
        self.BreaksDescent = [0]
        self.Breaks = [0]
        self.Distances = []
        self.counterClimb = 0
        self.counterDescent = 0
        self.VClimbs = []
        self.VDescents = []
        self.Velocities = []

        # For the discretized mission analysis  
        self.DiscretizedAltitudes = []
        self.DiscretizedVelocities = []
        self.DiscretizedPowerExcess = []
        self.DiscretizedTime = []

        self.TimesClimb = [0]
        self.TimesCruise = []
        self.TimesDescent = [0]
        self.TimesClimbDiversion = [0]
        self.TimesCruiseDiversion = []
        self.TimesDescentDiversion = [0]
        self.ClimbAltitudes = []
        self.CruiseAltitudes = []
        self.DescentAltitudes = []
        self.DiversionClimbAltitudes = []
        self.DiversionCruiseAltitudes = []
        self.DiversionDescentAltitudes = []
    

        
        self.HTDiversionClimb = []
        self.HTDiversionDescent = []
        self.BreaksDescentDiversion = [0]
        self.VClimbsDiversion = []
        self.VDescentsDiversion = []
        self.counterClimbDiversion = 0
        self.counterDescentDiversion = 0
        self.DistancesDiversion = []


        self.n_steps = 50

    """ Properties """

    @property
    def MissionRange(self):
        if self._MissionRange == None:
            raise ValueError("Mission Range unset. Exiting")
        return self._MissionRange
      
    @MissionRange.setter
    def MissionRange(self,value):
        self._MissionRange = value
        if(isinstance(value, numbers.Number) and (value <= 0)):
            raise ValueError("Error: Illegal mission range: %e. Exiting" %value)

    @property
    def DiversionRange(self):
        if self._DiversionRange== None:
            raise ValueError("Diversion Range unset. Exiting")
        return self._DiversionRange
      
    @DiversionRange.setter
    def DiversionRange(self,value):
        self._DiversionRange = value
        if(isinstance(value, numbers.Number) and (value <= 0)):
            raise ValueError("Error: Illegal diversion range: %e. Exiting" %value)

    @property
    def SPW(self):
        if len(self._SPW) == 0:
            raise ValueError("Supplied power ratio unset. Exiting")
        return self._SPW
      
    @SPW.setter
    def SPW(self,value):
        self._SPW = value
        if(isinstance(value, numbers.Number) and (value < 0 or value > 1)):
            raise ValueError("Error: Illegal Supplied power ratio: %e. Exiting" %value)

    """ Methods """

    def SetInput(self):
                
        self.MissionRange = Units.NMtoM(self.aircraft.MissionInput['Range Mission'])
        self.DiversionRange = Units.NMtoM(self.aircraft.MissionInput['Range Diversion'])
        self.MissionStages = self.aircraft.MissionStages
        self.DiversionStages = self.aircraft.DiversionStages
        if self.aircraft.LoiterStages is not None:
            self.LoiterStages = self.aircraft.LoiterStages 
            self.AltitudeLoiter = self.aircraft.LoiterStages['Cruise']['input']['Altitude'] 
            print(self.AltitudeLoiter)
            if 'Range Loiter' in self.aircraft.MissionInput:
                self.LoiterRange = Units.NMtoM(self.aircraft.MissionInput['Range Loiter'])
            elif 'Time Loiter' in self.aircraft.MissionInput:
                self.TLoiter = self.aircraft.MissionInput['Time Loiter']
            else:
                raise ValueError("Insert loiter range or duration ")
        

    def DefineMission(self):
        
        self.SetInput()

        #parse all phases except cruise and takeoff
        for Stage in self.MissionStages:
            if ('Cruise' in Stage) or ('Takeoff' in Stage): 
                continue
            else:
                getattr(self, self.MissionStages[Stage]['type'])(self.MissionStages[Stage]['input'],'Mission')

        #parse cruise 
        for Stage in self.MissionStages:
            if 'Cruise' not in Stage: 
                continue
            else:
                getattr(self, self.MissionStages[Stage]['type'])(self.MissionStages[Stage]['input'],'Mission')
        
        #parse supplied power ratios
        if self.aircraft.Configuration == 'Hybrid':
            for Stage in self.MissionStages: 
                if ('Takeoff') in Stage:
                    phiTO = self.MissionStages[Stage]['Supplied Power Ratio']['phi']
                    self.SPW = [[phiTO,phiTO]]
                else:
                    phi_start = self.MissionStages[Stage]['Supplied Power Ratio']['phi_start'] 
                    phi_end = self.MissionStages[Stage]['Supplied Power Ratio']['phi_end'] 
                    self.SPW = np.vstack([self.SPW,[phi_start,phi_end]])
        
        self.BreaksClimb.pop(0)
        self.BreaksDescent.pop(0)
        self.BreaksDescent += self.CruiseTime

        self.BreaksClimbDiversion = [self.BreaksDescent[-1]]

        #parse all phases except cruise and takeoff
        for Stage in self.DiversionStages:
            if ('Cruise' in Stage) or ('Takeoff' in Stage): 
                continue
            else:
                getattr(self, self.DiversionStages[Stage]['type'])(self.DiversionStages[Stage]['input'],'Diversion')

        #parse cruise 
        for Stage in self.DiversionStages:
            if 'Cruise' not in Stage: 
                continue
            else:
                getattr(self, self.DiversionStages[Stage]['type'])(self.DiversionStages[Stage]['input'],'Diversion')
        
        #parse supplied power ratios
        if self.aircraft.Configuration == 'Hybrid':
            for Stage in self.DiversionStages: 
                if ('Takeoff') in Stage:
                    pass
                else:
                    phi_start = self.DiversionStages[Stage]['Supplied Power Ratio']['phi_start'] 
                    phi_end = self.DiversionStages[Stage]['Supplied Power Ratio']['phi_end'] 
                    self.SPW = np.vstack([self.SPW,[phi_start,phi_end]])

        self.BreaksClimbDiversion.pop(0)
        self.BreaksDescentDiversion.pop(0)
        self.BreaksDescentDiversion += self.CruiseTimeDiversion

        if self.LoiterStages is not None:
            getattr(self, self.LoiterStages['Cruise']['type'])(self.LoiterStages['Cruise']['input'],'Loiter')

        #parse supplied power ratio for loiter phase
        
            if self.aircraft.Configuration == 'Hybrid':

                phi_start = self.LoiterStages['Cruise']['Supplied Power Ratio']['phi_start'] 
                phi_end = self.LoiterStages['Cruise']['Supplied Power Ratio']['phi_end'] 
                self.SPW = np.vstack([self.SPW,[phi_start,phi_end]])




        self.MergeMission()


        self.times = np.append(self.Breaks,self.MissionTime2)
        # print(self.times)
        self.SPWinterp = [lambda t,coef=i: np.interp(t, [self.times[coef], self.times[coef+1]], self.SPW[coef+1])  for i in range(len(self.times)-1)]

        return None
    


     
    def DefineDiscreteMission(self):
        
        self.SetInput()

        #parse all phases except cruise and takeoff
        for Stage in self.MissionStages:
            if ('Cruise' in Stage) or ('Takeoff' in Stage): 
                continue
            else:
                getattr(self, self.MissionStages[Stage]['type'])(self.MissionStages[Stage]['input'],'Mission')

        #parse cruise 
        for Stage in self.MissionStages:
            if 'Cruise' not in Stage: 
                continue
            else:
                getattr(self, self.MissionStages[Stage]['type'])(self.MissionStages[Stage]['input'],'Mission')
        
        #parse supplied power ratios
        if self.aircraft.Configuration == 'Hybrid':
            for Stage in self.MissionStages: 
                if ('Takeoff') in Stage:
                    phiTO = self.MissionStages[Stage]['Supplied Power Ratio']['phi']
                    self.SPW = [[phiTO,phiTO]]
                else:
                    phi_start = self.MissionStages[Stage]['Supplied Power Ratio']['phi_start'] 
                    phi_end = self.MissionStages[Stage]['Supplied Power Ratio']['phi_end'] 
                    self.SPW = np.vstack([self.SPW,[phi_start,phi_end]])
        
        self.BreaksClimb = np.delete(self.BreaksClimb,0)
        self.BreaksDescent = np.delete(self.BreaksDescent,0)
        self.BreaksDescent += self.TimesCruise[-1]

        self.BreaksClimbDiversion = [self.BreaksDescent[-1]]

        #parse all phases except cruise and takeoff
        for Stage in self.DiversionStages:
            if ('Cruise' in Stage) or ('Takeoff' in Stage): 
                continue
            else:
                getattr(self, self.DiversionStages[Stage]['type'])(self.DiversionStages[Stage]['input'],'Diversion')

        #parse cruise 
        for Stage in self.DiversionStages:
            if 'Cruise' not in Stage: 
                continue
            else:
                getattr(self, self.DiversionStages[Stage]['type'])(self.DiversionStages[Stage]['input'],'Diversion')
        
        #parse supplied power ratios
        if self.aircraft.Configuration == 'Hybrid':
            for Stage in self.DiversionStages: 
                if ('Takeoff') in Stage:
                    pass
                else:
                    phi_start = self.DiversionStages[Stage]['Supplied Power Ratio']['phi_start'] 
                    phi_end = self.DiversionStages[Stage]['Supplied Power Ratio']['phi_end'] 
                    self.SPW = np.vstack([self.SPW,[phi_start,phi_end]])

        self.BreaksClimbDiversion = np.delete(self.BreaksClimbDiversion,0)
        self.BreaksClimbDiversion += self.BreaksDescent[-1] 
        self.BreaksDescentDiversion = np.delete(self.BreaksDescentDiversion,0) 
        self.BreaksDescentDiversion += self.BreaksClimbDiversion[-1] + self.TimesCruiseDiversion[-1]

        if self.LoiterStages is not None:
            getattr(self, self.LoiterStages['Cruise']['type'])(self.LoiterStages['Cruise']['input'],'Loiter')

        #parse supplied power ratio for loiter phase
        
            if self.aircraft.Configuration == 'Hybrid':

                phi_start = self.LoiterStages['Cruise']['Supplied Power Ratio']['phi_start'] 
                phi_end = self.LoiterStages['Cruise']['Supplied Power Ratio']['phi_end'] 
                self.SPW = np.vstack([self.SPW,[phi_start,phi_end]])


        self.MergeDiscreteMission()


        self.times = np.append(self.Breaks,self.MissionTime2)
        self.SPWinterp = [lambda t,coef=i: np.interp(t, [self.times[coef], self.times[coef+1]], self.SPW[coef+1])  for i in range(len(self.times)-1)]

        return None


    def MergeMission(self):
        
        for i in range(len(self.BreaksClimb)):
            self.Breaks.append(self.BreaksClimb[i])
            self.HTMission.append(self.HTMissionClimb[i])
            self.Velocities.append(self.VClimbs[i])
        
        self.Breaks.append(self.CruiseTime)
        self.HTMission.append(0)
        self.Velocities.append(self.VCruise)
            
        for i in range(len(self.BreaksDescent)):  
            self.Breaks.append(self.BreaksDescent[i])
            
        self.MissionTime = self.Breaks[-1]
        # self.Breaks.pop(-1)
            
        for i in range(len(self.BreaksDescent)):   
            self.HTMission.append(self.HTMissionDescent[i])
            self.Velocities.append(self.VDescents[i])

        for i in range(len(self.BreaksClimbDiversion)):
            self.Breaks.append(self.BreaksClimbDiversion[i])
            self.HTMission.append(self.HTDiversionClimb[i])
            self.Velocities.append(self.VClimbsDiversion[i])
            
        self.Breaks.append(self.CruiseTimeDiversion)
        self.HTMission.append(0)
        self.Velocities.append(self.VCruiseDiversion)
        
        for i in range(len(self.BreaksDescentDiversion)):   # L'ultimo tempo non mi interessa
            self.Breaks.append(self.BreaksDescentDiversion[i])
            self.HTMission.append(self.HTDiversionDescent[i])
            self.Velocities.append(self.VDescentsDiversion[i])

        if self.LoiterStages is not None:

            self.Breaks.append(self.Breaks[-1] + self.DTLoiter)
            self.HTMission.append(0)
            self.Velocities.append(self.VCruiseLoiter)

        self.MissionTime2 = self.Breaks[-1]
        self.Breaks.pop(-1)






    def Altitude_Func(self,t):
        AltitudeFunctions=[]
        
          # Climb Mission        
        
        for i in range(len(self.BreaksClimb)):
            
            def localFunctionClimb(t):
                alt = self.Altitudes[i]
                htm = self.HTMission[i]
                brk = self.Breaks[i]
            
                return (lambda t : (alt + htm * (t - brk)))
            
            AltitudeFunctions.append(localFunctionClimb(t))
            
            
            # Cruise Mission
        AltitudeFunctions.append( self.Altitudes[len(self.BreaksClimb)]) # ATTENZIONE!!! NON VALE SE L'ALTITUDINE CAMBIA IN CROCIERA
                    
            # Descent Mission
        for i in range(len(self.BreaksDescent)):
            
            def localFunctionDescent(t):
                alt = self.Altitudes[i + len(self.BreaksClimb)]
                htm = self.HTMission[i + len(self.BreaksClimb) + 1]
                brk = self.Breaks[i + len(self.BreaksClimb) + 1]
                            
                return (lambda t : (alt + htm * (t - brk)))
                
            AltitudeFunctions.append(localFunctionDescent(t))
                
                
        # Climb Diversion       
               
        for i in range(len(self.BreaksClimbDiversion)):
                   
            def localFunctionClimb(t):
                alt = self.Altitudes[i + len(self.BreaksClimb) + len(self.BreaksDescent)]
                htm = self.HTMission[i + len(self.BreaksClimb) + len(self.BreaksDescent) + 1]
                brk = self.Breaks[i + len(self.BreaksClimb) + len(self.BreaksDescent) + 1]
                   
                return (lambda t : (alt + htm * (t - brk)))
                   
            AltitudeFunctions.append(localFunctionClimb(t))

            # Cruise Diversion
        AltitudeFunctions.append( self.Altitudes[len(self.BreaksClimb) + len(self.BreaksDescent) + len(self.BreaksClimbDiversion)]) # ATTENZIONE!!! NON VALE SE L'ALTITUDINE CAMBIA IN CROCIERA
                
                
            # Descent Diversion
        for i in range(len(self.BreaksDescent)):
            
            def localFunctionDescent(t):
                alt = self.Altitudes[i + len(self.BreaksClimb) + len(self.BreaksDescent) + len(self.BreaksClimbDiversion)]
                htm = self.HTMission[i + len(self.BreaksClimb) + len(self.BreaksDescent) + len(self.BreaksClimbDiversion) + 2]
                brk = self.Breaks[i + len(self.BreaksClimb) + len(self.BreaksDescent) + len(self.BreaksClimbDiversion) + 2]
                            
                return (lambda t : (alt + htm * (t - brk)))
                
            AltitudeFunctions.append(localFunctionDescent(t))                

        if self.LoiterStages is not None:
            
            AltitudeFunctions.append(self.AltitudeLoiter) 
 
        return AltitudeFunctions



    def Altitude(self,t):
        return np.piecewise(t, [ t >= ti for ti in self.Breaks], self.Altitude_Func(t))

    def PowerExcess(self,t):
        return np.piecewise(t, [ t >= ti for ti in self.Breaks], self.HTMission)
    
    def Velocity(self,t):
        return np.piecewise(t, [ t >= ti for ti in self.Breaks], self.Velocities)

    def SuppliedPowerRatio(self,t):
        idx=np.piecewise(t, [ self.times[i] <= t < self.times[i+1] for i in range(len(self.times)-1)], [i for i in range(len(self.times)-1)])
        return self.SPWinterp[idx.astype(int)](t) 


# Flight segments

    def ConstantRateClimb(self,StageInput,phase):
        
        StartAltitude = StageInput['StartAltitude']
        self.Altitudes.append(StartAltitude)
        EndAltitude = StageInput['EndAltitude']
        CB = StageInput['CB']
        VClimb = StageInput['Speed']

        HTClimb = CB * VClimb
        DHClimb = EndAltitude - StartAltitude
        DTClimb = np.ceil(DHClimb/HTClimb)
        DRClimb = VClimb * DTClimb

        # Devo definire un punto di break
    
        if (phase == 'Mission'):    
    
            self.BreaksClimb.append(DTClimb + self.BreaksClimb[self.counterClimb])
            self.Distances.append(DRClimb)
            self.HTMissionClimb.append(HTClimb)
            self.VClimbs.append(VClimb)
        
            self.counterClimb += 1
            
        if (phase == 'Diversion'):    
    
            self.BreaksClimbDiversion.append(DTClimb + self.BreaksClimbDiversion[self.counterClimbDiversion] )
            self.DistancesDiversion.append(DRClimb)
            self.HTDiversionClimb.append(HTClimb)
            self.VClimbsDiversion.append(VClimb)
        
            self.counterClimbDiversion += 1
        
        
    

    def ConstantMachCruise(self,StageInput,phase):
        
        Altitude = StageInput['Altitude']
        Mach = StageInput['Mach']

        if (phase == 'Mission'):
            
            self.VCruise = Speed.Mach2TAS(Mach, Altitude)
            
          
            DRCruise = self.MissionRange - np.sum(self.Distances)
            DTCruise = np.ceil(DRCruise/self.VCruise)
                
            self.CruiseTime = DTCruise + self.BreaksClimb[-1]
        
        if (phase == 'Diversion'):
            
            self.VCruiseDiversion = Speed.Mach2TAS(Mach, Altitude)
            
            DRCruise = self.DiversionRange - np.sum(self.DistancesDiversion)
            DTCruise = np.ceil(DRCruise/self.VCruiseDiversion)
                
            self.CruiseTimeDiversion = DTCruise + self.BreaksClimbDiversion[-1] 
        
        if (phase == 'Loiter'):

            self.VCruiseLoiter = Speed.Mach2TAS(Mach, Altitude)

            if self.TLoiter is not None:
                self.DTLoiter = self.TLoiter*60. #From minutes to seconds

            elif self.LoiterRange is not None:
                self.DTLoiter = np.ceil(self.LoiterRange/self.VCruiseLoiter)
    

            
        
        
    def ConstantRateDescent(self,StageInput,phase):
                
        StartAltitude = StageInput['StartAltitude']
        self.Altitudes.append(StartAltitude)
        EndAltitude = StageInput['EndAltitude']
        CB = StageInput['CB']
        VDescent = StageInput['Speed']

        HTDescent = CB * VDescent
        DHDescent = StartAltitude - EndAltitude
        DTDescent = np.ceil(np.abs(DHDescent/HTDescent))
        DRDescent = VDescent * DTDescent

        
        # Devo definire un punto di break
    
        if (phase == 'Mission'):
            
            self.BreaksDescent.append(DTDescent + self.BreaksDescent[self.counterDescent])
            self.Distances.append(DRDescent)
            self.HTMissionDescent.append(HTDescent)
            self.VDescents.append(VDescent)
        
            self.counterDescent += 1
        
        if (phase == 'Diversion'):
            
            self.BreaksDescentDiversion.append(DTDescent + self.BreaksDescentDiversion[self.counterDescentDiversion])
            self.DistancesDiversion.append(DRDescent)
            self.HTDiversionDescent.append(HTDescent)
            self.VDescentsDiversion.append(VDescent)
        
            self.counterDescentDiversion += 1
        
        





    def OptimumClimb(self,StageInput,phase):

        StartAltitude = StageInput['StartAltitude']
        self.Altitudes.append(StartAltitude)
        EndAltitude = StageInput['EndAltitude'] 
        CB = StageInput['CB'] 

        # The initial value problem is T = f(H), hereafter t symbolizes the altitude         
        
        def OptimalVelocity(H):
            return np.sqrt((2.*self.aircraft.DesignWTOoS/ISA.atmosphere.RHOstd(H,self.aircraft.constraint.DISA))*np.sqrt(self.aircraft.aerodynamics.ki()/(3.*self.aircraft.aerodynamics.Cd_0))) 

        def model(t,H):
            V = OptimalVelocity(t)
            dtdh = 1./(CB*V)
            return dtdh

        if (phase == 'Mission'):
            y0 = [self.TimesClimb[-1]]
        elif (phase == 'Diversion'):
            y0 = [self.TimesClimbDiversion[-1]]



        t_eval = np.linspace(StartAltitude, EndAltitude, self.n_steps)
        sol = integrate.solve_ivp(model,[StartAltitude, EndAltitude],y0,t_eval=t_eval) 
        
        DiscretizedAltitudes = sol.t
        DiscretizedVelocities = []
        DiscretizedPowerExcess = []
        for i in range(len(DiscretizedAltitudes)):
            DiscretizedVelocities.append(OptimalVelocity(DiscretizedAltitudes[i]))
            DiscretizedPowerExcess.append(OptimalVelocity(DiscretizedAltitudes[i])*CB)

        Range = integrate.simpson(DiscretizedVelocities,x=sol.y[0])
        
        if (phase == 'Mission'):    
    
            self.BreaksClimb = np.append(self.BreaksClimb,sol.y[0][-1])
            self.TimesClimb = np.append(self.TimesClimb,sol.y[0][1::])
            self.Distances.append(Range)
            
            if self.counterClimb > 0:
                DiscretizedVelocities.pop(0)
                DiscretizedPowerExcess.pop(0)
                DiscretizedAltitudes = np.delete(DiscretizedAltitudes,0)
            
            self.VClimbs = np.append(self.VClimbs, DiscretizedVelocities)
            self.HTMissionClimb = np.append(self.HTMissionClimb,DiscretizedPowerExcess)
            self.ClimbAltitudes = np.append(self.ClimbAltitudes, DiscretizedAltitudes)
        
            self.counterClimb += 1
            
        if (phase == 'Diversion'):    
    
            self.BreaksClimbDiversion = np.append(self.BreaksClimbDiversion, sol.y[0][-1])
            self.TimesClimbDiversion = np.append(self.TimesClimbDiversion,sol.y[0][1::])
            self.DistancesDiversion.append(Range)

            if self.counterClimbDiversion > 0:
                DiscretizedVelocities.pop(0)
                DiscretizedPowerExcess.pop(0)
                DiscretizedAltitudes = np.delete(DiscretizedAltitudes,0)


            self.HTDiversionClimb = np.append(self.HTDiversionClimb, DiscretizedPowerExcess)
            self.VClimbsDiversion = np.append(self.VClimbsDiversion, DiscretizedVelocities)
            self.DiversionClimbAltitudes = np.append(self.DiversionClimbAltitudes, DiscretizedAltitudes)
        
            self.counterClimbDiversion += 1






    def OptimumDescent(self,StageInput,phase):

        StartAltitude = StageInput['StartAltitude']
        self.Altitudes.append(StartAltitude)
        EndAltitude = StageInput['EndAltitude'] 
        CB = StageInput['CB'] 

        # The initial value problem is T = f(H), hereafter t symbolizes the altitude         
        
        def OptimalVelocity(H):
            return np.sqrt((2.*self.aircraft.DesignWTOoS/ISA.atmosphere.RHOstd(H,self.aircraft.constraint.DISA))*np.sqrt(self.aircraft.aerodynamics.ki()/(3.*self.aircraft.aerodynamics.Cd_0))) 

        def model(t,H):
            V = OptimalVelocity(t)
            dtdh = 1./(CB*V)
            return dtdh


        if (phase == 'Mission'):
            y0 = [self.TimesDescent[-1]]
        elif (phase == 'Diversion'):
            y0 = [self.TimesDescentDiversion[-1]]

        t_eval = np.linspace(StartAltitude, EndAltitude, self.n_steps)
        sol = integrate.solve_ivp(model,[StartAltitude, EndAltitude],y0,t_eval=t_eval) 
        
        DiscretizedAltitudes = sol.t
        DiscretizedVelocities = []
        DiscretizedPowerExcess = []
        for i in range(len(DiscretizedAltitudes)):
            DiscretizedVelocities.append(OptimalVelocity(DiscretizedAltitudes[i]))
            DiscretizedPowerExcess.append(OptimalVelocity(DiscretizedAltitudes[i])*CB)

        Range = integrate.simpson(DiscretizedVelocities,x=sol.y[0])
        
        if (phase == 'Mission'):    

            self.BreaksDescent = np.append(self.BreaksDescent, sol.y[0][-1])
            self.TimesDescent = np.append(self.TimesDescent,sol.y[0][1::])
            self.Distances.append(Range)

            if self.counterDescent > 0:
                DiscretizedVelocities.pop(0)
                DiscretizedPowerExcess.pop(0)
                DiscretizedAltitudes = np.delete(DiscretizedAltitudes,0)

            self.HTMissionDescent = np.append(self.HTMissionDescent, DiscretizedPowerExcess)
            self.VDescents = np.append(self.VDescents, DiscretizedVelocities)
            self.DescentAltitudes = np.append(self.DescentAltitudes, DiscretizedAltitudes)

            self.counterDescent += 1
            
        if (phase == 'Diversion'):    
    
            self.BreaksDescentDiversion = np.append(self.BreaksDescentDiversion,sol.y[0][-1])
            self.TimesDescentDiversion = np.append(self.TimesDescentDiversion,sol.y[0][1::])
            self.DistancesDiversion.append(Range)

            if self.counterDescentDiversion > 0:
                DiscretizedVelocities.pop(0)
                DiscretizedPowerExcess.pop(0)
                DiscretizedAltitudes = np.delete(DiscretizedAltitudes,0)

            self.HTDiversionDescent = np.append(self.HTDiversionDescent, DiscretizedPowerExcess)
            self.VDescentsDiversion = np.append(self.VDescentsDiversion, DiscretizedVelocities)
            self.DiversionDescentAltitudes = np.append(self.DiversionDescentAltitudes, DiscretizedAltitudes)

            self.counterDescentDiversion += 1



    def DiscretizedCruise(self,StageInput,phase):
        
        Altitude = StageInput['Altitude']
        Mach = StageInput['Mach']

        steps = np.ones(self.n_steps)


        if (phase == 'Mission'):
            
            self.VCruise = Speed.Mach2TAS(Mach, Altitude)*steps
            self.CruiseAltitudes = Altitude*steps 
          
            DRCruise = self.MissionRange - np.sum(self.Distances)
                
            self.TimesCruise = np.linspace(self.TimesClimb[-1], np.ceil(DRCruise/self.VCruise[0]) + self.TimesClimb[-1], self.n_steps)
        
        if (phase == 'Diversion'):
            
            self.VCruiseDiversion = Speed.Mach2TAS(Mach, Altitude)*steps
            self.DiversionCruiseAltitudes = Altitude*steps

            DRCruise = self.DiversionRange - np.sum(self.DistancesDiversion)
                
            self.TimesCruiseDiversion = np.linspace(0, np.ceil(DRCruise/self.VCruise[0]), self.n_steps)
        
        if (phase == 'Loiter'): 

            def OptimalVelocity(H):
                return np.sqrt((2.*self.aircraft.DesignWTOoS/ISA.atmosphere.RHOstd(H,self.aircraft.constraint.DISA))*np.sqrt(self.aircraft.aerodynamics.ki()/(3.*self.aircraft.aerodynamics.Cd_0))) 


            self.VCruiseLoiter = OptimalVelocity(Altitude)*steps
            self.LoiterAltitudes = Altitude*steps

            if self.TLoiter is not None:
                self.TimeLoiter = np.linspace(0,self.TLoiter*60.,self.n_steps) #From minutes to seconds

            elif self.LoiterRange is not None:
                self.TimeLoiter = np.linspace(0.,np.ceil(self.LoiterRange/self.VCruiseLoiter,self.n_steps))





    def MergeDiscreteMission(self):
        
        # CLIMB

        self.DiscretizedAltitudes = np.append(self.DiscretizedAltitudes, self.ClimbAltitudes)
        self.DiscretizedVelocities = np.append(self.DiscretizedVelocities, self.VClimbs)
        self.DiscretizedPowerExcess = np.append(self.DiscretizedPowerExcess, self.HTMissionClimb)
        self.DiscretizedTime = np.append(self.DiscretizedTime, self.TimesClimb)
        
        # CRUISE

        self.DiscretizedAltitudes = np.append(self.DiscretizedAltitudes, self.CruiseAltitudes)
        self.DiscretizedVelocities = np.append(self.DiscretizedVelocities, self.VCruise)
        self.DiscretizedPowerExcess = np.append(self.DiscretizedPowerExcess, np.zeros(len(self.VCruise)))
        self.DiscretizedTime = np.append(self.DiscretizedTime, self.TimesCruise) 

        # DESCENT

        self.TimesDescent += self.TimesCruise[-1]

        self.DiscretizedAltitudes = np.append(self.DiscretizedAltitudes, self.DescentAltitudes)
        self.DiscretizedVelocities = np.append(self.DiscretizedVelocities, self.VDescents)
        self.DiscretizedPowerExcess = np.append(self.DiscretizedPowerExcess, self.HTMissionDescent)
        self.DiscretizedTime = np.append(self.DiscretizedTime, self.TimesDescent) 
        
        # CLIMB DIVERSION

        self.TimesClimbDiversion += self.TimesDescent[-1]

        self.DiscretizedAltitudes = np.append(self.DiscretizedAltitudes, self.DiversionClimbAltitudes)
        self.DiscretizedVelocities = np.append(self.DiscretizedVelocities, self.VClimbsDiversion)
        self.DiscretizedPowerExcess = np.append(self.DiscretizedPowerExcess, self.HTDiversionClimb)
        self.DiscretizedTime = np.append(self.DiscretizedTime, self.TimesClimbDiversion) 

        # CRUISE DIVERSION 

        self.TimesCruiseDiversion += self.TimesClimbDiversion[-1]

        self.DiscretizedAltitudes = np.append(self.DiscretizedAltitudes, self.DiversionCruiseAltitudes)
        self.DiscretizedVelocities = np.append(self.DiscretizedVelocities, self.VCruiseDiversion)
        self.DiscretizedPowerExcess = np.append(self.DiscretizedPowerExcess, np.zeros(len(self.VCruiseDiversion)))
        self.DiscretizedTime = np.append(self.DiscretizedTime, self.TimesCruiseDiversion) 

        # DESCENT DIVERSION

        self.TimesDescentDiversion += self.TimesCruiseDiversion[-1]

        self.DiscretizedAltitudes = np.append(self.DiscretizedAltitudes, self.DiversionDescentAltitudes)
        self.DiscretizedVelocities = np.append(self.DiscretizedVelocities, self.VDescentsDiversion)
        self.DiscretizedPowerExcess = np.append(self.DiscretizedPowerExcess, self.HTDiversionDescent)
        self.DiscretizedTime = np.append(self.DiscretizedTime, self.TimesDescentDiversion) 

        if self.LoiterStages is not None:

            self.TimeLoiter += self.TimesDescentDiversion[-1]

            self.DiscretizedAltitudes = np.append(self.DiscretizedAltitudes, self.LoiterAltitudes)
            self.DiscretizedVelocities = np.append(self.DiscretizedVelocities, self.VCruiseLoiter)
            self.DiscretizedPowerExcess = np.append(self.DiscretizedPowerExcess, np.zeros(len(self.VCruiseLoiter)))
            self.DiscretizedTime = np.append(self.DiscretizedTime, self.TimeLoiter)  

        self.Breaks = np.append(self.Breaks, self.BreaksClimb)
        self.Breaks = np.append(self.Breaks, self.TimesCruise[-1])
        self.Breaks = np.append(self.Breaks, self.BreaksDescent)
        self.Breaks = np.append(self.Breaks, self.BreaksClimbDiversion)
        self.Breaks = np.append(self.Breaks, self.TimesCruiseDiversion[-1])
        self.Breaks = np.append(self.Breaks, self.BreaksDescentDiversion)

        if self.LoiterStages is not None:


            self.Breaks = np.append(self.Breaks, self.TimeLoiter[-1])

        self.MissionTime2 = self.Breaks[-1]
        self.Breaks = np.delete(self.Breaks, -1)

        
        return None
        
