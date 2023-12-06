import numpy as np
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed
from scipy.optimize import brentq, brenth, ridder, newton



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
        self.SPowerPMAD = self.aircraft.TechnologyInput['Specific Power PMAD']
        self.PtWPT = self.aircraft.TechnologyInput['PowertoWeight Powertrain']
        self.PtWBat = self.aircraft.TechnologyInput['PowertoWeight Battery']
        self.PtWPMAD = self.aircraft.TechnologyInput['PowertoWeight PMAD']


        return None
        
    def WeightEstimation(self):
        

        if self.aircraft.Configuration == 'Traditional':     
             
        
                 
                 return self.Traditional()
             
             
        elif self.aircraft.Configuration == 'Hybrid':     
                 
                 
                 return self.Hybrid()

        else:
                 return "Try a different configuration..."


    def Traditional(self):
        
        # self.WTO = [0, 16000]
        # WDifference = self.WTO[1] - self.WTO[0]
        # i = 1
        
        def func(WTO):
            
                self.Wf = self.aircraft.mission.EvaluateMission(WTO)/self.ef
                self.WPT = self.aircraft.powertrain.WeightPowertrain(WTO)
                self.WStructure = self.aircraft.structures.StructuralWeight(WTO) + 500 
            
                return (self.Wf + self.WPT + self.WStructure + self.WPayload + self.WCrew - WTO)
        
        self.WTO = brenth(func, 10000, 50000, xtol=0.1)

        # while (WDifference > self.tol):
            
        #     self.Wf = self.aircraft.mission.EvaluateMission(self.WTO[i])/self.ef
        #     # self.WPT = self.PtWPT * self.WTO[i] / self.SPowerPT
        #     # self.WPT =  np.sum(np.divide(self.PtWPT, self.SPowerPT)) * self.WTO[i]
        #     self.WPT = self.aircraft.powertrain.WeightPowertrain(self.WTO[i])
        #     self.WStructure = self.aircraft.structures.StructuralWeight(self.WTO[i]) + 500
        #     self.WTO.append(self.WPayload + self.WCrew + self.Wf + self.WStructure + self.WPT) 
        #     WDifference = np.abs(self.WTO[i+1] - self.WTO[i])
        #     i += 1
            
        #     print('---------------------------------------------------------------------------')
        #     print('Iteration:', i-1)
        #     print('Powertrain: ',self.WPT, 'Fuel: ', self.Wf, 'Structure: ', self.WStructure)
        #     print('Empty Weight: ', self.WPT + self.WStructure + self.WCrew)
        #     print('Total Weight: ', self.WTO[i])
        #     print(func(self.WTO[i]))
            



    
    def Hybrid(self):
        
        def func(WTO):
                self.i += 1
                # if self.i == 10:
                #     WTO += 1200
                print(WTO)
                self.TotalEnergies = self.aircraft.mission.EvaluateMission(WTO)
                self.Wf = self.TotalEnergies[0]/self.ef
                self.WBat  = np.max([self.TotalEnergies[1]/self.ebat , self.PtWBat*(1/self.pbat)*WTO])
                # print(self.TotalEnergies[1]/self.ebat )
                # print(self.PtWBat*(1/self.pbat)*WTO)
                self.WPT = self.aircraft.powertrain.WeightPowertrain(WTO)
                self.WStructure = self.aircraft.structures.StructuralWeight(WTO) + 500 
            
                print(self.i)
                print('energies: ', self.TotalEnergies)
                print('Powertrain: ',self.WPT, 'Fuel: ', self.Wf, 'Battery: ', self.WBat,'Structure: ', self.WStructure)
                print('Empty Weight: ', self.WPT + self.WStructure + self.WCrew)
                print(self.Wf + self.WBat + self.WPT + self.WStructure + self.WPayload + self.WCrew - WTO)
                print('---------------------------------------------------------------------------')

                return (self.Wf + self.WBat + self.WPT + self.WStructure + self.WPayload + self.WCrew - WTO)
         
        self.i = 0
        
        self.WTO = brenth(func, 10000, 150000, xtol=0.1)
        
        print('inizio test')
        

        # self.WTO_vector= [23505.310344827587,23505.379310344826]
        # self.WTO_vector = np.linspace(23000,25000,num=50)
        
        # self.Vector = [func(vec) for vec in self.WTO_vector]
        
        # print ("root is:", self.WTO)
        

        
        # self.WTO = [0, 18000]
        # WDifference = self.WTO[1] - self.WTO[0]
        # i = 1
        
        # while (WDifference > self.tol):
            
        #     # if (i == 30):
                
        #     #     self.WTO[-1] -= 1000
            
            
            
        #     if (i == 100):
                
        #         self.WTO.append(np.mean(self.WTO))
        #         print('Attention! Max number of iteration has been reached')
        #         break
            
        #     self.TotalEnergies = self.aircraft.mission.EvaluateMission(self.WTO[i])
            
        #     self.Wf = self.TotalEnergies[0]/self.ef
        #     self.WBat  = np.max([self.TotalEnergies[1]/self.ebat , self.PtWBat*(1/self.pbat)*self.WTO[i]])
        #     self.WPT = self.aircraft.powertrain.WeightPowertrain(self.WTO[i])
        #     # WPT = self.PtWPT * WTO[i] / self.SPowerPT
        #     # self.WPT =  (np.sum(np.divide(self.PtWPT, self.SPowerPT)) + np.sum(np.divide(self.PtWPMAD, self.SPowerPMAD))) * self.WTO[i] 
        #     self.WStructure = self.aircraft.structures.StructuralWeight(self.WTO[i]) + 500
        #     self.WTO.append(self.WPayload + self.WCrew + self.Wf + self.WStructure + self.WPT + self.WBat) 
        #     WDifference = np.abs(self.WTO[i+1] - self.WTO[i])
        #     i += 1
            
        #     print('---------------------------------------------------------------------------')
        #     print('Iteration:', i-1)
        #     print('Powertrain: ',self.WPT, 'Fuel: ', self.Wf, 'Battery: ', self.WBat,'Structure: ', self.WStructure)
        #     print('Empty Weight: ', self.WPT + self.WStructure + self.WCrew)
        #     print('Total Weight: ', self.WTO[i])
            
