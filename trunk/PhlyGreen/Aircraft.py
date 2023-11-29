class Aircraft:
    def __init__(self, powertrain, structures, aerodynamics, performance, mission, weight, constraint, welltowake):
        self.powertrain = powertrain
        self.structures = structures
        self.aerodynamics = aerodynamics
        self.performance = performance
        self.mission = mission
        self.weight = weight
        self.constraint = constraint
        self.welltowake = welltowake


    def ReadInput(self,ConstraintsInput,MissionInput,TechnologyInput,MissionStages,DiversionStages, WellToTankInput=None):
        
        self.ConstraintsInput = ConstraintsInput
        self.MissionInput = MissionInput
        self.TechnologyInput = TechnologyInput
        self.MissionStages = MissionStages
        self.DiversionStages = DiversionStages

        if WellToTankInput is not None:
            
            self.WellToTankInput = WellToTankInput
            self.welltowake.ReadInput()

        # Initialize Constraint Analysis
        self.constraint.ReadInput()
        
        # Initialize Mission profile and Analysis
        self.mission.InitializeProfile()
        self.mission.ReadInput()
        
        # Initialize Powertrain
        self.powertrain.ReadInput()
        
        # Initialize Weight Estimator
        self.weight.ReadInput()

    def DesignAircraft(self,ConstraintsInput, MissionInput, TechnologyInput, MissionStages, DiversionStages, WellToTankInput=None, PrintOutput = False):
        # print("Initializing aircraft...")
        self.ReadInput(ConstraintsInput, MissionInput, TechnologyInput, MissionStages, DiversionStages, WellToTankInput)

        # print("Finding Design Point...")
        self.constraint.FindDesignPoint()
        
        if PrintOutput:
            print('----------------------------------------')
            print('Design W/S: ',self.constraint.DesignWTOoS)
            print('Design P/W: ',self.constraint.DesignPW)
            print('----------------------------------------')

        # print("Evaluating Weights...")
        self.weight.WeightEstimation()
        self.WingSurface = self.weight.WTO / self.constraint.DesignWTOoS * 9.81
        
        if (self.Configuration == 'Hybrid'):
            self.welltowake.EvaluateSource()
        
        if PrintOutput:
            print('----------------------------------------')
            print('Powertrain mass: ',self.weight.WPT)
            print('Fuel mass: ', self.weight.Wf)
            if (self.Configuration == 'Hybrid'):
                print('Battery mass: ',self.weight.WBat)
                print('Structure: ', self.weight.WStructure)
                print('Empty Weight: ', self.weight.WPT + self.weight.WStructure + self.weight.WCrew)
                print('----------------------------------------')
                print('Takeoff Weight: ', self.weight.WTO)
                print('Source Energy: ', self.welltowake.SourceEnergy/1.e6,' MJ')
                print('Psi: ', self.welltowake.Psi)
                print('Wing Surface: ', self.WingSurface, ' m^2')
        
        
