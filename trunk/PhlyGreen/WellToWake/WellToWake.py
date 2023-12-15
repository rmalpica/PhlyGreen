import numpy as np
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed


class WellToWake:
    
    def __init__(self, aircraft):
        self.aircraft = aircraft
        
    
    def SetInput(self):
        
        
        self.EtaCH = self.aircraft.WellToTankInput['Eta Charge']
        self.EtaGR = self.aircraft.WellToTankInput['Eta Grid']
        self.EtaEX = self.aircraft.WellToTankInput['Eta Extraction']
        self.EtaPR = self.aircraft.WellToTankInput['Eta Production']
        self.EtaTR = self.aircraft.WellToTankInput['Eta Transportation']
    
        self.EtaSourceToBattery = self.EtaCH * self.EtaGR
        self.EtaSourceToFuel = self.EtaEX * self.EtaPR * self.EtaTR
        
        
    def EvaluateSource(self):
                
        SourceFuel = self.aircraft.weight.TotalEnergies[0] / self.EtaSourceToFuel
        SourceBattery = self.aircraft.weight.TotalEnergies[1] / self.EtaSourceToBattery 
        
        self.Psi = SourceBattery / (SourceBattery + SourceFuel)
        self.SourceEnergy = SourceFuel + SourceBattery