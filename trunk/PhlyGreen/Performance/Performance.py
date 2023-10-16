import numpy as np
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed

class Performance:
    def __init__(self, aircraft):
        self.aircraft = aircraft
        self.Mach = None
        self.TAS = None
        self.CAS = None
        self.KCAS = None
        self.KTAS = None
        #self.altitude = None
        #self.beta = None

    def read_input(self,ConstraintsInput):
        
        self.ConstraintsBeta = ConstraintsInput['beta']
        self.ConstraintsAltitude = ConstraintsInput['altitude']
        self.ConstraintsSpeed = ConstraintsInput['speed']
        self.ConstraintsSpeedtype = ConstraintsInput['speedtype']


        
        return None

    def set_speed(self,altitude,speed,speedtype,DISA):

        mTOkn = 1.94384 #Conversion meter/s -> knots

        if speedtype == 'Mach':
            self.Mach = speed
            self.TAS = Speed.Mach2TAS(speed,altitude,DISA)
            self.CAS = Speed.Mach2CAS(speed,altitude,DISA)
            self.KTAS = self.TAS*mTOkn
            self.KCAS = self.CAS*mTOkn
            
        elif speedtype == 'TAS':
            self.Mach = Speed.TAS2Mach(speed,altitude,DISA)
            self.TAS = speed
            self.CAS = Speed.TAS2CAS(speed,altitude,DISA)
            self.KTAS = self.TAS*mTOkn
            self.KCAS = self.CAS*mTOkn

        elif speedtype == 'CAS':
            self.Mach = Speed.CAS2Mach(speed,altitude,DISA)
            self.TAS = Speed.CAS2TAS(speed,altitude,DISA)
            self.CAS = speed
            self.KTAS = self.TAS*mTOkn
            self.KCAS = self.CAS*mTOkn

        elif speedtype == 'KTAS':
            self.KTAS = speed
            self.TAS = self.KTAS/mTOkn
            self.Mach = Speed.TAS2Mach(self.TAS,altitude,DISA)
            self.CAS = Speed.TAS2CAS(self.TAS,altitude,DISA)
            self.KCAS = self.CAS*mTOkn

        elif speedtype == 'KCAS':
            self.KCAS = speed
            self.CAS = self.KCAS/mTOkn
            self.Mach = Speed.CAS2Mach(self.CAS,altitude,DISA)
            self.TAS = Speed.CAS2TAS(self.CAS,altitude,DISA)
            self.KTAS = self.TAS*mTOkn
        
        else:
            raise ValueError("Speedtype not supported")

        return None


        

    def PoWTO(self,WTOoS,beta,Ps,n,altitude,DISA,speed,speedtype):       
        self.set_speed(altitude,speed,speedtype,DISA)
        q = 0.5 * ISA.atmosphere.RHOstd(altitude,DISA) * self.TAS**2
        Cl = n * beta * WTOoS / q
        PW = 9.81 * 1.0/WTOoS * q * self.TAS * self.aircraft.aerodynamics.Cd(Cl,self.Mach) + beta * Ps
        return PW
    
    def Ceiling(self,WTOoS,beta,Ps,n,altitude,DISA,MachC):
        TASCeiling = np.sqrt((2*beta*WTOoS)/(ISA.atmosphere.RHOstd(altitude, DISA)* self.aircraft.aerodynamics.ClE(MachC)))
        q = 0.5 * ISA.atmosphere.gammaair * ISA.atmosphere.Pstd(altitude) * MachC**2
        Cl = n * beta * WTOoS / q
        PW = 9.81 * 1.0/WTOoS * q * TASCeiling * self.aircraft.aerodynamics.Cd(Cl,MachC) + beta * Ps
        return PW
    
    def TakeOff(self,WTOoS,beta,altitudeTO,kTO,sTO,DISA,speed,speedtype):
        self.set_speed(altitudeTO, speed, speedtype, DISA)
        PW = 9.81 * self.TAS * beta**2 * WTOoS * (kTO**2) / (sTO * ISA.atmosphere.RHOstd(altitudeTO,DISA) * 9.81 * self.aircraft.aerodynamics.ClMax)
        return PW
        
    def Landing(self,altitude,speed,speedtype,DISA):
        self.set_speed(altitude, speed, speedtype, DISA)
        PWLanding = np.linspace(0, 400,num=100)
        WTOoSLanding = np.ones(100) * (ISA.atmosphere.RHOstd(altitude, DISA)/2 * self.aircraft.aerodynamics.ClMax * self.TAS**2)
        return PWLanding, WTOoSLanding
        
            #-----------------------              WIP            ------------------------#    
            
    def TakeOff_TORENBEEK(self, altitudeTO, sTO, fTO, hTO, V3oVS, mu, speed, speedtype, DISA):
        self.set_speed(altitudeTO,speed,speedtype,DISA)
        PW = np.linspace(1, 300, num=100)
        ToWTO = PW/self.TAS
        gammaLOF = 0.9 * ToWTO - 0.3/np.sqrt(self.aircraft.aerodynamics.AR)
        mu1 = mu + 0.01*self.aircraft.aerodynamics.ClMax 
        WTOoS = (sTO/fTO - hTO/gammaLOF) * (ISA.atmosphere.RHOstd(altitudeTO,DISA)  * self.aircraft.aerodynamics.ClMax * (1 + gammaLOF*np.sqrt(2))) / ((V3oVS)**2 * ((ToWTO - mu1)**(-1) + np.sqrt(2) ))
        
        return PW, WTOoS

            #----------------------------------------------------------------------------#  

    def FindDesignPoint(self, ConstraintsInput, WTOoS, DISA, kTO, sTO, CB, ht, PsAcceleration):

        self.EvaluateConstraints(ConstraintsInput, WTOoS, DISA, kTO, sTO, CB, ht, PsAcceleration)
        
        PWMatrix = np.matrix([self.PWCruise, self.PWTakeOff, self.PWClimb, self.PWTurn, self.PWCeiling, self.PWAcceleration])
        self.MaxPW = np.zeros(len(WTOoS))
        for i in range(len(WTOoS)):
            self.MaxPW[i] = np.max(PWMatrix[:,i])

        self.DesignPW = np.min(self.MaxPW)
        self.DesignWTOoS = WTOoS[np.argmin(self.MaxPW)]
        return None

    def EvaluateConstraints(self, ConstraintsInput, WTOoS, DISA, kTO, sTO, CB, ht, PsAcceleration):
        
        self.read_input(ConstraintsInput)
        
        self.PWCruise = self.PoWTO(WTOoS, self.ConstraintsBeta[0], 0, 1, self.ConstraintsAltitude[0], DISA, self.ConstraintsSpeed[0], self.ConstraintsSpeedtype[0])
        self.PWTakeOff = self.TakeOff(WTOoS, self.ConstraintsBeta[1], self.ConstraintsAltitude[1], kTO, sTO, DISA, self.ConstraintsSpeed[1], self.ConstraintsSpeedtype[1])
        self.PWClimb = self.PoWTO(WTOoS, self.ConstraintsBeta[2], 1.4*CB*self.ConstraintsSpeed[2], 1, self.ConstraintsAltitude[2], DISA, self.ConstraintsSpeed[2], self.ConstraintsSpeedtype[2])
        self.PWTurn = self.PoWTO(WTOoS, self.ConstraintsBeta[3], 0, 1.1, self.ConstraintsAltitude[3], DISA, self.ConstraintsSpeed[3], self.ConstraintsSpeedtype[3])
        self.PWCeiling = self.Ceiling(WTOoS, self.ConstraintsBeta[4], ht, 1., self.ConstraintsAltitude[4], DISA, self.ConstraintsSpeed[4])
        self.PWAcceleration = self.PoWTO(WTOoS, self.ConstraintsBeta[5], PsAcceleration, 1., self.ConstraintsAltitude[5], DISA, self.ConstraintsSpeed[5], self.ConstraintsSpeedtype[5])
        self.PWLanding, self.WTOoSLanding = self.Landing(self.ConstraintsAltitude[6], self.ConstraintsSpeed[6], self.ConstraintsSpeedtype[6], DISA)
        # self.PWTorenbeek, self.WTOoSTorenbeek = self.TakeOff_TORENBEEK(self.ConstraintsAltitude[1], sTO, 1.15, 10.7, 1.25 , 0.02, self.ConstraintsSpeed[1], self.ConstraintsSpeedtype[1], DISA)

        return None