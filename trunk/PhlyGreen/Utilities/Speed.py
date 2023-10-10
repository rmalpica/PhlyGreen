import numpy as np
from . import Atmosphere as ISA

def soundspeed(h):
    return np.sqrt(ISA.gammaair * ISA.Rair * ISA.Tstd(h))

def Mach2TAS(Mach,h):
    return Mach * soundspeed(h)
    
def Mach2CAS(Mach,h):
    return Mach2TAS(Mach,h) * np.sqrt(ISA.RHOoRHO0(Mach)) * (1 + (1/8)*(1-ISA.PoP0(Mach))*Mach**2)

