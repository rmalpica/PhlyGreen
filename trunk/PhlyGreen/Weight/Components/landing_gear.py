"""FLOPS landing-gear mass (Aviary ``landing_gear.py``, ``landing_mass.py``), imperial units."""

import numpy as np
import PhlyGreen.Utilities.Units as Units
from .sizing_inputs import design_mach, design_range_nm


class LandingGear:

    def __init__(self, aircraft, input):
        self.aircraft = aircraft
        self.input = input

    def design_landing_weight_lb(self):
        """FLOPS design landing weight [lb]: the gross weight times 1 - c * R, with R the design
        range [nm] and c = 5e-5 / (1 + exp(-1000 (M - 1))) + 4e-5 (about 4e-5 subsonic)."""
        mach = design_mach(self.aircraft)
        cruise_factor = 5e-5 / (1.0 + np.exp(-1000.0 * (mach - 1.0))) + 4e-5
        ratio = 1.0 - cruise_factor * design_range_nm(self.aircraft)
        return Units.kgTolb(self.input['GROSS_WEIGHT']) * ratio

    def LandingGearMass(self):
        """Main and nose gear mass [lb]; the gear lengths are the oleo lengths in inches."""
        main_scaler = self.input['LANDING_GEAR']['MAIN_SCALER']
        nose_scaler = self.input['LANDING_GEAR']['NOSE_SCALER']
        landing_weight = self.design_landing_weight_lb()
        main_gear_length = self.input['LANDING_GEAR']['MAIN_GEAR_LENGTH']
        nose_gear_length = self.input['LANDING_GEAR']['NOSE_GEAR_LENGTH']

        MainGear = main_scaler * 0.0117 * landing_weight**0.95 * main_gear_length**0.43
        NoseGear = nose_scaler * 0.048 * landing_weight**0.67 * nose_gear_length**0.43

        self.Landing_gearmass = NoseGear + MainGear

        return None
