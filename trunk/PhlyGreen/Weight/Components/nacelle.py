
class Nacelle:

    def __init__(self, aircraft, input):
        self.aircraft = aircraft
        self.input = input  

    def NacelleMass(self):

        num_eng = self.input['ENGINE']['N_ENGINES']
        avg_diam = self.input['NACELLE']['AVG_DIAM']
        avg_length = self.input['NACELLE']['AVG_LENGTH']
        thrust = self.input['ENGINE']['MAX_SLS_THRUST']
        scaler = self.input['NACELLE']['SCALER']

        count_factor = 1.0 # TO DO.... DISTRIBUTED PROPULSION

        self.nacellemass = 0.25 * count_factor * \
                avg_diam * avg_length * thrust**0.36 * scaler 

        return None