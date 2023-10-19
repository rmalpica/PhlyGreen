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
        
        self.EtaGT = self.aircraft.EtaGT
        self.EtaGB = self.aircraft.EtaGB
        self.EtaPP = self.aircraft.EtaPP

        
        return None
        
        
    def Traditional(self):
        
        self.ReadInput()
        
        A = np.array([[- self.EtaGT, 1, 0, 0],[0, - self.EtaGB, 1, 0],[0, 0, - self.EtaPP, 1],[0, 0, 0, 1]])
        b = np.array([0, 0, 0, 1])
        
        PowerRatio = np.linalg.solve(A,b)

        return PowerRatio
    

        
        
        