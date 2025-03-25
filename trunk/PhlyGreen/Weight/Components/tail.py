import PhlyGreen.Utilities.Units as Units

class Tail:

    def __init__(self, aircraft, input):
        self.aircraft = aircraft
        self.input = input  

    def HorizontalTailMass(self):

        sht = self.input['HORIZONTAL_TAIL']['AREA']
        dg = Units.kgTolb(self.input['GROSS_WEIGHT'])
        trht = self.input['HORIZONTAL_TAIL']['TAPER_RATIO']
        scaler = self.input['HORIZONTAL_TAIL']['SCALER']

        self.HTailmass = scaler * 0.53 * sht * (dg**0.2) * (trht + 0.5)  

        return None


    def VerticalTailMass(self):

        svt = self.input['VERTICAL_TAIL']['AREA']
        dg = Units.kgTolb(self.input['GROSS_WEIGHT'])
        trvt = self.input['VERTICAL_TAIL']['TAPER_RATIO'] 
        nvert = self.input['VERTICAL_TAIL']['N_VERTICAL_TAILS']
        scaler = self.input['VERTICAL_TAIL']['SCALER']

        self.VTailmass = scaler * 0.32 * (dg**0.3) * (trvt + 0.5) * (nvert**0.7) * (svt**0.85)

        return None