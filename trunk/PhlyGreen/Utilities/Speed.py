import numpy as np
import PhlyGreen.Utilities.Atmosphere as ISA
# ISA = PhlyGreen.Utilities.Atmosphere()


def soundspeed(h,DISA):
#    ISA = PhlyGreen.Utilities.Atmosphere()
    return np.sqrt(ISA.atmosphere.gammaair * ISA.atmosphere.Rair * (ISA.atmosphere.Tstd(h) + DISA))

def Mach2TAS(Mach, h, DISA=0.):
    return Mach * soundspeed(h,DISA)
    
def Mach2CAS(Mach,h, DISA=0.):
#    ISA = PhlyGreen.Utilities.Atmosphere()
    qc = ISA.atmosphere.Pstd(h) * ((1 + 0.2*Mach**2)**(1/ISA.atmosphere.delta) - 1)
    return np.sqrt(5)*ISA.atmosphere.a_sls*np.sqrt((qc/ISA.atmosphere.p_sls + 1)**ISA.atmosphere.delta - 1)
    # return Mach2TAS(Mach,h) * np.sqrt(ISA.RHOoRHO0(Mach)) * (1 + (1/8)*(1-ISA.PoP0(Mach))*Mach**2)

def CAS2Mach(CAS,h,DISA=0.):
     return TAS2Mach(CAS2TAS(CAS,h,DISA),h,DISA)

def TAS2Mach(TAS,h,DISA=0.):
    return TAS / soundspeed(h,DISA)

def CAS2TAS(CAS,h,DISA=0.):
#    ISA = PhlyGreen.Utilities.Atmosphere()
    C1 = ((CAS**2)/(5*ISA.atmosphere.a_sls**2) + 1)**(1/ISA.atmosphere.delta) - 1
    return np.sqrt(5) * soundspeed(h,DISA) * np.sqrt( ((ISA.atmosphere.p_sls/ISA.atmosphere.Pstd(h)) * C1 + 1 ) ** ISA.atmosphere.delta - 1)

def TAS2CAS(TAS,h,DISA=0.):
    return Mach2CAS(TAS2Mach(TAS,h,DISA),h,DISA)