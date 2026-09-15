import numpy as np
import numbers

class Aerodynamics:
    """ The Aerodynamics class. 

    This class provides models for the Class I estimation of the aircraft polar, i.e., the drag coefficient as a function of the lift coefficient. 
    At the moments, this class offers two major options:
    - an analytical quadratic polar, that expresses the CD as a function of CL with macroscopic aircraft properties as parameters (aspect ratio, oswald efficiency)
    - numerical polars, where the CD is a given numerical function of CL. Two polars have been implemented:
        - ATR42: 0.021476 + 0.03037383 * Cl**2
        - Do228: 0.029 + k1 * Cl**2 
    The class also stores and provides values for the maximum efficiency CL (analytical and numerical)

    """
    def __init__(self, aircraft):
        self.aircraft = aircraft
        self.AR = None
        self.e_osw = None
        self.polar = 'unset'
        self.kv = 0.01
        self.ClMin = None
        self.ClMax = None
        self.Cd_0 = None
        self.Cl_TO = None
        # Korn/Lock wave-drag geometry (only used by the 'compressible' polar)
        self.sweep = None        # quarter-chord sweep [deg]
        self.tc = None           # mean thickness-to-chord [-]
        self.kappa = None        # airfoil technology factor

    """ Properties """

    @property
    def polar(self):
        return self._polar
          
    @polar.setter
    def polar(self,value):
        if value in ('quadratic', 'compressible', 'ATR42', 'DO228', 'unset'):
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
            if polar.get("type") == 'compressible':
                self.set_compressible_polar(AR, e_osw)
            else:
                self.set_quadratic_polar(AR,e_osw)
        elif 'NumericalPolar' in self.aircraft.AerodynamicsInput: 
            self.polar = self.aircraft.AerodynamicsInput.get("NumericalPolar")['type']
            self.AR = 11
        else:
            raise ValueError("Error: aerodynamic model unknown")
        
        self.ClMax = self.aircraft.AerodynamicsInput['Landing Cl']
        self.Cl_TO = self.aircraft.AerodynamicsInput['Take Off Cl']
        self.ClMin = self.aircraft.AerodynamicsInput['Minimum Cl']
        self.Cd_0 = self.aircraft.AerodynamicsInput['Cd0']

        if self.polar == 'compressible':
            # Wing geometry driving the Korn drag-divergence Mach number. Defaults describe a
            # transonic transport with a supercritical section (A320/737 class).
            self.sweep = self.aircraft.AerodynamicsInput.get('Wing Sweep', 25.0)
            self.tc = self.aircraft.AerodynamicsInput.get('Thickness to Chord', 0.12)
            self.kappa = self.aircraft.AerodynamicsInput.get('Korn Kappa', 0.95)


    def set_quadratic_polar(self,AR,e_osw):
        self.polar = 'quadratic'
        self.AR = AR
        self.e_osw = e_osw

    def set_compressible_polar(self,AR,e_osw):
        """Quadratic polar plus a Korn/Lock transonic wave-drag rise.

        Use this polar whenever the cruise Mach number approaches drag divergence (turbofan
        transports). The plain 'quadratic' polar has no wave drag at all, so it understates
        cruise drag exactly where such a design lives.
        """
        self.polar = 'compressible'
        self.AR = AR
        self.e_osw = e_osw

    def Cd(self,Cl,Mach):
        if self.polar == 'quadratic':
            Cd = self.Cd0(Mach) + self.k1() * Cl**2 + self.k2() * Cl
            return Cd
        elif self.polar == 'compressible':
            Cd = self.Cd0(Mach) + self.k1() * Cl**2 + self.k2() * Cl + self.Cd_wave(Cl, Mach)
            return Cd
        elif self.polar == 'ATR42':
            return 0.021476 + 0.03037383 * Cl**2
        elif self.polar == 'DO228':
            return 0.029 + self.k1() * Cl**2
        else:
            raise ValueError("Polar model unset")

    def MachDD(self, Cl):
        """Drag-divergence Mach number from the Korn equation.

            M_dd = kappa/cos(L) - (t/c)/cos(L)^2 - Cl/(10 cos(L)^3)

        ``kappa`` is the airfoil technology factor (0.87 conventional, 0.95 supercritical)
        and ``L`` the quarter-chord sweep. Sweeping the wing, thinning it, or unloading it
        all push drag divergence to a higher Mach number.
        """
        cosL = np.cos(np.radians(self.sweep))
        return self.kappa/cosL - self.tc/cosL**2 - np.asarray(Cl)/(10.0*cosL**3)

    def MachCrit(self, Cl):
        """Critical Mach number, where the wave-drag rise starts.

        M_dd is *defined* as the Mach number at which dCd/dM = 0.1. With Lock's law
        ``Cd_wave = 20 (M - M_crit)^4`` that derivative is ``80 (M - M_crit)^3``, so
        drag divergence sits a fixed ``(0.1/80)^(1/3)`` ~ 0.108 above M_crit. Referencing
        the drag rise to M_crit rather than to M_dd is what makes it non-zero at a normal
        cruise Mach, which is the whole point of carrying the term.
        """
        return self.MachDD(Cl) - (0.1/80.0)**(1.0/3.0)

    def Cd_wave(self, Cl, Mach):
        """Transonic wave drag (Lock's fourth-power law), zero below the critical Mach.

            Cd_wave = 20 (M - M_crit)^4   for M > M_crit

        The fourth power is what makes the drag rise steep past M_crit; the linear ramp in
        the legacy `Cd0` bump is far too shallow to size a transonic aircraft against.
        """
        dM = np.asarray(Mach, dtype=float) - self.MachCrit(Cl)
        return 20.0 * np.where(dM > 0.0, dM, 0.0)**4

    def Cd0(self,Mach):
        # np.where (not np.piecewise) so an array of Mach numbers works: piecewise assigns
        # scalars-or-callables into a masked subset and mis-broadcasts the array branch.
        # The 'compressible' polar carries its drag rise in Cd_wave instead, so its Cd0 is
        # the flat (incompressible) value.
        Mach = np.asarray(Mach, dtype=float)
        if self.polar == 'compressible':
            return np.full(Mach.shape, self.Cd_0) if Mach.ndim else self.Cd_0
        return np.where(Mach <= 0.8, self.Cd_0, 0.035*Mach - 0.011)
    
    def k1(self):
        return self.kv + self.ki()
    
    def k2(self):
        return -2.0 * self.kv * self.ClMin
    
    def ki(self):
        return 1.0/(np.pi * self.AR * self.e_osw)
    
    def ClE(self,Mach):
        if self.polar in ('quadratic', 'compressible'):
            # Best-L/D lift coefficient of the parabolic polar. For 'compressible' this
            # ignores the wave term, so it is optimistic above drag divergence.
            return np.sqrt(self.Cd0(Mach)* np.pi * self.AR * self.e_osw)
        elif self.polar == 'ATR42':
            return 0.82
        else:
            raise ValueError("Polar model unset")
