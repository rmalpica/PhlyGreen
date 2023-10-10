import numpy as np
import PhlyGreen.Utilities.Atmosphere as ISA

class Performance:
    def __init__(self, aircraft):
        self.aircraft = aircraft
        self.Mach = None
        self.TAS = None
        self.CAS = None
        #self.altitude = None
        #self.beta = None


    def set_speed(self,altitude,speed,speedtype):
        


        

    def PoWTO(self,WTOoS,beta,n,altitude,speed,speedtype):
        self.set_speed(   )
        q = 0.5 * ISA.RHOstd(altitude) * self.TAS**2
        Cl = n * beta * WTOoS / q
        PW = 9.81 * 1.0/WTOoS * q * self.TAS * self.aircraft.aerodynamics.Cd(Cl,self.Mach) + beta * Ps
        return PW
