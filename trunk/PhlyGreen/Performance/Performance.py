import numpy as np
import pg.Atmosphere as ISA

class Performance:
    def __init__(self, aircraft):
        self.aircraft = aircraft


    def set_speed(self,altitude,Mach,TAS,IAS):
        if Mach is not None:
            self.Mach = Mach
            self.TAS = Mach * soundspeed
            self.EAS = Tas * np.sqrt(rho0ratio)


        

    def PoWTO(self,WTOoS,beta,n,altitude,Mach=None,TAS=None,IAS=None):
        V = Mach * np.sqrt(gamma * R * T)
        q = 0.5 * rho * V**2
        Cl = n * beta * WTOoS / q
        PW = 9.81 * 1.0/WTOoS * q * V * self.aircraft.aerodynamics.Cd(CL,Mach) + beta * Ps
        return PW
