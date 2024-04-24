class Aircraft:
    def __init__(self, powertrain, structures, aerodynamics, performance, mission, weight, constraint, welltowake, battery):
        #subsystems
        self.powertrain = powertrain
        self.structures = structures
        self.aerodynamics = aerodynamics
        self.performance = performance
        self.mission = mission
        self.weight = weight
        self.constraint = constraint
        self.welltowake = welltowake
        self.battery = battery
        #input dictionaries
        self.AerodynamicsInput = None 
        self.ConstraintsInput = None 
        self.MissionInput = None 
        self.EnergyInput = None 
        self.CellModel = None
        self.MissionStages = None 
        self.DiversionStages = None 
        self.LoiterStages = None
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

    def ReadInput(self,AerodynamicsInput,ConstraintsInput,MissionInput,EnergyInput,MissionStages,DiversionStages, LoiterStages=None, WellToTankInput=None):
        
        self.AerodynamicsInput = AerodynamicsInput
        self.ConstraintsInput = ConstraintsInput
        self.MissionInput = MissionInput
        self.EnergyInput = EnergyInput
        self.MissionStages = MissionStages
        self.DiversionStages = DiversionStages
        
        if LoiterStages is not None:
            self.LoiterStages = LoiterStages

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
        LoiterStages = kwargs.get('LoiterStages', None)
        PrintOutput = kwargs.get('PrintOutput', False)
        # print("Initializing aircraft...")
        self.ReadInput(AerodynamicsInput,ConstraintsInput, MissionInput, EnergyInput, MissionStages, DiversionStages,LoiterStages, WellToTankInput)

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
            print('Fuel mass (trip + altn) [Kg]: ', self.weight.Wf)
            print('Block Fuel mass [Kg]:         ', self.weight.Wf + self.weight.final_reserve)
            if (self.Configuration == 'Hybrid'):
                print('Battery mass [Kg]:            ', self.weight.WBat)
            print('Structure [Kg]:               ', self.weight.WStructure)
            print('Powertrain mass [Kg]:         ',self.weight.WPT)
            print('Empty Weight [Kg]:            ', self.weight.WPT + self.weight.WStructure + self.weight.WCrew + self.weight.WBat)
            print('Zero Fuel Weight [Kg]:        ', self.weight.WPT + self.weight.WStructure + self.weight.WCrew + self.weight.WBat + self.weight.WPayload)
            print('----------------------------------------')
            print('Takeoff Weight: ', self.weight.WTO)
            if self.WellToTankInput is not None:
                print('Source Energy: ', self.welltowake.SourceEnergy/1.e6,' MJ')
                print('Psi: ', self.welltowake.Psi)
            print('Wing Surface: ', self.WingSurface, ' m^2')
            print('TakeOff engine shaft peak power [kW]:      ', self.mission.TO_PP/1000.)
            print('Climb/cruise engine shaft peak power [kW]: ', self.mission.Max_PEng/1000.)
            if (self.Configuration == 'Hybrid'):
                print('TakeOff battery peak power [kW]:           ', self.mission.TO_PBat/1000.)
                print('Climb/cruise battery peak power [kW]:      ', self.mission.Max_PBat/1000.)
                print('Sizing phase for battery: ', 'Cruise energy' if self.weight.WBatidx == 0 else 'Cruise peak power' if self.weight.WBatidx == 1 else 'Takeoff peak power'  )
                print('Sizing phase for electric powertrain ', 'Climb/Cruise peak power' if self.mission.Max_PBat > self.mission.TO_PBat else 'Takeoff peak power'  )
            print('Sizing phase for thermal powertrain ', 'Climb/Cruise peak power' if self.mission.Max_PEng > self.mission.TO_PP else 'Takeoff peak power'  )


        
