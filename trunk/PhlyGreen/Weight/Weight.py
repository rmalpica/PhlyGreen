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
            
            Wf = self.aircraft.mission.EvaluateMission(WTO[i])/self.ef
            WPT = self.PtWPT * WTO[i] / self.SPowerPT
            WStructure = self.aircraft.structures.StructuralWeight(WTO[i])
            WTO.append(self.WPayload + self.WCrew + Wf + WStructure + WPT) 
            WDifference = np.abs(WTO[i+1] - WTO[i])
            i += 1
            
            # print('Powertrain: ',WPT, 'Fuel: ', Wf, 'Structure: ', WStructure)
            # print('Empty Weight: ', WPT + WStructure + self.WCrew)

        
        
        return WTO
