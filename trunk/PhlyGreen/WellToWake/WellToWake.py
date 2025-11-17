import numpy as np
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed


class WellToWake:
    """
    Computes well-to-wake (WTW) energy requirements and energy sourcing
    fractions for hybrid or conventional aircraft propulsion systems.

    This module sits at the end of the sizing loop and quantifies primary
    energy demand upstream of the aircraft:

        - Require Well-to-tank efficiencies for fuel production and delivery
        - Require Grid and charger efficiencies for battery electricity
        - Return Total well-to-wake energy demand
        - Return Fraction of energy sourced from electricity vs. fuel

    The class requires:
        * aircraft.weight.TotalEnergies = [E_fuel_used, E_battery_used]
        computed during mission analysis.

    Outputs:
        Psi  = battery energy fraction (0-1)
        SourceEnergy = total primary energy required upstream
                       (for a given mission)

    Notes
    -----
    The WTW module intentionally does not compute emissions directly.
    That occurs downstream once CO2-eq or pollutant intensities are applied.
    """
    
    def __init__(self, aircraft):
        self.aircraft = aircraft
        
    
    def SetInput(self):
        """
        Loads well-to-tank efficiencies from aircraft input and computes
        combined upstream efficiencies for the two relevant pathways:

            - Source → Grid → Charger → Battery
            - Source → Extraction → Production → Transport → Fuel Tank
        """
        
        # Electricity pathway
        self.EtaCH = self.aircraft.WellToTankInput['Eta Charge']            # Charger eff.
        self.EtaGR = self.aircraft.WellToTankInput['Eta Grid']              # Grid generation & distribution eff.

        # Fuel pathway
        self.EtaEX = self.aircraft.WellToTankInput['Eta Extraction']        # Resource extraction eff.
        self.EtaPR = self.aircraft.WellToTankInput['Eta Production']        # Fuel production / refining eff.
        self.EtaTR = self.aircraft.WellToTankInput['Eta Transportation']    # Distribution/logistics eff.
    
        # Aggregate efficiencies
        self.EtaSourceToBattery = self.EtaCH * self.EtaGR
        self.EtaSourceToFuel = self.EtaEX * self.EtaPR * self.EtaTR
        
        
    def EvaluateSource(self):
        """
        Computes the primary energy demand (well-to-wake) required to
        supply the mission's fuel and battery energy.

        Requires:
        ---------
        aircraft.weight.TotalEnergies = [E_fuel, E_battery]

        Outputs:
        --------
        SourceFuel    : upstream energy needed to produce delivered fuel
        SourceBattery : upstream energy needed to deliver electrical energy
        Psi           : fraction of energy from electricity (0-1)
        SourceEnergy  : total well-to-wake energy demand
        """
                
        SourceFuel = self.aircraft.weight.TotalEnergies[0] / self.EtaSourceToFuel
        SourceBattery = self.aircraft.weight.TotalEnergies[1] / self.EtaSourceToBattery 
        
        self.Psi = SourceBattery / (SourceBattery + SourceFuel)
        self.SourceEnergy = SourceFuel + SourceBattery