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

    def DesignAircraft(self,ConstraintsInput, MissionInput, TechnologyInput, MissionStages, DiversionStages):
        print("Initializing aircraft...")
        self.ReadInput(ConstraintsInput, MissionInput, TechnologyInput, MissionStages, DiversionStages)

        print("Finding Design Point...")
        self.constraint.FindDesignPoint()
        print('----------------------------------------')
        print('Design W/S: ',self.constraint.DesignWTOoS)
        print('Design P/W: ',self.constraint.DesignPW)
        print('----------------------------------------')

        print("Evaluating Weights...")
        self.weight.WeightEstimation()
        print('----------------------------------------')
        print('Powertrain mass: ',self.weight.WPT)
        print('Fuel mass: ', self.weight.Wf)
        if (self.Configuration == 'Hybrid'):
            print('Battery mass: ',self.weight.WBat)
        print('Structure: ', self.weight.WStructure)
        print('Empty Weight: ', self.weight.WPT + self.weight.WStructure + self.weight.WCrew)
        print('----------------------------------------')
        print('Takeoff Weight: ', self.weight.WTO[-1])
        print('Wing Surface: ', self.weight.WTO[-1] / self.constraint.DesignWTOoS * 9.81, ' m^2')
