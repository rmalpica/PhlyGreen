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
        self.AerodynamicsInput = None 
        self.ConstraintsInput = None 
        self.MissionInput = None 
        self.EnergyInput = None 
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

    def ReadInput(self,AerodynamicsInput,ConstraintsInput,MissionInput,EnergyInput,MissionStages,DiversionStages, WellToTankInput=None):
        
        self.AerodynamicsInput = AerodynamicsInput
        self.ConstraintsInput = ConstraintsInput
        self.MissionInput = MissionInput
        self.EnergyInput = EnergyInput
        self.MissionStages = MissionStages
        self.DiversionStages = DiversionStages

        if WellToTankInput is not None:
            
            self.WellToTankInput = WellToTankInput
            self.welltowake.SetInput()

        # Initialize Aerodynamics subsystem
        self.aerodynamics.SetInput()

        # Initialize Constraint Analysis
        self.constraint.SetInput()
        
        # Initialize Mission profile and Analysis
        self.mission.InitializeProfile()
        self.mission.SetInput()
        
        # Initialize Powertrain
        self.powertrain.SetInput()
        
        # Initialize Weight Estimator
        self.weight.SetInput()

    def DesignAircraft(self,AerodynamicsInput,ConstraintsInput, MissionInput, EnergyInput, MissionStages, DiversionStages, **kwargs):
        WellToTankInput = kwargs.get('WellToTankInput', None)
        PrintOutput = kwargs.get('PrintOutput', False)
        # print("Initializing aircraft...")
        self.ReadInput(AerodynamicsInput,ConstraintsInput, MissionInput, EnergyInput, MissionStages, DiversionStages, WellToTankInput)

        if PrintOutput: print("Finding Design Point...")
        self.constraint.FindDesignPoint()
        
        if PrintOutput:
            print('----------------------------------------')
            print('Design W/S: ',self.DesignWTOoS)
            print('Design P/W: ',self.DesignPW)
            print('----------------------------------------')

        if PrintOutput: print("Evaluating Weights...")
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
                if WellToTankInput is not None:
                    print('Source Energy: ', self.welltowake.SourceEnergy/1.e6,' MJ')
                    print('Psi: ', self.welltowake.Psi)
                print('Wing Surface: ', self.WingSurface, ' m^2')
                print('Sizing phase for battery: ', 'Cruise energy' if self.weight.WBatidx == 0 else 'Cruise peak power' if self.weight.WBatidx == 1 else 'Takeoff peak power'  )
                print('Sizing phase for thermal powertrain ', 'Cruise peak power' if self.mission.Max_PFoW > self.mission.TO_PFoW else 'Takeoff peak power'  )
                print('Sizing phase for electric powertrain ', 'Cruise peak power' if self.mission.Max_PBatoW > self.mission.TO_PBatoW else 'Takeoff peak power'  )
            else:
                print('Takeoff Weight: ', self.weight.WTO)
                print('Wing Surface: ', self.WingSurface, ' m^2')

        
