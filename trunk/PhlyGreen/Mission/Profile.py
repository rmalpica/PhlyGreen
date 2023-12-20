import numpy as np
import numbers
import PhlyGreen.Utilities.Speed as Speed
import PhlyGreen.Utilities.Units as Units


class Profile:
    
    def __init__(self, aircraft):
        self.aircraft = aircraft
      
        self.MissionRange = None 
        self.DiversionRange = None 
        self.MissionStages = None 
        self.DiversionStages = None 
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
        
        self.HTDiversionClimb = []
        self.HTDiversionDescent = []
        self.BreaksDescentDiversion = [0]
        self.VClimbsDiversion = []
        self.VDescentsDiversion = []
        self.counterClimbDiversion = 0
        self.counterDescentDiversion = 0
        self.DistancesDiversion = []

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
        

    def DefineMission(self):
        
        self.SetInput()

        #parse all phases except cruise and takeoff
        for Stage in self.MissionStages:
            if ('Cruise' in Stage) or ('Takeoff' in Stage): 
                continue
            else:
                print(Stage)
                getattr(self, self.MissionStages[Stage]['type'])(self.MissionStages[Stage]['input'],'Mission')

        #parse cruise 
        for Stage in self.MissionStages:
            if 'Cruise' not in Stage: 
                continue
            else:
                print(Stage)
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


        self.MergeMission()


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
            
        self.MissionTime2 = self.Breaks[-1]
        self.Breaks.pop(-1)
            
        for i in range(len(self.BreaksDescentDiversion)):   
            self.HTMission.append(self.HTDiversionDescent[i])
            self.Velocities.append(self.VDescentsDiversion[i])



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
        
        