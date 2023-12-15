class Aircraft:
    def __init__(self, powertrain, structures, aerodynamics, performance, mission, weight, constraint, welltowake):
        #subsystems
        self.powertrain = powertrain
        self.structures = structures
        self.aerodynamics = aerodynamics
        self.performance = performance
        self.mission = mission
        self.weight = weight
        self.constraint = constraint
        self.welltowake = welltowake
        #input dictionaries
        self.ConstraintsInput = None 
        self.MissionInput = None 
        self.TechnologyInput = None 
        self.MissionStages = None 
        self.DiversionStages = None 
        self.WellToTankInput = None
        #aircraft design
        self.DesignPW = None
        self.DesignWTOoS = None

    """ Properties """

    @property
    def DesignPW(self):
        if self._DesignPW == None:
            raise ValueError("Design P/W unset. Exiting")
        return self._DesignPW
      
    @DesignPW.setter
    def DesignPW(self,value):
        self._DesignPW = value

    @property
    def DesignWTOoS(self):
        if self._DesignWTOoS == None:
            raise ValueError("Design W/S unset. Exiting")
        return self._DesignWTOoS
      
    @DesignWTOoS.setter
    def DesignWTOoS(self,value):
        self._DesignWTOoS = value


    """ Methods """

    def ReadInput(self,ConstraintsInput,MissionInput,TechnologyInput,MissionStages,DiversionStages, WellToTankInput=None):
        
        self.ConstraintsInput = ConstraintsInput
        self.MissionInput = MissionInput
        self.TechnologyInput = TechnologyInput
        self.MissionStages = MissionStages
        self.DiversionStages = DiversionStages

        if WellToTankInput is not None:
            
            self.WellToTankInput = WellToTankInput
            self.welltowake.SetInput()

        # Initialize Constraint Analysis
        self.constraint.SetInput()
        
        # Initialize Mission profile and Analysis
        self.mission.InitializeProfile()
        self.mission.SetInput()
        
        # Initialize Powertrain
        self.powertrain.SetInput()
        
        # Initialize Weight Estimator
        self.weight.SetInput()

    def DesignAircraft(self,ConstraintsInput, MissionInput, TechnologyInput, MissionStages, DiversionStages, **kwargs):
        WellToTankInput = kwargs.get('WellToTankInput', None)
        PrintOutput = kwargs.get('PrintOutput', False)
        # print("Initializing aircraft...")
        self.ReadInput(ConstraintsInput, MissionInput, TechnologyInput, MissionStages, DiversionStages, WellToTankInput)

        # print("Finding Design Point...")
        self.constraint.FindDesignPoint()
        
        if PrintOutput:
            print('----------------------------------------')
            print('Design W/S: ',self.DesignWTOoS)
            print('Design P/W: ',self.DesignPW)
            print('----------------------------------------')

        # print("Evaluating Weights...")
        self.weight.WeightEstimation()
        self.WingSurface = self.weight.WTO / self.DesignWTOoS * 9.81
        
        if (self.Configuration == 'Hybrid' and WellToTankInput is not None):
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
            else:
                print('Takeoff Weight: ', self.weight.WTO)
                print('Wing Surface: ', self.WingSurface, ' m^2')

        
