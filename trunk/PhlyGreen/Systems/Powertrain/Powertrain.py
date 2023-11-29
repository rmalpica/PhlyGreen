import numpy as np
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed

class Powertrain:
    def __init__(self, aircraft):
        self.aircraft = aircraft

    def start(self):
        print("Powertrain started")

    def stop(self):
        print("Powertrain stopped")


    def ReadInput(self):
        
        self.EtaGT = self.aircraft.TechnologyInput['Eta Gas Turbine']
        self.EtaGB = self.aircraft.TechnologyInput['Eta Gearbox']
        self.EtaPP = self.aircraft.TechnologyInput['Eta Propulsive']
        self.SPowerPT = self.aircraft.TechnologyInput['Specific Power Powertrain']
        self.SPowerPMAD = self.aircraft.TechnologyInput['Specific Power PMAD']
        
        if self.aircraft.WellToTankInput is not None:
            
            self.EtaCH = self.aircraft.WellToTankInput['Eta Charge']
            self.EtaGR = self.aircraft.WellToTankInput['Eta Grid']
            self.EtaEX = self.aircraft.WellToTankInput['Eta Extraction']
            self.EtaPR = self.aircraft.WellToTankInput['Eta Production']
            self.EtaTR = self.aircraft.WellToTankInput['Eta Transportation']
            
            self.EtaSourceToBattery = self.EtaCH * self.EtaGR
            self.EtaSourceToFuel = self.EtaEX * self.EtaPR * self.EtaTR


        
        if (self.aircraft.Configuration == 'Hybrid'):
            
            self.EtaPM = self.aircraft.TechnologyInput['Eta PMAD']

            
            if (self.aircraft.HybridType == 'Parallel'):
        
                self.EtaEM = self.aircraft.TechnologyInput['Eta Electric Motor']
                
            if (self.aircraft.HybridType == 'Serial'):
                
                self.EtaEM1 = self.aircraft.TechnologyInput['Eta Electric Motor 1']
                self.EtaEM2 = self.aircraft.TechnologyInput['Eta Electric Motor 2']

        
        return None
        
        
    def Traditional(self):
        
        self.ReadInput()
        
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
        
        match self.aircraft.Configuration:
            
            case 'Traditional':
                
                PtWFuel = self.aircraft.constraint.DesignPW * self.Traditional()[0]
                
                WPT = PtWFuel * WTO / self.SPowerPT[0]
                
            case 'Hybrid':  # WORK IN PROGRESS
                
                PtWFuel = self.aircraft.constraint.DesignPW * self.Hybrid(0.15)[0]
                PtWBattery = self.aircraft.constraint.DesignPW * self.Hybrid(0.15)[5]
                PtWPMAD = self.aircraft.constraint.DesignPW * self.Hybrid(0.15)[3]
                
                PtWPT = [PtWFuel, PtWBattery]

                # WPT =  (np.sum(np.divide(PtWPT, self.SPowerPT)) + PtWPMAD  / self.SPowerPMAD[0]) * WTO  # Pesa un botto
                WPT =  np.sum(np.divide(PtWPT, self.SPowerPT)) * WTO
                
        return WPT
    

        

        