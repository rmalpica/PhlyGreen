class Aircraft:
    """ The Aircraft class. 

    This code is designed using the "mediator class" paradigm (a sort of hub and spoke). There is
    one central class (Aircraft) which takes subsystems modules as inputs, and each of the modules takes the mediator
    as their input as well. This way, any necessary module data or methods may be accessed by other modules by going through Aircraft.

    """

    def __init__(self, powertrain, structures, aerodynamics, performance, mission, weight, constraint, welltowake, battery, climateimpact):
        """Initialize a Aircraft instance.

        Args:
            powertrain: An instance of the powertrain class.
            structures: An instance of the structures class.
            aerodynamics: An instance of the aerodynamics class.
            performance: An instance of the performance class.
            mission: An instance of the mission class.
            weight: An instance of the weight class.
            constraint: An instance of the constraint class.
            welltowake: An instance of the welltowake class.
            battery: An instance of the battery class.
            climateimpact: An instance of the climateimpact class.

        Attributes:
            AerodynamicsInput (dictionary): contains aerodynamics input keys and values
            ConstraintsInput (dictionary): contains constraint analysis input keys and values
            MissionInput (dictionary): contains mission analysis input keys and values
            EnergyInput (dictionary): contains powertrain input keys and values
            CellInput (dictionary): contains battery cell input keys and values
            MissionStages (dictionary): contains mission profile input keys and values
            DiversionStages (dictionary): contains diversion mission profile input keys and values
            LoiterStages (dictionary): contains loiter mission profile input keys and values
            WellToTankInput (dictionary): contains well-to-wake input keys and values
            FLOPSInput (dictionary): contains FLOPS input keys and values
            PropellerInput (dictionary): contains propeller input keys and values
            Configuration (string): 'Traditional' or 'Hybrid'. Defines powertrain efficiency chain in powertrain.DefinePowertrainSystem and affects mission integration in mission.EvaluateMission.  
            HybridType (string): 'Parallel' or 'Serial'. Specifies powertrain efficiency chain in powertrain.DefinePowertrainSystem 
            AircraftType (string): 'ATR' or 'DO228'. Defines Class I structural model in structures.StructuralWeight
            WingSurface (float): aircraft wing surface [m^2] 
            DesignPW (float): aircraft design power-to-weight ratio [W/kg] 
            DesignWTOoS (float): aircraft design wing loading  
            
        """
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
        self.climateimpact = climateimpact
        #input dictionaries
        self.AerodynamicsInput = None 
        self.ConstraintsInput = None 
        self.MissionInput = None 
        self.EnergyInput = None 
        self.CellInput = None
        self.MissionStages = None 
        self.DiversionStages = None 
        self.LoiterStages = None
        self.WellToTankInput = None
        self.FLOPSInput = None
        self.PropellerInput = None
        #aircraft configuration
        self.Configuration = None
        self.HybridType = None
        self.AircraftType = None
        #aircraft design
        self.WingSurface = None
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

    def ReadInput(self,AerodynamicsInput,ConstraintsInput,MissionInput,EnergyInput,MissionStages,DiversionStages, LoiterStages=None, WellToTankInput=None, CellInput=None, ClimateImpactInput=None, PropellerInput=None):
        """Imports input dictionaries and assigns them to Aircraft class attributes. Then it also passes them over to the subsystems classes.

        Args:
            AerodynamicsInput (dictionary)
            ConstraintsInput (dictionary)
            MissionInput (dictionary)
            EnergyInput (dictionary)
            MissionStages (dictionary)
            DiversionStages (dictionary)
            LoiterStages (dictionary, optional) 
            WellToTankInput (dictionary, optional) 
            CellInput (dictionary, optional)
            ClimateImpactInput (dictionary, optional)
            PropellerInput (dictionary, optional)        
        """
        
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
        
        if PropellerInput is not None:
            self.PropellerInput = PropellerInput
            
        # Initialize Powertrain
        self.powertrain.SetInput()
        
        # Initialize Weight Estimator
        self.weight.SetInput()

        if CellInput is not None:
            
            self.CellInput = CellInput
            self.battery.SetInput()
        
        if ClimateImpactInput is not None:
            self.ClimateImpactInput = ClimateImpactInput
            self.climateimpact.SetInput()


    def DesignAircraft(self, AerodynamicsInput, ConstraintsInput, MissionInput, EnergyInput, MissionStages, DiversionStages, **kwargs):
        """Executes the ReadInput function, then finds desing point in the constraint diagram, then runs the mission analysis (WeightEstimation function) to design the aircraft.
           If PrintOutput is True, it returns a full summary of the design results.
        Args:
            AerodynamicsInput (dictionary)
            ConstraintsInput (dictionary)
            MissionInput (dictionary)
            EnergyInput (dictionary)
            MissionStages (dictionary)
            DiversionStages (dictionary)
            LoiterStages (dictionary, optional) 
            WellToTankInput (dictionary, optional) 
            CellInput (dictionary, optional)
            ClimateImpactInput (dictionary, optional)
            PropellerInput (dictionary, optional)  
            PrintOutput (bool, default is False)     
        """

        WellToTankInput = kwargs.get('WellToTankInput', None)
        LoiterStages = kwargs.get('LoiterStages', None)
        CellInput = kwargs.get('CellInput', None)
        ClimateImpactInput = kwargs.get('ClimateImpactInput', None)
        PropellerInput = kwargs.get('PropellerInput', None)
        PrintOutput = kwargs.get('PrintOutput', False)

        if PrintOutput: print("Reading input data...")
        self.ReadInput(AerodynamicsInput,ConstraintsInput, MissionInput, EnergyInput, MissionStages, DiversionStages,LoiterStages, WellToTankInput,CellInput,ClimateImpactInput,PropellerInput)

        if PrintOutput: print("Finding Design Point...")
        self.constraint.FindDesignPoint()
        
        if PrintOutput:
            print('----------------------------------------------')
            print(f'Design wing loading W/S: {self.DesignWTOoS:.1f} [N/m^2]')
            print(f'Design power-to-mass ratio P/W: {self.DesignPW:.2f} [W/kg]')
            print('----------------------------------------------')

        if PrintOutput: print("Evaluating Weights...")
        self.weight.WeightEstimation()
        self.WingSurface = self.weight.WTO / self.DesignWTOoS * 9.81
        
        if (self.Configuration == 'Hybrid' and WellToTankInput is not None):
            self.welltowake.EvaluateSource()
        
        if PrintOutput: self.Print_Aircraft_Design_Summary()
        

    def Print_Aircraft_Design_Summary(self):
        print(f'Fuel mass (trip + altn + loiter): {self.weight.Wf:.1f} [Kg]')
        print(f'Block Fuel mass:                  {self.weight.Wf + self.weight.final_reserve:.1f} [Kg]')
        if self.Configuration == 'Hybrid':
            print(f'Battery mass:                     {self.weight.WBat:.1f} [Kg]')
            print(f'Structure:                        {self.weight.WStructure:.1f} [Kg]')
            print(f'Powertrain mass:                  {self.weight.WPT:.1f} [Kg]')
            print(f'Empty Weight:                     {self.weight.WPT + self.weight.WStructure + self.weight.WCrew + self.weight.WBat:.1f} [Kg]')
            print(f'Zero Fuel Weight:                 {self.weight.WPT + self.weight.WStructure + self.weight.WCrew + self.weight.WBat + self.weight.WPayload:.1f} [Kg]')
        else:
            print(f'Structure:                        {self.weight.WStructure:.1f} [Kg]')
            print(f'Powertrain mass:                  {self.weight.WPT:.1f} [Kg]')
            print(f'Empty Weight:                     {self.weight.WPT + self.weight.WStructure + self.weight.WCrew:.1f} [Kg]')
            print(f'Zero Fuel Weight:                 {self.weight.WPT + self.weight.WStructure + self.weight.WCrew + self.weight.WPayload:.1f} [Kg]')

        print('----------------------------------------')
        print(f'Takeoff Weight:                   {self.weight.WTO:.1f} [Kg]')
        print(' ')
        if self.WellToTankInput is not None:
            print(f'Source Energy:                    {self.welltowake.SourceEnergy/1.e6:.1f} [MJ]')
            print(f'Psi:                              {self.welltowake.Psi:.4f} [-]')
        print(' ')
        print(f'Wing Surface:                     {self.WingSurface:.1f} [m^2]')
        print(' ')
        print(f'TakeOff engine shaft peak power:  {self.mission.TO_PP/1000.:.1f} [KW]')
        print(f'CLB/CRZ engine shaft peak power:  {self.mission.Max_PEng/1000.:.1f} [KW] @ {self.mission.Max_PEng_alt:.1f} [m]' )
        print(' ')
        
        print(f'Sizing phase for thermal powertrain: ', 'Climb/Cruise peak power (adjusted with altitude power lapse)' if self.mission.Max_PEng > self.mission.TO_PP else 'Takeoff peak power'  )
        print(f'Thermal powertrain rating shaft power SLS rating: {self.powertrain.engineRating/1000.:.1f} [kW]')
        print(' ')

        if self.Configuration == 'Hybrid':
            print('-------------Battery Specs-------------')
            if self.battery.BatteryClass == 'II':
                print(f'Battery Pack Energy:               {self.battery.pack_energy/1000:.1f} [kWh]')
                print(f'Battery Pack Max Power:            {self.battery.pack_power_max/1000:.1f} [kW]')
                print(f'Battery Pack Specific Energy:      {(self.battery.pack_energy)/self.weight.WBat:.1f} [Wh/kg]')
                print(f'Battery Pack Specific Power:       {(self.battery.pack_power_max/1000)/self.weight.WBat:.1f} [kW/kg]')
                print(f'Battery Configuration:             S-{self.battery.S_number:.0f} P-{self.battery.P_number:.0f}' )
            elif self.battery.BatteryClass == 'I':
                print(f'TakeOff battery peak power:       {self.mission.TO_PBat/1000.:.1f} [KW]')
                print(f'Climb/cruise battery peak power:  {self.mission.Max_PBat/1000.:.1f} [KW]')
                print(f'Energy capacity:                  {self.weight.TotalEnergies[1]*1e-6/(1-self.battery.SOC_min):.1f} [MJ]')
                print(f'Sizing requirement for battery:  ', 'Energy' if self.weight.WBatidx == 0 else 'Power')




        
