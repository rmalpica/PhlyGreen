import numpy as np
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed



class Weight:
  
    def __init__(self, aircraft):
        self.aircraft = aircraft
        self.tol = 0.1
        
            
        
    def ReadInput(self):
        
        self.WPayload = self.aircraft.MissionInput['Payload Weight']
        self.WCrew = self.aircraft.MissionInput['Crew Weight']
        self.ef = self.aircraft.TechnologyInput['Ef']
        self.ebat = self.aircraft.TechnologyInput['Ebat']
        self.pbat = self.aircraft.TechnologyInput['pbat']
        self.SPowerPT = self.aircraft.TechnologyInput['Specific Power Powertrain']
        self.PtWPT = self.aircraft.TechnologyInput['PowertoWeight Powertrain']
        self.PtWBat = self.aircraft.TechnologyInput['PowertoWeight Battery']

        return None
        
    def WeightEstimation(self):
        

        match self.aircraft.Configuration:     # DA PYTHON 3.10 IN POI.......
             
             case 'Traditional':
                 
                 return self.Traditional()
             
             
             case 'Hybrid':
                 
                 
                 return self.Hybrid()

             case _:
                 return "Try a different configuration..."


    def Traditional(self):
        
        WTO = [0, 16000]
        WDifference = WTO[1] - WTO[0]
        i = 1
        
        while (WDifference > self.tol):
            
            Wf = self.aircraft.mission.EvaluateMission(WTO[i])/self.ef
            WPT = self.PtWPT * WTO[i] / self.SPowerPT
            WStructure = self.aircraft.structures.StructuralWeight(WTO[i])
            WTO.append(self.WPayload + self.WCrew + Wf + WStructure + WPT) 
            WDifference = np.abs(WTO[i+1] - WTO[i])
            i += 1
            
        return WTO
    
    
    def Hybrid(self):
        
        WTO = [0, 17500]
        WDifference = WTO[1] - WTO[0]
        i = 1
        
        while (WDifference > self.tol):
            
            TotalEnergies = self.aircraft.mission.EvaluateMission(WTO[i])
            
            Wf = TotalEnergies[0]/self.ef
            WBat  = np.max([TotalEnergies[1]/self.ebat , self.PtWBat*(1/self.pbat)*WTO[i]])
            WPT = self.PtWPT * WTO[i] / self.SPowerPT
            WStructure = self.aircraft.structures.StructuralWeight(WTO[i])
            WTO.append(self.WPayload + self.WCrew + Wf + WStructure + WPT + WBat) 
            WDifference = np.abs(WTO[i+1] - WTO[i])
            i += 1
            
            print('---------------------------------------------------------------------------')
            print('Iteration:', i-1)
            print('Powertrain: ',WPT, 'Fuel: ', Wf, 'Battery: ',WBat,'Structure: ', WStructure)
            print('Empty Weight: ', WPT + WStructure + self.WCrew)
            
        return WTO