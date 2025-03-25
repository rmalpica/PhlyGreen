import numpy as np
import PhlyGreen.Utilities.Units as Units

class Propeller:

    def __init__(self, aircraft, input):
        self.aircraft = aircraft
        self.input = input  

    def PropellerMass(self):

        N_engines = self.input['ENGINE']['N_ENGINES']
        Thrust_sls = self.input['ENGINE']['MAX_SLS_POWER']
        Prop_diameter = self.input['PROPELLER']['DIAMETER']
        N_blades = self.input['PROPELLER']['N_BLADES']
        scaler = self.input['PROPELLER']['SCALER']

        WBlades = 1.1*(Prop_diameter * Thrust_sls * N_blades**0.5)**0.52
        WController = 0.322 * N_blades**0.589 * (Prop_diameter*Thrust_sls*1e-3)**1.178

        self.propellermass = (WBlades + WController) * N_engines * scaler
        return None