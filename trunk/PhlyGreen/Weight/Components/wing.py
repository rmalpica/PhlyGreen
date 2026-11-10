"""FLOPS transport wing mass (Aviary ``wing_simple.py``, ``wing_common.py``), imperial units."""

import numpy as np
import PhlyGreen.Utilities.Units as Units
from .sizing_inputs import wing_area_ft2, wing_span_ft

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

        fstrt = self.input['WING']['STRUT_BRACING_FACTOR']
        span = wing_span_ft(self.aircraft, self.input)          # sqrt(AR * S) [ft]
        tr = self.input['WING']['TAPER_RATIO']
        area = wing_area_ft2(self.aircraft, self.input)         # [ft^2]
        tca = self.input['WING']['THICKNESS_TO_CHORD']
        faert = self.input['WING']['AEROELASTIC_TAILORING_FACTOR']
        ar = self.aircraft.aerodynamics.AR
        sweep = self.input['WING']['SWEEP']                     # quarter-chord [deg]

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

        fcomp = self.input['WING']['COMPOSITE_FRACTION']
        area = wing_area_ft2(self.aircraft, self.input)         # [ft^2]
        sflap = area * self.input['SYSTEM_EQUIPMENT']['CONTROL_SURFACE_AREA_RATIO']
        dg = Units.kgTolb(self.input['GROSS_WEIGHT'])            # [lb]

        W2 = self.A3 * (1.0 - 0.17*fcomp) * (sflap**self.A4) * (dg**self.A5)

        return W2

    def calcW3(self):

        fcomp = self.input['WING']['COMPOSITE_FRACTION']
        sw = wing_area_ft2(self.aircraft, self.input)           # [ft^2]

        W3 = self.A6 * (1.0 - 0.3*fcomp) * (sw**self.A7)

        return W3


    def calcW1(self):

        num_wing_eng = self.input['ENGINE']['N_WING_ENGINES']   # inertia relief of wing engines
        span = wing_span_ft(self.aircraft, self.input)          # [ft]
        faert = self.input['WING']['AEROELASTIC_TAILORING_FACTOR']
        sweep = self.input['WING']['SWEEP']
        ulf = self.input['WING']['ULTIMATE_LOAD_FACTOR']
        fcomp = self.input['WING']['COMPOSITE_FRACTION']
        varswp = self.input['WING']['VAR_SWEEP_MASS_PENALTY']
        ptcl = self.input['WING']['LOAD_FRACTION']
        dg = Units.kgTolb(self.input['GROSS_WEIGHT'])            # [lb]

        # Multiple-fuselage factor: 1.0 for one fuselage, 0.5 for more (Aviary wing_common).
        cayf = 0.5 if self.input['FUSELAGE']['NUM_FUSELAGES'] > 1 else 1.0
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
