class Structures:
    """ The Structures class. 

    This class provides models for the Class I estimation of the aircraft mass. 
    Such models are usually correlation-based models that return a rough estimte of the aircraft empty mass as a fraction of the take-off mass.
    Different models exist based on the aircraft size (e.g., regional, narrow-body, wide-body, freighter, etc.)

    """
    def __init__(self, aircraft):
        self.aircraft = aircraft
        # Multiplier on the Class-I empty-weight regression. 1.0 is the textbook correlation.
        # Any other value is a CALIBRATION to a specific reference aircraft and must be declared
        # as such wherever the result is reported -- a calibrated empty weight is no longer an
        # independent prediction of it.
        self.calibration = 1.0


    # Every Class-I model here is an *empty-weight* regression (We/W0), and an empty weight
    # by definition includes the installed powertrain. Adding Weight.WPT on top of it therefore
    # double-counts the engines. Which models this applies to is declared here rather than
    # assumed at the call site.
    INCLUDES_POWERTRAIN = {'ATR': True, 'DO228': True, 'Jet': True, 'TwinTP': True,
                           'NarrowBody': True}

    # We/W0 = A * W0^C, least-squares fit in log space to six in-service narrow-body
    # transports (MTOW, OEW in kg), each reproduced within 2 %:
    #   A319-100   75 500 / 40 800      B737-700    70 080 / 38 147
    #   A320-200   78 000 / 42 600      B737-800    79 010 / 41 410
    #   A321-200   93 500 / 48 500      B737-900ER  85 130 / 44 676
    # These are secondary-source figures (see validation/a320_reference.md). This is a fit to
    # a population of aircraft, not a calibration to one design's answer.
    NARROW_BODY_FIT = (4.2747, -0.1844)

    def includes_powertrain(self):
        """True when this aircraft type's regression already contains the powertrain mass."""
        return self.INCLUDES_POWERTRAIN.get(self.aircraft.AircraftType, False)

    def StructuralWeight(self,WTO):
        """
        Returns aircraft EMPTY mass in kg (structure + systems + installed powertrain).
        Presently, five models are implemented: 
        - 'ATR' is a model we used for replicating the ATR42-600 empty mass
        - 'DO228' is a model we used for replicating the Dornier 228 empty mass
        - 'Jet' is a classic textbook model for jetliners
        - 'TwinTP' is a classic model for twin turboprops
        - 'NarrowBody' is a regression fitted to modern narrow-body transports

        The textbook 'Jet' fraction is a poor fit for a modern narrow-body: it gives
        We/W0 = 0.495 at 78 t against ~0.546 for an A320-200, i.e. it under-predicts the empty
        weight by about 10 %. 'NarrowBody' is fitted to six in-service aircraft instead (see
        NARROW_BODY_FIT) and reproduces all six within 2 %. Use 'Jet' only when you want the
        textbook correlation.
        """
        
        k = self.calibration

        if self.aircraft.AircraftType == 'ATR':

            return k * (WTO**(-0.06) * WTO)
        
        if self.aircraft.AircraftType == 'DO228':

            return k * (WTO*0.545)

        if self.aircraft.AircraftType == 'Jet':

            return k * (0.97*WTO**(-0.06) * WTO)
        
        if self.aircraft.AircraftType == 'TwinTP':

            return k * (0.92*WTO**(-0.05) * WTO)

        if self.aircraft.AircraftType == 'NarrowBody':

            A, C = self.NARROW_BODY_FIT
            return k * (A * WTO**C * WTO)

        raise ValueError(
            f"Unknown AircraftType {self.aircraft.AircraftType!r}. Expected one of "
            f"'ATR', 'DO228', 'Jet', 'TwinTP', 'NarrowBody'.")
    
