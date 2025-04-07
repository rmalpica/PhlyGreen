import numpy as np
import PhlyGreen.Utilities.Units as Units

class Wing:

    def __init__(self, aircraft, input):
        self.aircraft = aircraft
        self.input = input
        self.A1 = 8.80 
        self.A2 = 6.25
        self.A3 = 0.68
        self.A4 = 0.34
        self.A5 = 0.6
        self.A6 = 0.035
        self.A7 = 1.5


    def BendingMaterialFactor(self):
            
        fstrt = self.input['WING']['STRUT_BRACING_FACTOR'] # non so che è
        span = self.input['WING']['SPAN'] # ce l'abbiamo
        tr = self.input['WING']['TAPER_RATIO'] # ce lo possiamo avere
        area = Units.m2toft2(self.input['GROSS_WEIGHT']/self.aircraft.DesignWTOoS) # ce l'abbiamo
        tca = self.input['WING']['THICKNESS_TO_CHORD'] # potremmo avercelo
        faert = self.input['WING']['AEROELASTIC_TAILORING_FACTOR'] # chi sei?
        ar = self.aircraft.aerodynamics.AR # ce l'abbiamo
        sweep = self.input['WING']['SWEEP'] # ce l'abbiamo

        C4 = 1.0 - 0.5 * faert
        C6 = 0.5 * faert - 0.16 * fstrt

        if ar <= 5.0:
            caya = 0.0
        else:
            caya = ar - 5.0

        tlam = np.tan(np.pi / 180. * sweep) - 2 * (1 - tr) / (ar * (1 + tr))

        slam = tlam / (1.0 + tlam**2)**0.5

        cayl = (1.0 - slam**2) * (1.0 + C6 * slam**2 + 0.03 * caya * C4 * slam)

        ems = 1.0 - 0.25 * fstrt

        BT = (0.215 * (0.37 + 0.7 * tr) * (span**2 / area) ** ems / (cayl * tca))

        return BT


    def calcW2(self):

        fcomp = self.input['WING']['COMPOSITE_FRACTION'] # forse zero??
        area = Units.m2toft2(self.input['GROSS_WEIGHT']/self.aircraft.DesignWTOoS) # ce l'abbiamo
        sflap = area * self.input['SYSTEM_EQUIPMENT']['CONTROL_SURFACE_AREA_RATIO']
        dg = Units.kgTolb(self.input['GROSS_WEIGHT']) # da passare in input dentro al loop

        W2 = self.A3 * (1.0 - 0.17*fcomp) * (sflap**self.A4) * (dg**self.A5)

        return W2

    def calcW3(self):

        fcomp = self.input['WING']['COMPOSITE_FRACTION'] # forse zero??
        sw = Units.m2toft2(self.input['GROSS_WEIGHT']/self.aircraft.DesignWTOoS) # ce l'abbiamo
        

        W3 = self.A6 * (1.0 - 0.3*fcomp) * (sw**self.A7)

        return W3


    def calcW1(self):

        num_wing_eng = self.input['ENGINE']['N_ENGINES'] # ce l'abbiamo
            
        span = self.input['WING']['SPAN'] # ce l'abbiamo
        faert = self.input['WING']['AEROELASTIC_TAILORING_FACTOR'] # chi sei?
        sweep = self.input['WING']['SWEEP'] # ce l'abbiamo
        ulf = self.input['WING']['ULTIMATE_LOAD_FACTOR'] # bho ????
        fcomp = self.input['WING']['COMPOSITE_FRACTION'] # forse zero??
        varswp = self.input['WING']['VAR_SWEEP_MASS_PENALTY'] # ehhhhhhh
        ptcl = self.input['WING']['LOAD_FRACTION']
        dg = Units.kgTolb(self.input['GROSS_WEIGHT']) # da passare in input dentro al loop

        cayf = 0.5 
        vfact = 1.0 + varswp * (0.96 / np.cos(np.pi / 180. * sweep) - 1.0)
        caye = 1.0 - 0.03 * num_wing_eng

        W1NIR = self.A1 * self.BendingMaterialFactor() * (1. + np.sqrt(self.A2/span)) * ulf * span * (1.0 - 0.4*fcomp) * (1.0 - 0.1*faert) * cayf * vfact * ptcl*1e-6

        W2 = self.calcW2()
        W3 = self.calcW3()

        W1 = ( (dg * caye * W1NIR + W2 + W3) / (1.0 + W1NIR) ) - W2 - W3

        return W1


    def calcW4(self):

        # W4 represents the BWB AFT_BODY MASS, here is fixed to zero.
        W4 = 0
        return W4


    def WingMass(self):

        scaler = self.input['WING']['SCALER']

        self.wingmass = (self.calcW1() + self.calcW2() + self.calcW3() + self.calcW4()) * scaler

        return None