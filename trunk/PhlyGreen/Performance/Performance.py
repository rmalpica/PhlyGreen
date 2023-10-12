import numpy as np
#import PhlyGreen.Utilities.Atmosphere as ISA
#import PhlyGreen.Utilities.Speed as Speed

class Performance:
    def __init__(self, aircraft):
        self.aircraft = aircraft
        self.Mach = None
        self.TAS = None
        self.CAS = None
        #self.altitude = None
        #self.beta = None


    def set_speed(self,altitude,speed,speedtype):

        if speedtype == 'Mach':
            self.Mach = speed
            self.TAS = Speed.Mach2TAS(speed,altitude)
            self.CAS = Speed.Mach2CAS(speed,altitude)
            
        if speedtype == 'TAS':
            self.Mach = Speed.TAS2Mach(speed,altitude)
            self.TAS = speed
            self.CAS = Speed.TAS2CAS(speed,altitude)

        if speedtype == 'CAS':
            self.Mach = Speed.CAS2Mach(speed,altitude)
            self.TAS = Speed.CAS2TAS(speed,altitude)
            self.CAS = speed

        if speedtype == 'KTAS':
            self.Mach = Speed.TAS2Mach(speed,altitude)
            self.TAS = speed
            self.CAS = Speed.TAS2CAS(speed,altitude)

        if speedtype == 'KCAS':
            self.Mach = Speed.CAS2Mach(speed,altitude)
            self.TAS = Speed.CAS2TAS(speed,altitude)
            self.CAS = speed
        
        return None


        

    def PoWTO(self,WTOoS,beta,n,altitude,speed,speedtype):
        self.set_speed(self,altitude,speed,speedtype)
        q = 0.5 * ISA.RHOstd(altitude) * self.TAS**2
        Cl = n * beta * WTOoS / q
        PW = 9.81 * 1.0/WTOoS * q * self.TAS * self.aircraft.aerodynamics.Cd(Cl,self.Mach) + beta * Ps
        return PW
