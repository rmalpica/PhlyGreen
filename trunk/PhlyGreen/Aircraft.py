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
        
        # Contraint analysis inputs
        self.ConstraintsBeta = ConstraintsInput['beta']
        self.ConstraintsAltitude = ConstraintsInput['altitude']
        self.ConstraintsSpeed = ConstraintsInput['speed']
        self.ConstraintsSpeedtype = ConstraintsInput['speedtype']
        self.ConstraintsN = ConstraintsInput['load factor']
        self.DISA = ConstraintsInput['DISA']
        self.kTO = ConstraintsInput['kTO']
        self.sTO = ConstraintsInput['sTO']
        self.CB = ConstraintsInput['Climb Gradient']
        self.ht = ConstraintsInput['ht']
        self.M1 = ConstraintsInput['M1']
        self.M2 = ConstraintsInput['M2']
        self.DTAcceleration = ConstraintsInput['DTAcceleration']


        # Mission analysis inputs
        self.MissionRange = MissionInput['Range Mission']
        self.DiversionRange = MissionInput['Range Diversion']
        self.beta0 = MissionInput['Beta start']
        self.WPayload = MissionInput['Payload Weight']
        self.WCrew = MissionInput['Crew Weight']

        
        # Technology parameters
        self.ef = TechnologyInput['Ef']
        self.EtaGT = TechnologyInput['Eta Gas Turbine']
        self.EtaGB = TechnologyInput['Eta Gearbox']
        self.EtaPP = TechnologyInput['Eta Propulsive']
        self.SPowerPT = TechnologyInput['Specific Power Powertrain']
        self.PtWPT = TechnologyInput['PowertoWeight Powertrain']
        
        self.MissionStages = MissionStages
        self.DiversionStages = DiversionStages
        return None




    def design_aircraft(self):
        print("Initializing aircraft...")
        self.powertrain.set()
        self.structure.set()
        self.aerodynamics.set()
        self.performance.set()
        self.mission.set()

