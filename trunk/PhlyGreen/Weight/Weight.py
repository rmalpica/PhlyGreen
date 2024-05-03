import numpy as np
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed
from scipy.optimize import brentq, brenth, ridder, newton
from pprint import pprint


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

                '''#maximum power for the battery, Max_PBat does not include takeoff power
                if self.aircraft.mission.Max_PBat > self.aircraft.mission.TO_PBat:
                    self.MaxBatPwr = self.aircraft.mission.Max_PBat
                    self.TOPwr_or_CruisePwr = "cruise"
                else:
                    self.MaxBatPwr = self.aircraft.mission.TO_PBat
                    self.TOPwr_or_CruisePwr = "takeoff"

                self.aircraft.battery.Configuration(self.TotalEnergies[1],self.MaxBatPwr)
                
                ##everything before here needs to be rewritten to use cell counts instead of power and energy
                # the idea is to simply make use of the number of cells in parallel as if it were the power itself
                # this is because peak power is only representative of one SOC of the battery,
                # while parallel cell nr is representative of the entire power profile over the mission'''
                self.WBat=self.aircraft.battery.pack_weight

                self.WPT = self.aircraft.powertrain.WeightPowertrain(WTO)
                self.WStructure = self.aircraft.structures.StructuralWeight(WTO) 
                if self.final_reserve == 0:
                    self.final_reserve = 0.05*self.Wf

                return (self.Wf + self.final_reserve + self.WBat + self.WPT + self.WStructure + self.WPayload + self.WCrew - WTO)

        self.WTO = brenth(func, 10000, 300000, xtol=0.1) ##this iterates the weight function over and over until it converges on a value of takeoff weight. notice how func() returns the difference between the takeoff weight and the previous takeoff weight. this re-runs the weight function until it returns a difference of weights below 0.1kg. i need to put something somewhere in this loop that tries to increase the number of parallel cells if the power is too low during integration