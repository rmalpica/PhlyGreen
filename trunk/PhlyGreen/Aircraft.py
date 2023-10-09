class Aircraft:
    def __init__(self, powertrain, structures, aerodynamics, performance, mission):
        self.powertrain = powertrain
        self.structures = structures
        self.aerodynamics = aerodynamics
        self.performance = performance
        self.mission = mission

    def design_aircraft(self):
        print("Initializing aircraft...")
        self.powertrain.set()
        self.structure.set()
        self.aerodynamics.set()
        self.performance.set()
        self.mission.set()

