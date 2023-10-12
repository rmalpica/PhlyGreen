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


    def set_speed(self,altitude,speed,speedtype):

        mTOkn = 1.94384 #Conversion meter/s -> knots

        if speedtype == 'Mach':
            self.Mach = speed
            self.TAS = Speed.Mach2TAS(speed,altitude)
            self.CAS = Speed.Mach2CAS(speed,altitude)
            self.KTAS = self.TAS*mTOkn
            self.KCAS = self.CAS*mTOkn
            
        elif speedtype == 'TAS':
            self.Mach = Speed.TAS2Mach(speed,altitude)
            self.TAS = speed
            self.CAS = Speed.TAS2CAS(speed,altitude)
            self.KTAS = self.TAS*mTOkn
            self.KCAS = self.CAS*mTOkn

        elif speedtype == 'CAS':
            self.Mach = Speed.CAS2Mach(speed,altitude)
            self.TAS = Speed.CAS2TAS(speed,altitude)
            self.CAS = speed
            self.KTAS = self.TAS*mTOkn
            self.KCAS = self.CAS*mTOkn

        elif speedtype == 'KTAS':
            self.KTAS = speed
            self.TAS = self.KTAS/mTOkn
            self.Mach = Speed.TAS2Mach(self.TAS,altitude)
            self.CAS = Speed.TAS2CAS(self.TAS,altitude)
            self.KCAS = self.CAS*mTOkn

        elif speedtype == 'KCAS':
            self.KCAS = speed
            self.CAS = self.KCAS/mTOkn
            self.Mach = Speed.CAS2Mach(self.CAS,altitude)
            self.TAS = Speed.CAS2TAS(self.CAS,altitude)
            self.KTAS = self.TAS*mTOkn
        
        return None


        

    def PoWTO(self,WTOoS,beta,Ps,n,altitude,speed,speedtype):
        self.set_speed(self,altitude,speed,speedtype)
        q = 0.5 * ISA.RHOstd(altitude) * self.TAS**2
        Cl = n * beta * WTOoS / q
        PW = 9.81 * 1.0/WTOoS * q * self.TAS * self.aircraft.aerodynamics.Cd(Cl,self.Mach) + beta * Ps
        return PW
