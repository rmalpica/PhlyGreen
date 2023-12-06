import numpy as np
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed

class Constraint:
    def __init__(self, aircraft):
        self.aircraft = aircraft
        self.WTOoS = np.linspace(1, 7000, num=100)


    def ReadInput(self):
        
        self.ConstraintsBeta = self.aircraft.ConstraintsInput['beta']
        self.ConstraintsAltitude = self.aircraft.ConstraintsInput['altitude']
        self.ConstraintsSpeed = self.aircraft.ConstraintsInput['speed']
        self.ConstraintsSpeedtype = self.aircraft.ConstraintsInput['speedtype']
        self.ConstraintsN = self.aircraft.ConstraintsInput['load factor']
        self.DISA = self.aircraft.ConstraintsInput['DISA']
        self.kTO = self.aircraft.ConstraintsInput['kTO']
        self.sTO = self.aircraft.ConstraintsInput['sTO']
        self.CB = self.aircraft.ConstraintsInput['Climb Gradient']
        self.ht = self.aircraft.ConstraintsInput['ht']
        self.M1 = self.aircraft.ConstraintsInput['M1']
        self.M2 = self.aircraft.ConstraintsInput['M2']
        self.DTAcceleration = self.aircraft.ConstraintsInput['DTAcceleration']
        self.Mavg = (self.M1 + self.M2)/2
        self.PsAcceleration = Speed.Mach2TAS(self.Mavg, self.ConstraintsAltitude[5],self.DISA) * (Speed.Mach2TAS(self.M2, self.ConstraintsAltitude[5],self.DISA) - Speed.Mach2TAS(self.M1, self.ConstraintsAltitude[5],self.DISA))/(self.DTAcceleration * 9.81) 

        


    def EvaluateConstraints(self, WTOoS, DISA, kTO, sTO, CB, ht, PsAcceleration):
        
        
        
        self.PWCruise = self.aircraft.performance.PoWTO(self.WTOoS, self.ConstraintsBeta[0], 0, self.ConstraintsN[0], self.ConstraintsAltitude[0], DISA, self.ConstraintsSpeed[0], self.ConstraintsSpeedtype[0])
        self.PWTakeOff = self.aircraft.performance.TakeOff(WTOoS,self.ConstraintsBeta[1], self.ConstraintsAltitude[1], kTO, sTO, DISA, self.ConstraintsSpeed[1], self.ConstraintsSpeedtype[1])
        self.PWOEI = self.aircraft.performance.OEIClimb(self.WTOoS,self.ConstraintsBeta[2], 1.4*CB*self.ConstraintsSpeed[2], self.ConstraintsN[2], self.ConstraintsAltitude[2], DISA, self.ConstraintsSpeed[2], self.ConstraintsSpeedtype[2])
        self.PWClimb = self.aircraft.performance.PoWTO(self.WTOoS,self.ConstraintsBeta[2], 1.4*CB*self.ConstraintsSpeed[2], self.ConstraintsN[2], self.ConstraintsAltitude[2], DISA, self.ConstraintsSpeed[2], self.ConstraintsSpeedtype[2])
        self.PWTurn = self.aircraft.performance.PoWTO(self.WTOoS, self.ConstraintsBeta[3], 0, self.ConstraintsN[3], self.ConstraintsAltitude[3], DISA, self.ConstraintsSpeed[3], self.ConstraintsSpeedtype[3])
        self.PWCeiling = self.aircraft.performance.Ceiling(WTOoS, self.ConstraintsBeta[4], ht, self.ConstraintsN[4], self.ConstraintsAltitude[4], DISA, self.ConstraintsSpeed[4])
        self.PWAcceleration = self.aircraft.performance.PoWTO(self.WTOoS,self.ConstraintsBeta[5], PsAcceleration, self.ConstraintsN[5], self.ConstraintsAltitude[5], DISA, self.Mavg, self.ConstraintsSpeedtype[5])
        self.PWLanding, self.WTOoSLanding = self.aircraft.performance.Landing(WTOoS, self.ConstraintsAltitude[6], self.ConstraintsSpeed[6], self.ConstraintsSpeedtype[6], DISA)
        # self.PWTorenbeek, self.aircraft.performance.WTOoSTorenbeek = self.TakeOff_TORENBEEK(self.ConstraintsAltitude[1], sTO, 1.15, 10.7, 1.25 , 0.02, self.ConstraintsSpeed[1], self.ConstraintsSpeedtype[1], DISA)

        return None
    
    def FindDesignPoint(self):

           
        self.EvaluateConstraints(self.WTOoS, self.DISA, self.kTO, self.sTO, self.CB, self.ht, self.PsAcceleration)
        
        PWMatrix = np.matrix([self.PWCruise, self.PWTakeOff, self.PWClimb, self.PWTurn, self.PWCeiling, self.PWAcceleration, self.PWOEI])
        self.MaxPW = np.zeros(len(self.WTOoS))
        for i in range(len(self.WTOoS)):
            self.MaxPW[i] = np.max(PWMatrix[:,i])

        self.DesignPW = np.min(self.MaxPW)
        self.DesignWTOoS = self.WTOoS[np.argmin(self.MaxPW)]
        return None