class Aircraft:
    def __init__(self, powertrain, structures, aerodynamics, performance, mission, weight, constraint):
        self.powertrain = powertrain
        self.structures = structures
        self.aerodynamics = aerodynamics
        self.performance = performance
        self.mission = mission
        self.weight = weight
        self.constraint = constraint


    def ReadInput(self,ConstraintsInput,MissionInput,TechnologyInput,MissionStages,DiversionStages):
        
        self.ConstraintsInput = ConstraintsInput
        self.MissionInput = MissionInput
        self.TechnologyInput = TechnologyInput
        self.MissionStages = MissionStages
        self.DiversionStages = DiversionStages


        # Initialize Constraint Analysis
        self.constraint.ReadInput()
        
        # Initialize Mission profile and Analysis
        self.mission.InitializeProfile()
        self.mission.ReadInput()
        
        # Initialize Powertrain
        self.powertrain.ReadInput()
        
        # Initialize Weight Estimator
        self.weight.ReadInput()

    def design_aircraft(self):
        print("Initializing aircraft...")
        self.powertrain.set()
        self.structure.set()
        self.aerodynamics.set()
        self.performance.set()
        self.mission.set()

