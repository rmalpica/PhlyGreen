from .Components import Wing
from .Components import Fuselage
from .Components import Tail
from .Components import LandingGear
from .Components import SystemEquipment
from .Components import Nacelle
from .Components import Paint
from .Components import Propeller

class FLOPS_model:

    def __init__(self, aircraft):
        self.aircraft = aircraft

    def SetInput(self):

        self.InputData = self.aircraft.FLOPSInput
        self.Wing = Wing(self.aircraft, self.InputData)
        self.Fuselage = Fuselage(self.aircraft, self.InputData)
        self.Tail = Tail(self.aircraft, self.InputData)
        self.LandingGear = LandingGear(self.aircraft, self.InputData)
        self.SystemEquipment = SystemEquipment(self.aircraft, self.InputData)
        self.Nacelle = Nacelle(self.aircraft, self.InputData)
        self.Paint = Paint(self.aircraft, self.InputData)
        self.Propeller = Propeller(self.aircraft, self.InputData)

        return None
    

    def CalculateComponentMasses(self):

        self.Wing.WingMass()
        self.Fuselage.FuselageMass()
        self.Tail.HorizontalTailMass()
        self.Tail.VerticalTailMass()
        self.LandingGear.LandingGearMass()
        self.SystemEquipment.SystemEquipmentMass()
        self.Nacelle.NacelleMass()
        self.Paint.PaintMass()
        self.Propeller.PropellerMass()

        return None