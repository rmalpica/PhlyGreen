import numpy as np
import numbers

class Aerodynamics:
    def __init__(self, aircraft):
        self.aircraft = aircraft
        self.AR = None
        self.e_osw = None
        self.polar = 'unset'
        self.kv = 0.01
        self.ClMin = 0.2
        self.ClMax = 1.9

    """ Properties """

    @property
    def polar(self):
        return self._polar
          
    @polar.setter
    def polar(self,value):
        if value == 'quadratic' or value == 'unset':
            self._polar = value
        else:
            raise ValueError("Error: %s polar model not implemented. Exiting" %value)
        
    @property
    def AR(self):
        if self._AR == None:
            raise ValueError("Aspect Ratio unset. Exiting")
        return self._AR
          
    @AR.setter
    def AR(self,value):
        self._AR = value
        if(isinstance(value, numbers.Number) and value <= 0):
            raise ValueError("Error: Illegal Aspect Ratio: %e. Exiting" %value)
        
    @property
    def e_osw(self):
        if self._e_osw == None:
            raise ValueError("Oswald efficiency unset. Exiting")
        return self._e_osw
          
    @e_osw.setter
    def e_osw(self,value):
        self._e_osw = value
        if(isinstance(value, numbers.Number) and value <= 0):
            raise ValueError("Error: Illegal Oswald efficiency %e. Exiting" %value)




    """ Methods """

    def SetInput(self):
        if 'AnalyticPolar' in self.aircraft.AerodynamicsInput:
            polar = self.aircraft.AerodynamicsInput.get("AnalyticPolar")
            AR = polar['input'].get("AR")
            e_osw = polar['input'].get("e_osw")
            self.set_quadratic_polar(AR,e_osw)
        else:
            raise ValueError("Error: aerodynamic model unknown")


    def set_quadratic_polar(self,AR,e_osw):
        self.polar = 'quadratic'
        self.AR = AR
        self.e_osw = e_osw

    def Cd(self,Cl,Mach):
        if self.polar == 'quadratic':
            Cd = self.Cd0(Mach) + self.k1() * Cl**2 + self.k2() * Cl
            return Cd
        else:
            raise ValueError("Polar model unset")
        
    def Cd0(self,Mach):
        return np.piecewise(Mach,[Mach <= 0.8, Mach > 0.8],[0.017,0.035*Mach-0.011])
    
    def k1(self):
        return self.kv + self.ki()
    
    def k2(self):
        return -2.0 * self.kv * self.ClMin
    
    def ki(self):
        return 1.0/(np.pi * self.AR * self.e_osw)
    
    def ClE(self,Mach):
        return np.sqrt(self.Cd0(Mach)* np.pi * self.AR * self.e_osw)


        