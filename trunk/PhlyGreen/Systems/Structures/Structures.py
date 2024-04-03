class Structures:
    def __init__(self, aircraft):
        self.aircraft = aircraft


    def StructuralWeight(self,WTO):
        
        if self.aircraft.AircraftType == 'ATR':

            return (WTO**(-0.06) * WTO)
        
        if self.aircraft.AircraftType == 'DO228':

            return WTO*0.545
    
