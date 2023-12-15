import numpy as np
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
        
    def ReadInput(self):
                
        self.MissionRange = Units.NMtoM(self.aircraft.MissionInput['Range Mission'])
        self.DiversionRange = Units.NMtoM(self.aircraft.MissionInput['Range Diversion'])
        self.MissionStages = self.aircraft.MissionStages
        self.DiversionStages = self.aircraft.DiversionStages
        
        if (self.aircraft.Configuration == 'Hybrid'):
            self.SPW = self.aircraft.TechnologyInput['Supplied Power Ratio']
        

    def DefineMission(self):
        
        self.ReadInput()
        
        for Stage in self.MissionStages:
    
            getattr(self, self.MissionStages[Stage]['type'])(self.MissionStages[Stage]['input'],'Mission')
            
        self.BreaksClimb.pop(0)
        self.BreaksDescent.pop(0)
        self.BreaksDescent += self.CruiseTime

        self.BreaksClimbDiversion = [self.BreaksDescent[-1]]

        for Stage in self.DiversionStages:
    
            getattr(self, self.DiversionStages[Stage]['type'])(self.DiversionStages[Stage]['input'],'Diversion')

        self.BreaksClimbDiversion.pop(0)
        self.BreaksDescentDiversion.pop(0)
        self.BreaksDescentDiversion += self.CruiseTimeDiversion


        self.MergeMission()


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
        
        
        return np.piecewise(t, [t >= 0, t >= self.BreaksClimb[-1], t >= self.CruiseTime, t >= self.BreaksDescent[-1], t >= self.BreaksClimbDiversion[-1], t >= self.CruiseTimeDiversion], 
                            [lambda t: np.interp(t, [0, self.BreaksClimb[-1]], self.SPW[0]),
                             lambda t: np.interp(t, [self.BreaksClimb[-1], self.CruiseTime], self.SPW[1]),
                             lambda t: np.interp(t, [self.CruiseTime, self.BreaksDescent[-1]], self.SPW[2]),
                             lambda t: np.interp(t, [self.BreaksDescent[-1], self.BreaksClimbDiversion[-1]], self.SPW[3]),
                             lambda t: np.interp(t, [self.BreaksClimbDiversion[-1], self.CruiseTimeDiversion], self.SPW[4]),
                             lambda t: np.interp(t, [self.CruiseTimeDiversion, self.BreaksDescentDiversion[-1]], self.SPW[5])])














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
        
        
        
        
        
        
        
        
        
        
# --------------------------------------- OLD VERSION -----------------------------------------#        
        
    # def DefineMission(self):
             
    
    #     # Climb     
    #     self.HTClimb = self.CB * self.VClimb
    #     DHClimb = self.H2 - self.H1
    #     self.DTClimb = np.ceil(DHClimb/self.HTClimb)
    #     DRClimb = self.VClimb * self.DTClimb

    #     # Descent (Same of Climb, with negative PS)
    #     self.HTDescent = - self.CB * self.VDescent
    #     DHDescent = DHClimb
    #     self.DTDescent = np.ceil(np.abs(DHDescent/self.HTDescent))
    #     DRDescent = self.VDescent * self.DTDescent

    #     # Cruise
    #     DRCruise = self.MissionRange - DRClimb - DRDescent
    #     self.DTCruise = np.ceil(DRCruise/self.VCruise)
        
    #     # Diversion Climb
    #     DiversionDHClimb = self.H3 - self.H1
    #     self.DiversionDTClimb = np.ceil(DiversionDHClimb/self.HTClimb)
    #     DiversionDRClimb = self.VClimb * self.DiversionDTClimb
        
    #     # Diversion Descent
    #     DiversionDHDescent = DiversionDHClimb
    #     self.DiversionDTDescent = np.ceil(np.abs(DiversionDHDescent/self.HTDescent))
    #     DiversionDRDescent = self.VDescent * self.DiversionDTDescent
        
    #     # Diversion Cruise
    #     DiversionDRCruise = self.DiversionRange - DiversionDRClimb - DiversionDRDescent
    #     self.DiversionDTCruise = np.ceil(DiversionDRCruise/self.DiversionVCruise)
        
        
    #     self.T1 = self.DTClimb + self.DTCruise
    #     self.T2 = self.T1 + self.DTDescent
    #     self.T3 = self.T2 + self.DiversionDTClimb
    #     self.T4 = self.T3 + self.DiversionDTCruise
    #     self.TotalTime = self.T4 + self.DiversionDTDescent
        
    #     return None
    
    # def Altitude(self,t):

    #     return np.piecewise(t, [t < self.DTClimb, ((t >= self.DTClimb) & (t < self.T1)), ((t >= self.T1) & (t < self.T2)), 
    #                             ((t >= self.T2) & (t < self.T3)), ((t >= self.T3) & (t < self.T4)), t >= self.T4], 
    #                         [lambda t : (self.H1+self.HTClimb*t), self.H2, lambda t : (self.H2+self.HTDescent*(t-self.T1)), 
    #                           lambda t : (self.H1+self.HTClimb*(t-self.T2)), self.H3, lambda t : (self.H3+self.HTDescent*(t-self.T4))])

    
    # def PowerExcess(self,t):
    #     return np.piecewise(t, [t < self.DTClimb, ((t >= self.DTClimb) & (t < self.T1)), ((t >= self.T1) & (t < self.T2)), 
    #                             ((t >= self.T2) & (t < self.T3)), ((t >= self.T3) & (t < self.T4)), t >= self.T4], 
    #                         [self.HTClimb, 0, self.HTDescent, self.HTClimb, 0, self.HTDescent])

    # def Velocity(self,t):
    #     return np.piecewise(t, [t < self.DTClimb, ((t >= self.DTClimb) & (t < self.T1)), ((t >= self.T1) & (t < self.T2)), 
    #                             ((t >= self.T2) & (t < self.T3)), ((t >= self.T3) & (t < self.T4)), t >= self.T4], 
    #                         [self.VClimb, self.VCruise, self.VDescent, self.VClimb, self.DiversionVCruise, self.VDescent])