import numpy as np
import PhlyGreen.Utilities.Units as Units

class Paint:

    def __init__(self, aircraft, input):
        self.aircraft = aircraft
        self.input = input  

    def CalcWettedSurface(self):

        # These relations are built upon the data from the Aviary tutorials
        Surface_HTail = self.input['HORIZONTAL_TAIL']['AREA']
        Surface_VTail = self.input['VERTICAL_TAIL']['AREA']
        Surface_Wing = Units.m2toft2(self.input['GROSS_WEIGHT']/self.aircraft.DesignWTOoS)
        fuse_width = self.input['FUSELAGE']['MAX_WIDTH']
        fuse_height = self.input['FUSELAGE']['MAX_HEIGHT']
        fuse_length = self.input['FUSELAGE']['LENGTH']
        nacelle_scaler = self.input['NACELLE']['SCALER']
        num_engines = self.input['ENGINE']['N_ENGINES']
        nacelle_diameter = self.input['NACELLE']['AVG_DIAM']
        nacelle_length = self.input['NACELLE']['AVG_LENGTH']

        fuse_avg_diameter = (fuse_height + fuse_width)/2

        WS_HTail = (Surface_HTail*2)*0.8
        WS_VTail = (Surface_VTail*2)*1.02
        WS_Wing = (Surface_Wing*2)*0.87
        WS_Fuselage = (np.pi*fuse_avg_diameter*fuse_length)*0.8
        WS_Nacelle = nacelle_scaler * 2.8 * num_engines * nacelle_diameter * nacelle_length # TAKEN FROM FLOPS GEOMETRY MODULE

        WettedArea = WS_HTail + WS_VTail + WS_Wing + WS_Fuselage + WS_Nacelle 

        return WettedArea

    def PaintMass(self):

        mass_per_area = self.input['PAINT']['MASS_PER_AREA']

        self.paintmass = self.CalcWettedSurface() * mass_per_area

        return None