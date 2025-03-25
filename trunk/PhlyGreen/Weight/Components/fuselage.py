

class Fuselage:

    def __init__(self, aircraft, input):
        self.aircraft = aircraft
        self.input = input

    def FuselageMass(self):

        length = self.input['FUSELAGE']['LENGTH'] 
        scaler = self.input['FUSELAGE']['SCALER']

        max_height = self.input['FUSELAGE']['MAX_HEIGHT']
        max_width = self.input['FUSELAGE']['MAX_WIDTH']
        avg_diameter = 0.5 * (max_height + max_width)

        num_fuse = self.input['FUSELAGE']['NUM_FUSELAGES']
        num_fuse_eng = self.input['FUSELAGE']['TOTAL_NUM_FUSELAGE_ENGINES']

        military_cargo = self.input['FUSELAGE']['MILITARY_CARGO_FLOOR']

        mil_factor = 1.38 if military_cargo else 1.0

        self.fuselagemass = (scaler * 1.35 * (avg_diameter * length) ** 1.28 * (1.0 + 0.05 * num_fuse_eng) * mil_factor * num_fuse )

        return None