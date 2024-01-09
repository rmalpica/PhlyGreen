import numpy as np
import numbers
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed

class Powertrain:
    def __init__(self, aircraft):
        self.aircraft = aircraft
        #thermal powerplant efficiencies
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

    """ Properties """

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
        if(isinstance(value, numbers.Number) and (value <= 0)):
            raise ValueError("Error: Illegal Thermal powertrain Weight: %e. Exiting" %value)

    @property
    def WElectric(self):
        if self._WElectric == None:
            raise ValueError("Electric powertrain Weight unset. Exiting")
        return self._WElectric
      
    @WElectric.setter
    def WElectric(self,value):
        self._WElectric = value
        if(isinstance(value, numbers.Number) and (value <= 0)):
            raise ValueError("Error: Illegal Electric powertrain Weight: %e. Exiting" %value)




    """ Methods """

    def SetInput(self):

        self.EtaGT = self.aircraft.EnergyInput['Eta Gas Turbine']
        self.EtaGB = self.aircraft.EnergyInput['Eta Gearbox']
        self.EtaPP = self.aircraft.EnergyInput['Eta Propulsive']
        self.SPowerPT = self.aircraft.EnergyInput['Specific Power Powertrain']
        self.SPowerPMAD = self.aircraft.EnergyInput['Specific Power PMAD']
        
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

            
            if (self.aircraft.HybridType == 'Parallel'):
        
                self.EtaEM = self.aircraft.EnergyInput['Eta Electric Motor']
                
            if (self.aircraft.HybridType == 'Serial'):
                
                self.EtaEM1 = self.aircraft.EnergyInput['Eta Electric Motor 1']
                self.EtaEM2 = self.aircraft.EnergyInput['Eta Electric Motor 2']

        
        return None
        
        
    def Traditional(self):
        
        #self.ReadInput()
        
        A = np.array([[- self.EtaGT, 1, 0, 0],
                      [0, - self.EtaGB, 1, 0],
                      [0, 0, - self.EtaPP, 1],
                      [0, 0, 0, 1]])
       
        b = np.array([0, 0, 0, 1])
        
        PowerRatio = np.linalg.solve(A,b)

        return PowerRatio
    
    
    def Hybrid(self,phi):
        
        # phi = self.aircraft.mission.profile.SuppliedPowerRatio(t)
        
        if (self.aircraft.HybridType == 'Parallel'):
        
            A = np.array([[- self.EtaGT, 1, 0, 0, 0, 0, 0],
                      [0, -self.EtaGB, -self.EtaGB, 1, 0, 0, 0],
                      [0, 0, 0, 0, 1, -self.EtaPM, 0],
                      [0, 0, 1, 0, - self.EtaEM, 0, 0],
                      [0, 0, 0, - self.EtaPP, 0, 0, 1],
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
                      [0, 0, 0, 0, 0, 0, - self.EtaPP, 1],
                      [phi, 0, 0, 0, 0, phi - 1, 0, 0],
                      [0, 0, 0, 0, 0, 0, 0, 1]])
       
            b = np.array([0, 0, 0, 0, 0, 0, 0, 1])
        
        PowerRatio = np.linalg.solve(A,b)
        
    #Ordine output   Pf/Pp  Pgt/Pp   Pgb/Pp    Pe1/Pp  Pe2/Pp   Pbat/Pp   Ps2/Pp   Pp1/Pp 
        return PowerRatio
        
        
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
    
    def WeightPowertrain(self,WTO):
        
        if self.aircraft.Configuration == 'Traditional':
        
                
                PtWFuel = self.aircraft.DesignPW * self.Traditional()[0]
                
                WPT = PtWFuel * WTO / self.SPowerPT[0]
                
        elif self.aircraft.Configuration == 'Hybrid':
   
                
                PtWFuel = np.max([self.aircraft.mission.Max_PFoW ,self.aircraft.mission.TO_PFoW]) 
                PtWBattery = np.max([self.aircraft.mission.Max_PBatoW, self.aircraft.mission.TO_PBatoW])
                #PtWFuel = self.aircraft.mission.Max_PFoW
                #PtWBattery = self.aircraft.mission.Max_PBatoW
                # PtWPMAD = self.aircraft.DesignPW * self.Hybrid(0.05)[3]
                self.WThermal = PtWFuel * self.EtaGT /self.SPowerPT[0]
                self.WElectric = PtWBattery/self.SPowerPT[1] * self.EtaEM * self.EtaPM

                WPT = self.WThermal + self.WElectric 

                #versione general purpose (mancano i rendimenti)
                #PtWPT = [PtWFuel, PtWBattery]

                ## WPT =  (np.sum(np.divide(PtWPT, self.SPowerPT)) + PtWPMAD  / self.SPowerPMAD[0]) * WTO  # Pesa un botto
                #WPT =  np.sum(np.divide(PtWPT, self.SPowerPT)) 
        else:
             raise Exception("Unknown aircraft configuration: %s" %self.aircraft.Configuration)
                
        return WPT
