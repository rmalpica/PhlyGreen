import numpy as np
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed
from scipy.optimize import fsolve


class Weight:
  
    def __init__(self, aircraft):
        self.aircraft = aircraft
        self.tol = 0.1
        
            
        
    def ReadInput(self):
        
        self.WPayload = self.aircraft.WPayload
        self.WCrew = self.aircraft.WCrew
        self.ef = self.aircraft.ef
        self.SPowerPT = self.aircraft.SPowerPT
        self.PtWPT = self.aircraft.PtWPT
        return None
        
    def WeightEstimation(self):
        
        self.ReadInput()
        
        WTO = [0, 16000]
        WDifference = WTO[1] - WTO[0]
        i = 1
        
        while (WDifference > self.tol):
            
            Ef = self.aircraft.mission.EvaluateMission(WTO[i])
            WPT = self.PtWPT * WTO[i] / self.SPowerPT
            WTO.append(self.WPayload + self.WCrew + Ef/self.ef + self.aircraft.structures.StructuralWeight(WTO[i]) + WPT) 
            # WTO[i+1] = self.WPayload + self.WCrew + Ef/self.ef + self.aircraft.structures.StructuralWeight(WTO[i])
            WDifference = np.abs(WTO[i+1] - WTO[i])
            i += 1
            
            print('Powertrain: ',WPT, 'Fuel: ', Ef/self.ef, 'Structure: ', self.aircraft.structures.StructuralWeight(WTO[i]))
            print('Empty Weight: ', WPT + self.aircraft.structures.StructuralWeight(WTO[i]) + self.WCrew)

        
        
        return WTO
