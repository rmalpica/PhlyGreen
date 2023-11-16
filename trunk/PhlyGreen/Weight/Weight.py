import numpy as np
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed



class Weight:
  
    def __init__(self, aircraft):
        self.aircraft = aircraft
        self.tol = 1
        
            
        
    def ReadInput(self):
        
        self.WPayload = self.aircraft.MissionInput['Payload Weight']
        self.WCrew = self.aircraft.MissionInput['Crew Weight']
        self.ef = self.aircraft.TechnologyInput['Ef']
        self.ebat = self.aircraft.TechnologyInput['Ebat']
        self.pbat = self.aircraft.TechnologyInput['pbat']
        self.SPowerPT = self.aircraft.TechnologyInput['Specific Power Powertrain']
        self.SPowerPMAD = self.aircraft.TechnologyInput['Specific Power PMAD']
        self.PtWPT = self.aircraft.TechnologyInput['PowertoWeight Powertrain']
        self.PtWBat = self.aircraft.TechnologyInput['PowertoWeight Battery']
        self.PtWPMAD = self.aircraft.TechnologyInput['PowertoWeight PMAD']


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
        
        self.WTO = [0, 16000]
        WDifference = self.WTO[1] - self.WTO[0]
        i = 1
        
        while (WDifference > self.tol):
            
            self.Wf = self.aircraft.mission.EvaluateMission(self.WTO[i])/self.ef
            # self.WPT = self.PtWPT * self.WTO[i] / self.SPowerPT
            # self.WPT =  np.sum(np.divide(self.PtWPT, self.SPowerPT)) * self.WTO[i]
            self.WPT = self.aircraft.powertrain.WeightPowertrain(self.WTO[i])
            self.WStructure = self.aircraft.structures.StructuralWeight(self.WTO[i]) + 500
            self.WTO.append(self.WPayload + self.WCrew + self.Wf + self.WStructure + self.WPT) 
            WDifference = np.abs(self.WTO[i+1] - self.WTO[i])
            i += 1
            
            # print('---------------------------------------------------------------------------')
            # print('Iteration:', i-1)
            # print('Powertrain: ',self.WPT, 'Fuel: ', self.Wf, 'Structure: ', self.WStructure)
            # print('Empty Weight: ', self.WPT + self.WStructure + self.WCrew)
            # print('Total Weight: ', self.WTO[i])
    
    
    def Hybrid(self):
        
        self.WTO = [0, 17500]
        WDifference = self.WTO[1] - self.WTO[0]
        i = 1
        
        while (WDifference > self.tol):
            
            if (i == 100):
                
                self.WTO.append(np.mean(self.WTO))
                print('Attention! Max number of iteration has been reached')
                break
            
            self.TotalEnergies = self.aircraft.mission.EvaluateMission(self.WTO[i])
            
            self.Wf = self.TotalEnergies[0]/self.ef
            self.WBat  = np.max([self.TotalEnergies[1]/self.ebat , self.PtWBat*(1/self.pbat)*self.WTO[i]])
            self.WPT = self.aircraft.powertrain.WeightPowertrain(self.WTO[i])
            # WPT = self.PtWPT * WTO[i] / self.SPowerPT
            # self.WPT =  (np.sum(np.divide(self.PtWPT, self.SPowerPT)) + np.sum(np.divide(self.PtWPMAD, self.SPowerPMAD))) * self.WTO[i] 
            self.WStructure = self.aircraft.structures.StructuralWeight(self.WTO[i]) + 500
            self.WTO.append(self.WPayload + self.WCrew + self.Wf + self.WStructure + self.WPT + self.WBat) 
            WDifference = np.abs(self.WTO[i+1] - self.WTO[i])
            i += 1
            
            # print('---------------------------------------------------------------------------')
            # print('Iteration:', i-1)
            # print('Powertrain: ',self.WPT, 'Fuel: ', self.Wf, 'Battery: ', self.WBat,'Structure: ', self.WStructure)
            # print('Empty Weight: ', self.WPT + self.WStructure + self.WCrew)
            # print('Total Weight: ', self.WTO[i])
            
