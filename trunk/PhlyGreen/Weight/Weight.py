import numpy as np
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed
import PhlyGreen.Utilities.Units as Units
from scipy.optimize import brentq, brenth, ridder, newton
from pprint import pprint
from .FLOPS_model import FLOPS_model

class Weight:
  
    def __init__(self, aircraft):
        self.aircraft = aircraft
        self.tol = 0.1
        self.final_reserve = None  
        self.Class = 'I'
        
            
        
    def SetInput(self):
        
        self.WPayload = self.aircraft.MissionInput['Payload Weight']
        self.WCrew = self.aircraft.MissionInput['Crew Weight']
        self.ef = self.aircraft.EnergyInput['Ef']
        self.final_reserve = self.aircraft.EnergyInput['Contingency Fuel']

        if self.Class == 'II':
            self.AircraftComponents = FLOPS_model(self.aircraft)

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

                if self.Class == 'I':

                    self.WStructure = self.aircraft.structures.StructuralWeight(WTO) 

                elif self.Class == 'II':

                    self.aircraft.FLOPSInput['GROSS_WEIGHT'] = WTO # UNITS KG 

                    self.AircraftComponents.SetInput()

                    self.AircraftComponents.CalculateComponentMasses()

                    self.WStructure =  Units.lbTokg(self.AircraftComponents.Wing.wingmass + self.AircraftComponents.Fuselage.fuselagemass
                                                    + self.AircraftComponents.Tail.HTailmass + self.AircraftComponents.Tail.VTailmass 
                                                    + self.AircraftComponents.LandingGear.Landing_gearmass + self.AircraftComponents.Nacelle.nacellemass
                                                    + self.AircraftComponents.Paint.paintmass + self.AircraftComponents.SystemEquipment.system_equipment_mass
                                                    + self.AircraftComponents.Propeller.propellermass) 


                if self.final_reserve == 0:
                    self.final_reserve = 0.05*self.Wf
                
                return (self.Wf + self.final_reserve + self.WPT + self.WStructure + self.WPayload + self.WCrew - WTO)
        
        self.WTO = brenth(func, 1000, 300000, xtol=0.1)


    def Hybrid(self):

        def func(WTO):

                self.TotalEnergies = self.aircraft.mission.EvaluateMission(WTO)
                self.Wf = self.TotalEnergies[0]/self.ef
                if self.aircraft.battery.BatteryClass == 'II':
                    self.WBat=self.aircraft.battery.pack_weight
                elif self.aircraft.battery.BatteryClass == 'I':
                    WBat  = [self.TotalEnergies[1]/self.aircraft.battery.Ebat , self.aircraft.mission.Max_PBat*(1/self.aircraft.battery.pbat), self.aircraft.mission.TO_PBat*(1/self.aircraft.battery.pbat)]
                    self.WBatidx = np.argmax(WBat)
                    self.WBat = WBat[self.WBatidx] 

                self.WPT = self.aircraft.powertrain.WeightPowertrain(WTO)

                if self.Class == 'I':

                    self.WStructure = self.aircraft.structures.StructuralWeight(WTO) 

                elif self.Class == 'II':

                    self.aircraft.FLOPSInput['GROSS_WEIGHT'] = WTO # UNITS KG 

                    self.AircraftComponents.SetInput()

                    self.AircraftComponents.CalculateComponentMasses()

                    self.WStructure =  Units.lbTokg(self.AircraftComponents.Wing.wingmass + self.AircraftComponents.Fuselage.fuselagemass
                                                    + self.AircraftComponents.Tail.HTailmass + self.AircraftComponents.Tail.VTailmass 
                                                    + self.AircraftComponents.LandingGear.Landing_gearmass + self.AircraftComponents.Nacelle.nacellemass
                                                    + self.AircraftComponents.Paint.paintmass + self.AircraftComponents.SystemEquipment.system_equipment_mass
                                                    + self.AircraftComponents.Propeller.propellermass) 

                if self.final_reserve == 0:
                    self.final_reserve = 0.05*self.Wf

                return (self.Wf + self.final_reserve + self.WBat + self.WPT + self.WStructure + self.WPayload + self.WCrew - WTO)
        # this iterates the weight estimator function with the brent method until it converges on a value of takeoff weight
        self.WTO = brenth(func, 1000, 60000, xtol=0.1) 