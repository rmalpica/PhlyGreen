import numpy as np
from . import Atmosphere as ISA



def soundspeed(h,DISA):
    return np.sqrt(ISA.gammaair * ISA.Rair * (ISA.Tstd(h) + DISA))

def Mach2TAS(Mach, h, DISA=0.):
    return Mach * soundspeed(h,DISA)
    
def Mach2CAS(Mach,h, DISA=0.):
    qc = ISA.Pstd(h) * ((1 + 0.2*Mach**2)**(1/ISA.delta) - 1)
    return np.sqrt(5)*ISA.a_sls*np.sqrt((qc/ISA.p_sls + 1)**ISA.delta - 1)
    # return Mach2TAS(Mach,h) * np.sqrt(ISA.RHOoRHO0(Mach)) * (1 + (1/8)*(1-ISA.PoP0(Mach))*Mach**2)

def CAS2Mach(CAS,h,DISA=0.):
     return TAS2Mach(CAS2TAS(CAS,h,DISA),h,DISA)

def TAS2Mach(TAS,h,DISA=0.):
    return TAS / soundspeed(h,DISA)

def CAS2TAS(CAS,h,DISA=0.):
    C1 = ((CAS**2)/(5*ISA.a_sls**2) + 1)**(1/ISA.delta) - 1
    return np.sqrt(5) * soundspeed(h,DISA) * np.sqrt( ((ISA.p_sls/ISA.Pstd(h)) * C1 + 1 ) ** ISA.delta - 1)

def TAS2CAS(TAS,h,DISA=0.):
    return Mach2CAS(TAS2Mach(TAS,h,DISA),h,DISA)