import numpy as np
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed
from scipy.optimize import brentq, brenth, ridder, newton



class Weight:
  
    def __init__(self, aircraft):
        self.aircraft = aircraft
        self.tol = 0.1
        self.final_reserve = None  
        
            
        
    def SetInput(self):
        
        self.WPayload = self.aircraft.MissionInput['Payload Weight']
        self.WCrew = self.aircraft.MissionInput['Crew Weight']
        self.ef = self.aircraft.EnergyInput['Ef']
        self.final_reserve = self.aircraft.EnergyInput['Contingency Fuel']
        if (self.aircraft.Configuration == 'Hybrid'):
            pass
        #  put something here that activates the battery class?

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
                self.WStructure = self.aircraft.structures.StructuralWeight(WTO)  
                if self.final_reserve == 0:
                    self.final_reserve = 0.05*self.Wf
                
                return (self.Wf + self.final_reserve + self.WPT + self.WStructure + self.WPayload + self.WCrew - WTO)
        
        self.WTO = brenth(func, 5000, 50000, xtol=0.1)

       
    
    def Hybrid(self):
        
        def func(WTO):
                self.TotalEnergies = self.aircraft.mission.EvaluateMission(WTO)
                self.Wf = self.TotalEnergies[0]/self.ef

                WBat  = [self.TotalEnergies[1]/self.ebat , self.aircraft.mission.Max_PBat*(1/self.pbat), self.aircraft.mission.TO_PBat*(1/self.pbat)]

                self.MaxBatPwr=np.max([self.aircraft.mission.Max_PBat,self.aircraft.mission.TO_PBat])#maximum power for the battery, Max_PBat does not include takeoff power
                self.ConfigBat  = self.aircraft.Battery.Configuration(self.TotalEnergies[1],self.MaxBatPwr) #passes the battery requirements to the configurator
                self.WBat=self.ConfigBat.pack_weight

                # print(self.TotalEnergies[1]/self.ebat )
                # print(self.PtWBat*(1/self.pbat)*WTO)
                self.WPT = self.aircraft.powertrain.WeightPowertrain(WTO)
                self.WStructure = self.aircraft.structures.StructuralWeight(WTO) 
                if self.final_reserve == 0:
                    self.final_reserve = 0.05*self.Wf
                 
                #print('energies: ', self.TotalEnergies)
                #print('Powertrain: ',self.WPT, 'Fuel: ', self.Wf, 'Battery: ', self.WBat,'Structure: ', self.WStructure)
                #print('Empty Weight: ', self.WPT + self.WStructure + self.WCrew)
                #print(self.Wf + self.WBat + self.WPT + self.WStructure + self.WPayload + self.WCrew - WTO)
                #print('---------------------------------------------------------------------------')

                return (self.Wf + self.final_reserve + self.WBat + self.WPT + self.WStructure + self.WPayload + self.WCrew - WTO)
         
        
        self.WTO = brenth(func, 10000, 300000, xtol=0.1)
        
        