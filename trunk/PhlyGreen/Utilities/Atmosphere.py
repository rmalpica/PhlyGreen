import numpy as np

class Atmosphere:
    def __init__(self):
        self.p_sls = 101325  #Pa
        self.T_sls = 288.15 #K
        self.Rair = 287 #J/(Kg k)
        self.gammaair = 1.4
        self.delta = (self.gammaair - 1)/self.gammaair
        self.a_sls = np.sqrt(self.gammaair * self.Rair * self.T_sls) #m/s


    def Tstd(self,h):
        def z(h):
            r0 = 6356577
            return r0*h/(r0+h)
        
        def i(z):
            return np.piecewise(z,[z <= 11000, 11000 < z <= 20000, 20000 < z <= 32000], [0,1,2])
        
        Lstd = [-6.5, 0 , 1]
        zstd = [0, 11000, 20000]
        T_0 = [288.15,216.65,216.65]
        j=int(i(z(h)))

        return T_0[j] + Lstd[j] * (z(h)-zstd[j]) / 1000
    
    def Pstd(self,h):
        return 100*((44331.514-h)/11880.516)**(1/0.1902632)
    
    def RHOstd(self,h,DISA):
        return self.Pstd(h)/(self.Rair * (self.Tstd(h)+DISA))
    
    def RHO(self,T,P,DISA):
        return P/(self.Rair * (T+DISA))
 
    def ToT0(self,Mach):
        return (1 + self.delta * Mach**2) ** -1

    def PoP0(self,Mach):
        return (1 + self.delta * Mach**2) ** -(self.gammaair/(self.gammaair - 1))

    def RHOoRHO0(self,Mach):
        return (1 + self.delta * Mach**2) ** -(1/(self.gammaair - 1))

    def T0std(self,h,Mach):
        return self.Tstd(h) * self.ToT0(Mach)**-1
   
    def P0std(self,h,Mach):
        return self.Pstd(h) * self.PoP0(Mach)**-1

    def RHO0std(self,h,Mach,DISA):
        return self.RHOstd(h,DISA) * self.RHOoRHO0(Mach)**-1
    

atmosphere = Atmosphere()


   
