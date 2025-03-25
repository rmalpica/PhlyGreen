import PhlyGreen.Utilities.Units as Units

class LandingGear:

    def __init__(self, aircraft, input):
        self.aircraft = aircraft
        self.input = input

    def LandingGearMass(self):

        main_scaler = self.input['LANDING_GEAR']['MAIN_SCALER']
        nose_scaler = self.input['LANDING_GEAR']['NOSE_SCALER']
        landing_weight = Units.kgTolb(self.input['GROSS_WEIGHT']) * self.aircraft.mission.Beta[-1]
        main_gear_length = self.input['LANDING_GEAR']['MAIN_GEAR_LENGTH']
        nose_gear_length = self.input['LANDING_GEAR']['NOSE_GEAR_LENGTH']

        MainGear = main_scaler * 0.0117 * landing_weight**0.95 * main_gear_length**0.43 
        NoseGear = nose_scaler * 0.048 * landing_weight**0.67 * nose_gear_length**0.43

        self.Landing_gearmass = NoseGear + MainGear

        return None