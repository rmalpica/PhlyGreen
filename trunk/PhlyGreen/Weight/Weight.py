import numpy as np
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed
import PhlyGreen.Utilities.Units as Units
from scipy.optimize import brentq, brenth, ridder, newton
from pprint import pprint
from .FLOPS_model import FLOPS_model

class Weight:
    """
    Aircraft weight estimation module.

    This class estimates the aircraft Take-Off Weight (WTO) by solving the 
    coupled mission-powertrain-structure design problem:

        WTO = W_fuel(WTO) + W_battery(WTO) + W_struct(WTO) + W_powertrain(WTO) + W_payload + W_crew

    The aircraft model and the mission profile determine fuel and battery energy consumption, the 
    powertrain model provides propulsion system mass, and the structural 
    model (or FLOPS surrogate model) provides airframe component masses.

    Two weight estimation classes are supported:

    - Class I:  Simplified regression model from the user's Structures module.
    - Class II: Uses FLOPS-based component mass estimation (empirical).

    Two propulsion configurations are supported:

    - Traditional (thermal only)
    - Hybrid-electric (thermal + electric battery pack)

    Brent's root-finding method is used to find the WTO that satisfies the 
    mass consistency equation above.

    Parameters
    ----------
    aircraft : Aircraft
        Parent aircraft object containing mission, powertrain, structure, and 
        battery models."""
  
    def __init__(self, aircraft):
        self.aircraft = aircraft
        self.tol = 0.1
        self.final_reserve = None  
        self.Class = 'I'
        
            
        
    def SetInput(self):
        """
        Load required user inputs from the aircraft data structure.

        Sets:
        - Payload weight
        - Crew weight
        - Fuel specific energy
        - Contingency fuel or final reserve
        - FLOPS model components (Class II only)
        """
        
        self.WPayload = self.aircraft.MissionInput['Payload Weight']
        self.WCrew = self.aircraft.MissionInput['Crew Weight']
        self.ef = self.aircraft.EnergyInput['Ef']
        self.final_reserve = self.aircraft.EnergyInput['Contingency Fuel']

        if self.Class == 'II':
            self.AircraftComponents = FLOPS_model(self.aircraft)

        return None
        
    def WeightEstimation(self):
        """
         Perform full aircraft weight estimation for the selected configuration.

        Returns
        -------
        float or str
            Converged take-off weight WTO, or a string if configuration is invalid."""
        

        if self.aircraft.Configuration == 'Traditional':     
             
              
                 return self.Traditional()
             
             
        elif self.aircraft.Configuration == 'Hybrid':     
                 
                 
                 return self.Hybrid()

        else:
                 return "Try a different configuration..."


    def Traditional(self):
        """
        Solve the weight equation for a traditional (non-hybrid) 
        propulsion system.

        The objective function is:

            f(WTO) = W_fuel + W_final_reserve + W_powertrain + W_structure
                     + W_payload + W_crew - WTO

        The root of f(WTO) is the correct takeoff weight.

        Returns
        -------
        float
            Converged take-off weight WTO.
        """
        
        # self.WTO = [0, 16000]
        # WDifference = self.WTO[1] - self.WTO[0]
        # i = 1
        
        def func(WTO):
                """
                Weight residual function for use with Brent's method.

                Evaluates:
                 - Mission fuel burn
                 - Propulsion system weight
                 - Structural weight (Class I or II)
                 - Final reserve rule
                """
            
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
        """
        Solve the weight equation for a hybrid-electric aircraft.

        Same logic as Traditional(), but includes battery sizing.

        Battery mass is computed differently depending on battery class:

        - Class I  : analytical battery mass formula
        - Class II : battery pack weight determined by P-number sizing loop
                     inside the mission model

        Returns
        -------
        float
            Converged take-off weight WTO
        """

        def func(WTO):
                """
                Weight residual function evaluated at a given WTO.

                Includes:
                 - fuel mass
                 - battery mass 
                 - propulsion mass
                 - structure mass
                 - payload + crew
                 - reserve fuel
                """

                self.TotalEnergies = self.aircraft.mission.EvaluateMission(WTO)
                self.Wf = self.TotalEnergies[0]/self.ef
                if self.aircraft.battery.BatteryClass == 'II':
                    self.WBat=self.aircraft.battery.pack_weight
                elif self.aircraft.battery.BatteryClass == 'I':
                    WBat  = [(self.TotalEnergies[1]/(1-self.aircraft.battery.SOC_min))/self.aircraft.battery.Ebat , self.aircraft.mission.Max_PBat*(1/self.aircraft.battery.pbat), self.aircraft.mission.TO_PBat*(1/self.aircraft.battery.pbat)]
                    self.WBatidx = np.argmax(WBat)
                    self.WBat = WBat[self.WBatidx] 

                self.WPT = self.aircraft.powertrain.WeightPowertrain(WTO)

                if self.Class == 'I':

                    self.WStructure = self.aircraft.structures.StructuralWeight(WTO)
                    # print('Structural weight: ', self.WStructure) 

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
        self.WTO = brenth(func, 10000, 60000, xtol=0.1) 