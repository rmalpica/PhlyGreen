import numpy as np
import numbers
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed
import PhlyGreen.Utilities.Units as Units
import joblib
import os
from sklearn.preprocessing import PolynomialFeatures
from .Propeller import Propeller
from scipy.optimize import brentq, brenth, ridder, newton

class Powertrain:
    """
    The Powertrain class.

    This class provides efficiency chains for several propulsive architectures. It also computes Class I estimates of the powertrain mass.
    Efficiency chains are computed by properly assembling user-provided efficiencies of each powertrain component. Components efficiencies can be constant or can depend on the operating condition. Also, Hamilton model for propeller efficiency is available.
    Several powertrain architectures are available (traditional, hybrid-series, hybrid-parallel), with reference to De Vries, R., Brown, M., and Vos, R., “Preliminary Sizing Method for Hybrid-Electric Distributed-Propulsion Aircraft,” Journal of Aircraft, Vol. 56, No. 6, 2019, pp. 2172–2188.
    In addition to the on-board efficiency chain, the well-to-tank chain can be also taken into account.

    """
    def __init__(self, aircraft):
        self.aircraft = aircraft
        #thermal powerplant efficiencies
        self.EtaGTmodelType = 'constant'
        self.EtaPPmodelType = 'constant'
        self.EtaGT = None
        self.EtaGB = None 
        self.EtaPP = None 
        #well-to-wake efficiencies
        self.EtaCH = None 
        self.EtaGR = None 
        self.EtaEX = None 
        self.EtaPR = None 
        self.EtaTR = None 
        self.EtaSourceToBattery = None 
        self.EtaSourceToFuel = None 
        #electric powerplant efficiencies 
        self.EtaPM = None
        self.EtaEM = None
        self.EtaEM1 = None
        self.EtaEM2 = None
        #specific powers
        self.SPowerPT = None 
        self.SPowerPMAD = None  
        #components mass
        self.WThermal = None
        self.WElectric = None
        #components rating
        self.engineRating = None


    """ Properties """

    @property
    def EtaGTmodelType(self):
        return self._EtaGTmodelType
      
    @EtaGTmodelType.setter
    def EtaGTmodelType(self,value):
        if value == 'PW127' or value == 'constant':
            self._EtaGTmodelType = value
        else:
            raise ValueError("Error: %s Eta GT model not implemented. Exiting" %value)
    
    @property
    def EtaPPmodelType(self):
        return self._EtaPPmodelType
      
    @EtaPPmodelType.setter
    def EtaPPmodelType(self,value):
        if value == 'PW127' or value == 'constant' or value == 'Hamilton':
            self._EtaPPmodelType = value
        else:
            raise ValueError("Error: %s Eta PP model not implemented. Exiting" %value)


    @property
    def EtaGT(self):
        if self._EtaGT == None:
            raise ValueError("Eta Gas Turbine unset. Exiting")
        return self._EtaGT
      
    @EtaGT.setter
    def EtaGT(self,value):
        self._EtaGT = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Gas Turbine: %e. Exiting" %value)
    
    @property
    def EtaGB(self):
        if self._EtaGB == None:
            raise ValueError("Eta Gearbox unset. Exiting")
        return self._EtaGB
      
    @EtaGB.setter
    def EtaGB(self,value):
        self._EtaGB = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Gearbox: %e. Exiting" %value)

    @property
    def EtaPP(self):
        if self._EtaPP == None:
            raise ValueError("Eta Propulsive unset. Exiting")
        return self._EtaPP
      
    @EtaPP.setter
    def EtaPP(self,value):
        self._EtaPP = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Propulsive: %e. Exiting" %value)
 
    @property
    def EtaCH(self):
        if self._EtaCH == None:
            raise ValueError("Eta Charge unset. Exiting")
        return self._EtaCH
      
    @EtaCH.setter
    def EtaCH(self,value):
        self._EtaCH = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Charge: %e. Exiting" %value)

    @property
    def EtaGR(self):
        if self._EtaGR == None:
            raise ValueError("Eta Grid unset. Exiting")
        return self._EtaGR
      
    @EtaGR.setter
    def EtaGR(self,value):
        self._EtaGR = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Grid: %e. Exiting" %value)

    @property
    def EtaEX(self):
        if self._EtaEX == None:
            raise ValueError("Eta Extraction unset. Exiting")
        return self._EtaEX
      
    @EtaEX.setter
    def EtaEX(self,value):
        self._EtaEX = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Extraction: %e. Exiting" %value)

    @property
    def EtaPR(self):
        if self._EtaPR == None:
            raise ValueError("Eta Production unset. Exiting")
        return self._EtaPR
      
    @EtaPR.setter
    def EtaPR(self,value):
        self._EtaPR = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Production: %e. Exiting" %value)

    @property
    def EtaTR(self):
        if self._EtaTR == None:
            raise ValueError("Eta Transportation unset. Exiting")
        return self._EtaTR
      
    @EtaTR.setter
    def EtaTR(self,value):
        self._EtaTR = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Transportation: %e. Exiting" %value)

    @property
    def EtaSourceToBattery(self):
        if self._EtaSourceToBattery == None:
            raise ValueError("Eta Source-to-Battery unset. Exiting")
        return self._EtaSourceToBattery
      
    @EtaSourceToBattery.setter
    def EtaSourceToBattery(self,value):
        self._EtaSourceToBattery = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Source-to-battery: %e. Exiting" %value)

    @property
    def EtaSourceToFuel(self):
        if self._EtaSourceToFuel== None:
            raise ValueError("Eta Source-to-Fuel unset. Exiting")
        return self._EtaSourceToFuel
      
    @EtaSourceToFuel.setter
    def EtaSourceToFuel(self,value):
        self._EtaSourceToFuel = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Source-to-fuel: %e. Exiting" %value)

    @property
    def EtaPM(self):
        if self._EtaPM == None:
            raise ValueError("Eta PMAD unset. Exiting")
        return self._EtaPM
      
    @EtaPM.setter
    def EtaPM(self,value):
        self._EtaPM = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta PMAD: %e. Exiting" %value)

    @property
    def EtaEM(self):
        if self._EtaEM == None:
            raise ValueError("Eta Electric Motor unset. Exiting")
        return self._EtaEM
      
    @EtaEM.setter
    def EtaEM(self,value):
        self._EtaEM = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Electric Motor: %e. Exiting" %value)

    @property
    def EtaEM1(self):
        if self._EtaEM1 == None:
            raise ValueError("Eta Electric Motor-1 unset. Exiting")
        return self._EtaEM1
      
    @EtaEM1.setter
    def EtaEM1(self,value):
        self._EtaEM1 = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Electric Motor-1: %e. Exiting" %value)

    @property
    def EtaEM2(self):
        if self._EtaEM2 == None:
            raise ValueError("Eta Electric Motor-2 unset. Exiting")
        return self._EtaEM2
      
    @EtaEM2.setter
    def EtaEM2(self,value):
        self._EtaEM2 = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Electric Motor-2: %e. Exiting" %value)

    @property
    def SPowerPT(self):
        if self._SPowerPT == None:
            raise ValueError("Powertrain Specific Power unset. Exiting")
        return self._SPowerPT
      
    @SPowerPT.setter
    def SPowerPT(self,value):
        self._SPowerPT = value
        if(isinstance(value, numbers.Number) and (value <= 0)):
            raise ValueError("Error: Illegal Powertrain Specific Power: %e. Exiting" %value)

    @property
    def SPowerPMAD(self):
        if self._SPowerPMAD == None:
            raise ValueError("PMAD Specific Power unset. Exiting")
        return self._SPowerPMAD
      
    @SPowerPMAD.setter
    def SPowerPMAD(self,value):
        self._SPowerPMAD = value
        if(isinstance(value, numbers.Number) and (value <= 0)):
            raise ValueError("Error: Illegal PMAD Specific Power: %e. Exiting" %value)

    @property
    def WThermal(self):
        if self._WThermal == None:
            raise ValueError("Thermal powertrain Weight unset. Exiting")
        return self._WThermal
      
    @WThermal.setter
    def WThermal(self,value):
        self._WThermal = value
        if(isinstance(value, numbers.Number) and (value < 0)):
            raise ValueError("Error: Illegal Thermal powertrain Weight: %e. Exiting" %value)

    @property
    def WElectric(self):
        if self._WElectric == None:
            raise ValueError("Electric powertrain Weight unset. Exiting")
        return self._WElectric
      
    @WElectric.setter
    def WElectric(self,value):
        self._WElectric = value
        if(isinstance(value, numbers.Number) and (value < 0)):
            raise ValueError("Error: Illegal Electric powertrain Weight: %e. Exiting" %value)




    """ Methods """

    def SetInput(self):

        try:
            self.aircraft.EnergyInput['Eta Gas Turbine']
        except:
            print('Warning: Eta Gas Turbine value unset. Using Eta Gas Turbine Model.')
        else:
            self.EtaGT = self.aircraft.EnergyInput['Eta Gas Turbine']

        try:
            self.aircraft.EnergyInput['Eta Gas Turbine Model'] 
        except:
            print('Warning: Eta Gas Turbine model unset. Using constant model')
        else: 
            self.EtaGTmodelType = self.aircraft.EnergyInput['Eta Gas Turbine Model'] 
            if self.EtaGTmodelType == 'PW127': 
                self.model_etath_0 = joblib.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'PW127', 'model_eta_th_0.joblib'))
                self.model_etath_1 = joblib.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'PW127', 'model_eta_th_1.joblib'))
                self.model_etath_2 = joblib.load(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'PW127', 'model_eta_th_2.joblib'))


        try:
            self.aircraft.EnergyInput['Eta Propulsive']
        except:
            print('Warning: Eta Propulsive value unset. Using Eta Eta Propulsive Model.')
        else:
            self.EtaPP = self.aircraft.EnergyInput['Eta Propulsive']

        try:
            self.aircraft.EnergyInput['Eta Propulsive Model'] 
        except:
            print('Warning: Eta Propulsive model unset. Using constant model')
        else: 
            self.EtaPPmodelType = self.aircraft.EnergyInput['Eta Propulsive Model'] 

        if self.EtaPPmodelType == 'Hamilton':
            self.Propeller = Propeller(self.aircraft)
            self.Propeller.SetInput()

        self.EtaGB = self.aircraft.EnergyInput['Eta Gearbox']
        self.SPowerPT = self.aircraft.EnergyInput['Specific Power Powertrain']
                
        if self.aircraft.WellToTankInput is not None:
            
            self.EtaCH = self.aircraft.WellToTankInput['Eta Charge']
            self.EtaGR = self.aircraft.WellToTankInput['Eta Grid']
            self.EtaEX = self.aircraft.WellToTankInput['Eta Extraction']
            self.EtaPR = self.aircraft.WellToTankInput['Eta Production']
            self.EtaTR = self.aircraft.WellToTankInput['Eta Transportation']
            
            self.EtaSourceToBattery = self.EtaCH * self.EtaGR
            self.EtaSourceToFuel = self.EtaEX * self.EtaPR * self.EtaTR


        
        if (self.aircraft.Configuration == 'Hybrid'):
            
            self.EtaPM = self.aircraft.EnergyInput['Eta PMAD']
            self.SPowerPMAD = self.aircraft.EnergyInput['Specific Power PMAD']

            
            if (self.aircraft.HybridType == 'Parallel'):
        
                self.EtaEM = self.aircraft.EnergyInput['Eta Electric Motor']
                
            if (self.aircraft.HybridType == 'Serial'):
                
                self.EtaEM1 = self.aircraft.EnergyInput['Eta Electric Motor 1']
                self.EtaEM2 = self.aircraft.EnergyInput['Eta Electric Motor 2']

        
        return None

    def PowerLapse(self,altitude,DISA):
        """ Full throttle power lapse, to be used in constraint analysis. Source: Ruijgrok, Elements of airplane performance, Eq.(6.7-11)"""
        n = 0.75
        lapse = (ISA.atmosphere.RHOstd(altitude,DISA)/ISA.atmosphere.RHOstd(0.0,DISA))**n
        return lapse
    
    def EtaPPconstModel(self,altitude,velocity,powerOutput):
        
        const = self.EtaPP

        return const
        
    def EtaPPpw127Model(self,altitude,velocity,powerOutput):

        eta = 0.89

        return eta
    
    def EtaPPHamiltonModel(self,alt,vel,PP):
        
        def func(Pgb):

            eta_PP = self.Propeller.ComputePropEfficiency(alt,vel,Pgb)
            if eta_PP > 1. or eta_PP < 0.4:
                eta_PP = 0.4

            A, b = self.DefinePowertrainSystem(alt,vel,PP,eta_PP)

            PR = np.linalg.solve(A,b)

            if self.aircraft.Configuration == 'Traditional':
                PDiff = PR[2] - Pgb/PP
            elif self.aircraft.Configuration == 'Hybrid': 
                # if self.aircraft.HybridType == 'Parallel':
                PDiff = PR[3] - Pgb/PP
            
            # print('Pgb/PP: ', PR[3])
            # print('Pgb solution of the linear system: ', PR[3]*PP)
            # print('Pgb guess: ', Pgb)
            # print('Difference: ', PDiff)
            # print('-'*40)
            return PDiff
            
        try:
            Pgb_Hamilton = brenth(func,PP, PP/0.4, xtol=0.001)
        except ValueError as e:
            if "must have different signs" in str(e):
                Pgb_Hamilton = 0.4
            else:
                raise

        Eta_Hamilton = self.Propeller.ComputePropEfficiency(alt,vel,Pgb_Hamilton) 
        if Eta_Hamilton > 1. or Eta_Hamilton < 0.4:
            Eta_Hamilton = 0.4

        # print('Propeller Efficiency: ', Eta_Hamilton)

        return Eta_Hamilton
    
    def EtaPPmodel(self,alt,vel,pwr):

        if self.EtaPPmodelType == 'constant':
            return self.EtaPPconstModel(alt,vel,pwr)
        elif self.EtaPPmodelType == 'PW127':
            return self.EtaPPpw127Model(alt,vel,pwr) 
        elif self.EtaPPmodelType == 'Hamilton':
            return self.EtaPPHamiltonModel(alt,vel,pwr)
        else:
            raise Exception("Unknown EtaPPmodelType: %s" %self.EtaPPmodelType)

    def EtaGTconstModel(self,altitude,velocity,powerOutput):
        
        const = self.EtaGT

        return const
        
    def EtaGTpw127Model(self,altitude,velocity,powerOutput):
        # potenza erogata all'albero dal singolo motore:
        pwsd_c = 1e-3*0.5*self.EtaPPmodel(altitude,velocity,powerOutput)*powerOutput
        # il fattore 0.5 serve a tenere conto che la potenza powerOutput è complessivamente erogata dai due motori 

        pwsd = min(2280, pwsd_c)

        if 0 <= pwsd <= 400 and 0 <= altitude <= 7600:
            model = self.model_etath_1
        elif 2000 <= pwsd <= 2280 and 0 <= altitude <= 1000:
            model = self.model_etath_2
        else:
            model = self.model_etath_0

        data_for_prediction = np.array([[pwsd, velocity, altitude]])
        poly_features = PolynomialFeatures(degree=4)
        data_for_prediction_poly = poly_features.fit_transform(data_for_prediction)

        eta_th = model.predict(data_for_prediction_poly)[0]

        eta = max(0.001, eta_th)

        return eta
    
    def EtaGTmodel(self,alt,vel,pwr):

        if self.EtaGTmodelType == 'constant':
            return self.EtaGTconstModel(alt,vel,pwr)
        elif self.EtaGTmodelType == 'PW127':
            return self.EtaGTpw127Model(alt,vel,pwr) 
        else:
            raise Exception("Unknown EtaGTmodelType: %s" %self.EtaGTmodelType)


       
    def Traditional(self,alt,vel,pwr):
        """
        Compute the power ratios across a traditional gas-turbine propulsion
        chain.

        This function solves a 4x4 linear system representing the steady-state power
        balance between fuel power, gas-turbine shaft power, gearbox power, and
        delivered propulsive power. The solution is expressed in nondimensional
        form, normalized by the propulsive power P_p.

        Parameters
        ----------
        alt : float
            Aircraft altitude [m].
        vel : float
            True airspeed [m/s].
        pwr : float
            Requested shaft power.

        These inputs are required for quering the instantaneous values of the components efficiencies 
        if models are provided. Otherwise, the constant user-provided values are employed.

        Returns
        -------
        numpy.ndarray of shape (4,)
            Normalized power ratios, in the following order:

            - Pf/Pp : fuel power to propulsive power ratio 
            - Pgt/Pp : gas-turbine shaft power to propulsive power ratio 
            - Pgb/Pp : gearbox output power to propulsive power ratio 
            - Pp/Pp  : always equal to 1

        Notes
        -----
        The system matrix is upper-triangular and could be solved analytically.
        However, using ``np.linalg.solve`` keeps the expression general and ensures
        numerical robustness with negligible computational overhead.
        """
        

        A = np.array([[- self.EtaGTmodel(alt,vel,pwr), 1, 0, 0],
                      [0, - self.EtaGB, 1, 0],
                      [0, 0, - self.EtaPPmodel(alt,vel,pwr), 1],
                      [0, 0, 0, 1]])
       
        b = np.array([0, 0, 0, 1])
        
        PowerRatio = np.linalg.solve(A,b)

        #Ordine output   Pf/Pp  Pgt/Pp   Pgb/Pp  Pp/Pp 
        return PowerRatio

    
    def Hybrid(self,phi,alt,vel,pwr):
        """
        Compute power ratios for hybrid-electric propulsion architectures.

        This function assembles and solves a linear system representing the steady-state
        power balance across all components of a hybrid propulsion system. Two
        architectures are supported:

        1. **Parallel hybrid**
           Includes:
           - Gas turbine (GT) engine
           - Gearbox (GB)
           - Electric motor/generator (EM)
           - Power electronics and/or management system(PM)
           - Propulsive device, e.g., propeller (PP)
           - Hybrid power-split defined by ``phi``

           The returned power ratios correspond to:
           ``[Pf/Pp, Pgt/Pp, Pgb/Pp, Ps1/Pp, Pe1/Pp, Pbat/Pp, Pp1/Pp]``

        2. **Serial hybrid**
           Includes:
           - Gas turbine (GT) engine
           - generator (EM1)
           - Power electronics and/or management system(PM)
           - Electric motor (EM2)
           - Gearbox (GB)
           - Propulsive device, e.g., propeller (PP)
           - Hybrid power-split constraint defined by ``phi``

           The returned power ratios correspond to:
           ``[Pf/Pp, Pgt/Pp, Pgb/Pp, Ps1/Pp, Pe1/Pp, Pbat/Pp, Pgen/Pp, Pp1/Pp]``

        Parameters
        ----------
        phi : float
            Hybrid power-split ratio.  
            - In parallel mode: fraction of propulsive power supplied electrically.  
            - In serial mode: fraction of generator/battery power routed to propulsion.
        alt : float
            Aircraft altitude [m].
        vel : float
            True airspeed [m/s].
        pwr : float
            Requested shaft power level.

        Returns
        -------
        numpy.ndarray
            Vector of nondimensional power ratios, normalized by propulsive power P_p.
            The output order depends on the hybrid configuration (parallel or serial).

        Notes
        -----
        - The function constructs a 7x7 (parallel) or 8x8 (serial) linear system and
          solves it using ``np.linalg.solve``.
        - The systems have block-triangular structure, but closed-form analytical
          expressions would be lengthy and less maintainable than the numerical solve.
        - All efficiencies (GT, GB, EM, PM, PP) are evaluated at the given flight
          condition, if models are available.
        """
        
        # phi = self.aircraft.mission.profile.SuppliedPowerRatio(t)
        self.phi = phi

        if (self.aircraft.HybridType == 'Parallel'):
        
            A = np.array([[- self.EtaGTmodel(alt,vel,pwr), 1, 0, 0, 0, 0, 0],
                      [0, -self.EtaGB, -self.EtaGB, 1, 0, 0, 0],
                      [0, 0, 0, 0, 1, -self.EtaPM, 0],
                      [0, 0, 1, 0, - self.EtaEM, 0, 0],
                      [0, 0, 0, - self.EtaPPmodel(alt,vel,pwr), 0, 0, 1],
                      [phi, 0, 0, 0, 0, phi - 1, 0],
                      [0, 0, 0, 0, 0, 0, 1]])
       
            b = np.array([0, 0, 0, 0, 0, 0, 1])
            
            #Ordine output   Pf/Pp  Pgt/Pp   Pgb/Pp  Ps1/Pp  Pe1/Pp   Pbat/Pp    Pp1/Pp 

        
        elif (self.aircraft.HybridType == 'Serial'):
                        
            A = np.array([[- self.EtaGT, 1, 0, 0, 0, 0, 0, 0],
                      [0, - self.EtaEM1, 0, 1, 0, 0, 0, 0],
                      [0, 0, 0, -self.EtaPM, 1, -self.EtaPM, 0, 0],
                      [0, 0, 1, 0,  - self.EtaEM2, 0, 0, 0],
                      [0, 0, - self.EtaGB, 0, 0, 0, 1, 0],
                      [0, 0, 0, 0, 0, 0, - self.EtaPPmodel(alt,vel,pwr), 1],
                      [phi, 0, 0, 0, 0, phi - 1, 0, 0],
                      [0, 0, 0, 0, 0, 0, 0, 1]])
       
            b = np.array([0, 0, 0, 0, 0, 0, 0, 1])

        
        PowerRatio = np.linalg.solve(A,b)
        
    #Ordine output   Pf/Pp  Pgt/Pp   Pgb/Pp    Pe1/Pp  Pe2/Pp   Pbat/Pp   Ps2/Pp   Pp1/Pp 
        return np.abs(PowerRatio)  #here abs is used to avoid that Pbat/Pp = -0 when phi=0
        
        
    # def ParallelHybrid2(self,t):
        
    #     self.ReadInput()
        
    #     phi = self.aircraft.mission.profile.SuppliedPowerRatio(t)
        
    #     P1 = self.EtaPP / (self.EtaGB*self.EtaGT - (phi/(phi-1))*self.EtaGB*self.EtaPM*self.EtaEM)
    #     P2 = P1 * self.EtaGT
    #     P3 = - (phi/(phi-1)) * self.EtaPM * self.EtaEM * P1
    #     P4 = self.EtaPP
    #     P5 = - (phi/(phi-1)) * self.EtaPM * P1
    #     P6 = - (phi/(phi-1)) * P1
    #     P7 = 1
    #     PowerRatio = [P1, P2, P3, P4, P5, P6, P7]
        
    # #Ordine output   Pf/Pp  Pgt/Pp   Pgb/Pp  Ps1/Pp  Pe1/Pp   Pbat/Pp    Pp1/Pp 
    #     return PowerRatio
    

    def DefinePowertrainSystem(self,alt,vel,PP,eta_PP):
        """
        Auxiliary function that returns the matrix A and the vector B of the linear systems employed in powertrain.Traditional and powertrain.Hybrid

        Presently unused.
        """


        if self.aircraft.Configuration == 'Traditional':
            A = np.array([[- self.EtaGTmodel(alt,vel,PP), 1, 0, 0],
                      [0, - self.EtaGB, 1, 0],
                      [0, 0, - eta_PP, 1],
                      [0, 0, 0, 1]])
       
            b = np.array([0, 0, 0, 1])

        elif self.aircraft.Configuration == 'Hybrid':

            if (self.aircraft.HybridType == 'Parallel'):
            
                A = np.array([[- self.EtaGTmodel(alt,vel,PP), 1, 0, 0, 0, 0, 0],
                        [0, -self.EtaGB, -self.EtaGB, 1, 0, 0, 0],
                        [0, 0, 0, 0, 1, -self.EtaPM, 0],
                        [0, 0, 1, 0, - self.EtaEM, 0, 0],
                        [0, 0, 0, - eta_PP, 0, 0, 1],
                        [self.phi, 0, 0, 0, 0, self.phi - 1, 0],
                        [0, 0, 0, 0, 0, 0, 1]])
        
                b = np.array([0, 0, 0, 0, 0, 0, 1])
                
                #Ordine output   Pf/Pp  Pgt/Pp   Pgb/Pp  Ps1/Pp  Pe1/Pp   Pbat/Pp    Pp1/Pp 

            
            elif (self.aircraft.HybridType == 'Serial'):
                            
                A = np.array([[- self.EtaGT, 1, 0, 0, 0, 0, 0, 0],
                        [0, - self.EtaEM1, 0, 1, 0, 0, 0, 0],
                        [0, 0, 0, -self.EtaPM, 1, -self.EtaPM, 0, 0],
                        [0, 0, 1, 0,  - self.EtaEM2, 0, 0, 0],
                        [0, 0, - self.EtaGB, 0, 0, 0, 1, 0],
                        [0, 0, 0, 0, 0, 0, - eta_PP, 1],
                        [self.phi, 0, 0, 0, 0, self.phi - 1, 0, 0],
                        [0, 0, 0, 0, 0, 0, 0, 1]])
        
                b = np.array([0, 0, 0, 0, 0, 0, 0, 1])

        return A,b



    def WeightPowertrain(self,WTO):
        """
        This function estimates the total weight of the propulsion powertrain based on the aircraft
        configuration (traditional or hybrid) and the maximum required power level.

        This function inherits from the mission class the installed power requirements for the propulsion
        system and converts them into component weights using specific power
        coefficients (shaft-power-to-weight ratios). The methodology differs for
        traditional and hybrid-electric architectures:

        - **Traditional configuration**
          Only the thermal (gas-turbine) powertrain is present. The peak required
          shaft power is determined as the maximum between:
            1. Mission maximum engine power corrected by power lapse, and
            2. Take-Off (TO) required propulsive power.
          The thermal powertrain weight is obtained by dividing this peak shaft
          power by the thermal specific power ratio ``SPowerPT[0]``.

        - **Hybrid configuration**
          Both thermal and electric subsystems are sized independently:
            * Thermal subsystem: same criterion as in traditional case.
            * Electric subsystem: peak battery power is the maximum between mission
              maximum electric power and TO electric power.
          The total powertrain weight is the sum of thermal and electric subsystem
          weights, computed using ``SPowerPT[0]`` and ``SPowerPT[1]`` respectively.

        Parameters
        ----------
        WTO : float
            Take-off weight of the aircraft [kg].  
            (Currently unused inside the method but included for interface
            compatibility.)

        Returns
        -------
        float
            Total estimated powertrain weight [kg]. Fuel and Battery weights are not included.

        Attributes Updated
        ------------------
        engineRating : float
            Rated thermal shaft power required for the mission [W].
        WThermal : float
            Weight of the thermal propulsion subsystem [kg].
        WElectric : float, optional
            Weight of the electric power subsystem (only for hybrid configurations)
            [kg].

        Notes
        -----
        - ``SPowerPT`` is assumed to contain the specific power (W/kg) for thermal
          and electric powertrain components. 
        - ``PowerLapse(alt, vel)`` is used to compute the reduction in available
          GT power with altitude.
        - Raises an exception if an unsupported aircraft configuration is provided.
        """
        
        if self.aircraft.Configuration == 'Traditional':
        
                PeakPwr = np.max(
                    [self.aircraft.mission.Max_PEng / self.PowerLapse(self.aircraft.mission.Max_PEng_alt,0), 
                     self.aircraft.mission.TO_PP]
                     ) #maximum among take-off shaft power and mission shaft-power (adjusted with power-lapse)

                self.engineRating = PeakPwr #shaft power 
                self.WThermal = PeakPwr /self.SPowerPT[0]
                WPT = self.WThermal
                
        elif self.aircraft.Configuration == 'Hybrid':
   
                
                PeakPwrEng = np.max(
                    [self.aircraft.mission.Max_PEng / self.PowerLapse(self.aircraft.mission.Max_PEng_alt,0), 
                     self.aircraft.mission.TO_PP]
                     ) #maximum among take-off shaft power and mission shaft-power (adjusted with power-lapse)
                PeakPwrBat = np.max([self.aircraft.mission.Max_PBat, self.aircraft.mission.TO_PBat])

                self.engineRating = PeakPwrEng #shaft power

                self.WThermal = PeakPwrEng /self.SPowerPT[0]
                self.WElectric = PeakPwrBat /self.SPowerPT[1] 

                WPT = self.WThermal + self.WElectric 

        else:
             raise Exception("Unknown aircraft configuration: %s" %self.aircraft.Configuration)
                
        return WPT
    

