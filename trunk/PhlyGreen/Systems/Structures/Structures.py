class Structures:
    """ The Structures class. 

    This class provides models for the Class I estimation of the aircraft mass. 
    Such models are usually correlation-based models that return a rough estimte of the aircraft empty mass as a fraction of the take-off mass.
    Different models exist based on the aircraft size (e.g., regional, narrow-body, wide-body, freighter, etc.)

    """
    def __init__(self, aircraft):
        self.aircraft = aircraft


    def StructuralWeight(self,WTO):
        """
        Returns aircraft empty mass in kg. Presently, two models are implemented: 
        - 'ATR' is a model we used for replicating the ATR42-600 empty mass
        - 'DO228' is a model we used for replicating the Dornier 228 empty mass
        - 'Jet' is a classic model for jetliners
        - 'TwinTP' is a classic model for twin turboprops

        """
        
        if self.aircraft.AircraftType == 'ATR':

            return (WTO**(-0.06) * WTO)
        
        if self.aircraft.AircraftType == 'DO228':

            return WTO*0.545

        if self.aircraft.AircraftType == 'Jet':

            return (0.97*WTO**(-0.06) * WTO)
        
        if self.aircraft.AircraftType == 'TwinTP':

            return (0.92*WTO**(-0.05) * WTO)
    
