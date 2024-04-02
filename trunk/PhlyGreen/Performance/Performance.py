import numpy as np
import numbers
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed
import PhlyGreen.Utilities.Units as Units


class Performance:
    def __init__(self, aircraft):
        self.aircraft = aircraft
        self.g_acc = 9.81 
        self.n_engines = 2
        self.Mach = None
        self.TAS = None
        self.CAS = None 
        self.KTAS = None
        self.KCAS = None

    """ Properties """

    @property
    def Mach(self):
        if self._Mach == None:
            raise ValueError("Mach unset. Exiting")
        return self._Mach
      
    @Mach.setter
    def Mach(self,value):
        self._Mach = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Mach number: %e. Exiting" %value)

    @property
    def TAS(self):
        if self._TAS == None:
            raise ValueError("True Air Speed unset. Exiting")
        return self._TAS
      
    @TAS.setter
    def TAS(self,value):
        self._TAS = value
        if(isinstance(value, numbers.Number) and (value <= 0)):
            raise ValueError("Error: Illegal True Air Speed: %e. Exiting" %value)

    @property
    def CAS(self):
        if self._CAS == None:
            raise ValueError("Calibrated Air Speed unset. Exiting")
        return self._CAS
      
    @CAS.setter
    def CAS(self,value):
        self._CAS = value
        if(isinstance(value, numbers.Number) and (value <= 0)):
            raise ValueError("Error: Illegal Calibrated Air Speed: %e. Exiting" %value)

    @property
    def KTAS(self):
        if self._KTAS == None:
            raise ValueError("True Air Speed (knots) unset. Exiting")
        return self._KTAS
      
    @KTAS.setter
    def KTAS(self,value):
        self._KTAS = value
        if(isinstance(value, numbers.Number) and (value <= 0)):
            raise ValueError("Error: Illegal True Air Speed (knots): %e. Exiting" %value)

    @property
    def KCAS(self):
        if self._KCAS == None:
            raise ValueError("Calibrated Air Speed (knots) unset. Exiting")
        return self._KCAS
      
    @KCAS.setter
    def KCAS(self,value):
        self._KCAS = value
        if(isinstance(value, numbers.Number) and (value <= 0)):
            raise ValueError("Error: Illegal Calibrated Air Speed (knots): %e. Exiting" %value)



    """ Methods """

    def set_speed(self,altitude,speed,speedtype,DISA):

        if speedtype == 'Mach':
            self.Mach = speed
            self.TAS = Speed.Mach2TAS(speed,altitude,DISA)
            self.CAS = Speed.Mach2CAS(speed,altitude,DISA)
            self.KTAS = Units.MtoKN(self.TAS)
            self.KCAS = Units.MtoKN(self.CAS)
            
        elif speedtype == 'TAS':
            self.Mach = Speed.TAS2Mach(speed,altitude,DISA)
            self.TAS = speed
            self.CAS = Speed.TAS2CAS(speed,altitude,DISA)
            self.KTAS = Units.MtoKN(self.TAS)
            self.KCAS = Units.MtoKN(self.CAS)

        elif speedtype == 'CAS':
            self.Mach = Speed.CAS2Mach(speed,altitude,DISA)
            self.TAS = Speed.CAS2TAS(speed,altitude,DISA)
            self.CAS = speed
            self.KTAS = Units.MtoKN(self.TAS)
            self.KCAS = Units.MtoKN(self.CAS)

        elif speedtype == 'KTAS':
            self.KTAS = speed
            self.TAS = Units.KNtoM(self.KTAS)
            self.Mach = Speed.TAS2Mach(self.TAS,altitude,DISA)
            self.CAS = Speed.TAS2CAS(self.TAS,altitude,DISA)
            self.KCAS = Units.MtoKN(self.CAS)

        elif speedtype == 'KCAS':
            self.KCAS = speed
            self.CAS = Units.KNtoM(self.KCAS)
            self.Mach = Speed.CAS2Mach(self.CAS,altitude,DISA)
            self.TAS = Speed.CAS2TAS(self.CAS,altitude,DISA)
            self.KTAS = Units.MtoKN(self.TAS)
        
        else:
            raise ValueError("Speedtype not supported")

        return None

    def PoWTO(self,WTOoS,beta,Ps,n,altitude,DISA,speed,speedtype):      # W/Kg 
        self.set_speed(altitude,speed,speedtype,DISA)
        q = 0.5 * ISA.atmosphere.RHOstd(altitude,DISA) * self.TAS**2
        Cl = n * beta * WTOoS / q
        PW = self.g_acc * ( 1.0/WTOoS * q * self.TAS * self.aircraft.aerodynamics.Cd(Cl,self.Mach)  + beta * Ps )
        return PW

    def OEIClimb(self,WTOoS,beta,Ps,n,altitude,DISA,speed,speedtype):       
        self.set_speed(altitude,speed,speedtype,DISA)
        q = 0.5 * ISA.atmosphere.RHOstd(altitude,DISA) * self.TAS**2
        Cl = n * beta * WTOoS / q
        PW =  (self.n_engines/(self.n_engines-1))*(self.g_acc * (1.0/WTOoS * q * self.TAS * self.aircraft.aerodynamics.Cd(Cl,self.Mach) + beta * Ps))
        return PW
    
    def Ceiling(self,WTOoS,beta,Ps,n,altitude,DISA,MachC):
        TASCeiling = np.sqrt((2*beta*WTOoS)/(ISA.atmosphere.RHOstd(altitude, DISA)* self.aircraft.aerodynamics.ClE(MachC)))
        q = 0.5 * ISA.atmosphere.gammaair * ISA.atmosphere.Pstd(altitude) * MachC**2
        Cl = n * beta * WTOoS / q
        PW = self.g_acc * ( 1.0/WTOoS * q * TASCeiling * self.aircraft.aerodynamics.Cd(Cl,MachC) + beta * Ps )
        return PW
    
    def TakeOff(self,WTOoS,beta,altitudeTO,kTO,sTO,DISA,speed,speedtype):
        self.set_speed(altitudeTO, speed, speedtype, DISA)
        PW = self.TAS * beta**2 * WTOoS * (kTO**2) / (sTO * ISA.atmosphere.RHOstd(altitudeTO,DISA) * self.aircraft.aerodynamics.Cl_TO)
        return PW
        
    def Landing(self,WTOoS,altitude,speed,speedtype,DISA):
        self.set_speed(altitude, speed, speedtype, DISA)
        PWLanding = np.linspace(0, 400,num= len(WTOoS))
        WTOoSLanding = np.ones(len(WTOoS)) * (ISA.atmosphere.RHOstd(altitude, DISA)/2 * self.aircraft.aerodynamics.ClMax * self.TAS**2)
        return PWLanding, WTOoSLanding
        
            #-----------------------              WIP            ------------------------#    
            
    def TakeOff_TORENBEEK(self, altitudeTO, sTO, fTO, hTO, V3oVS, mu, speed, speedtype, DISA):
        self.set_speed(altitudeTO,speed,speedtype,DISA)
        PW = np.linspace(1, 300, num=100)
        ToWTO = PW/self.TAS
        gammaLOF = 0.9 * ToWTO - 0.3/np.sqrt(self.aircraft.aerodynamics.AR)
        mu1 = mu + 0.01*self.aircraft.aerodynamics.ClMax 
        WTOoS = (sTO/fTO - hTO/gammaLOF) * (ISA.atmosphere.RHOstd(altitudeTO,DISA)  * self.aircraft.aerodynamics.ClMax * (1 + gammaLOF*np.sqrt(2))) / ((V3oVS)**2 * ((ToWTO - mu1)**(-1) + np.sqrt(2) ))
        
        return PW, WTOoS

            #----------------------------------------------------------------------------#  

