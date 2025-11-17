import numpy as np
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed

class Constraint:
    """
    Computes aircraft power-to-weight (P/W) constraint curves over a range of 
    wing loading values (W/S), and identifies the design operating point where 
    all constraints are simultaneously satisfied.

    This implements the classical aircraft sizing method based on constraint 
    analysis (Raymer/Mattingly method), where each flight requirement 
    produces a curve:

        Required (P/W) = f(W/S)

    Constraints typically include:
      • Cruise       (level flight)
      • Take-off
      • AEO Climb    (all-engines-operating climb)
      • OEI Climb    (one-engine-inoperative climb)
      • Turn         (constant-load-factor)
      • Ceiling      (service ceiling rate of climb)
      • Acceleration (Mach acceleration requirement)
      • Landing      (defines max W/S allowed)

    The design point is the minimum P/W that satisfies *all* constraints, 
    computed as the envelope of the constraint curves.
    Note that, in hybrid designs, this is not necessarily the optimal solution.
    """
    def __init__(self, aircraft):
        self.aircraft = aircraft
        self.WTOoS = np.linspace(1, 7000, num=1000) # Range of wing loading W/S to evaluate [N/m^2]


    def SetInput(self):
        """
        Load all constraint definitions from the aircraft input dictionary.

        These constraints are user-defined and come from the conceptual 
        design requirements, e.g.:

            - Cruise Mach, altitude, beta (mass fraction)
            - Takeoff field length, kTO factor
            - Climb gradients
            - Turn load factor
            - Service ceiling
            - Acceleration requirement (dM/dt or ΔM/Δt)

        Notes
        -----
        DISA is the off-standard temperature (ISA deviation).
        """
        
        # self.ConstraintsBeta = self.aircraft.ConstraintsInput['beta']
        # self.ConstraintsAltitude = self.aircraft.ConstraintsInput['altitude']
        # self.ConstraintsSpeed = self.aircraft.ConstraintsInput['speed']
        # self.ConstraintsSpeedtype = self.aircraft.ConstraintsInput['speedtype']
        # self.ConstraintsN = self.aircraft.ConstraintsInput['load factor']
        # self.kTO = self.aircraft.ConstraintsInput['kTO']
        # self.sTO = self.aircraft.ConstraintsInput['sTO']
        # self.CB = self.aircraft.ConstraintsInput['OEI Climb Gradient']
        # self.ROC = self.aircraft.ConstraintsInput['Rate of Climb']
        # self.ht = self.aircraft.ConstraintsInput['ht']
        # self.M1 = self.aircraft.ConstraintsInput['M1']
        # self.M2 = self.aircraft.ConstraintsInput['M2']
        # self.DTAcceleration = self.aircraft.ConstraintsInput['DTAcceleration']
        # self.Mavg = (self.M1 + self.M2)/2
        
        self.DISA = self.aircraft.ConstraintsInput['DISA']
        # self.PsAcceleration = Speed.Mach2TAS(self.Mavg, self.ConstraintsAltitude[5],self.DISA) * (Speed.Mach2TAS(self.M2, self.ConstraintsAltitude[5],self.DISA) - Speed.Mach2TAS(self.M1, self.ConstraintsAltitude[5],self.DISA))/(self.DTAcceleration * 9.81) 

        self.CruiseConstraints = self.aircraft.ConstraintsInput['Cruise']
        self.AEOClimbConstraints = self.aircraft.ConstraintsInput['AEO Climb']
        self.AccelerationConstraints = self.aircraft.ConstraintsInput['Acceleration']
        self.TakeOffConstraints = self.aircraft.ConstraintsInput['Take Off'] 
        self.LandingConstraints = self.aircraft.ConstraintsInput['Landing']
        self.OEIClimbConstraints = self.aircraft.ConstraintsInput['OEI Climb']
        self.TurnConstraints = self.aircraft.ConstraintsInput['Turn']
        self.CeilingConstraints = self.aircraft.ConstraintsInput['Ceiling'] 


    def EvaluateConstraints(self, WTOoS, DISA):
        """
        Computes the required power-to-weight ratio (P/W) for each constraint 
        across the full W/S range.

        Parameters
        ----------
        WTOoS : ndarray
            Wing loading values over which constraints are evaluated.
        DISA : float
            ISA temperature deviation used in performance calculations.

        Produces
        --------
        Attributes filled:
            self.PWCruise
            self.PWTakeOff
            self.PWAEOClimb
            self.PWOEIClimb
            self.PWAcceleration
            self.PWTurn
            self.PWCeiling
            self.PWLanding
            self.WTOoSLanding

        Note:
            Presently, only one constraint curve can be built per flight phase.
        """

        # =============================================================
        # 1. CRUISE CONSTRAINT (level flight)
        # =============================================================
        if len(self.CruiseConstraints) > 0:
            self.PWCruise = (
                1.0/self.aircraft.powertrain.PowerLapse(
                    self.CruiseConstraints['Altitude'],DISA)
                ) * self.aircraft.performance.PoWTO(
                    self.WTOoS, 
                    self.CruiseConstraints['Beta'], 
                    0, 
                    1., 
                    self.CruiseConstraints['Altitude'],
                    DISA, 
                    self.CruiseConstraints['Speed'], 
                    self.CruiseConstraints['Speed Type']
                    )
        else:
            self.PWCruise = np.zeros(len(self.WTOoS))

        # =============================================================
        # 2. TAKE-OFF CONSTRAINT
        # =============================================================
        if len(self.TakeOffConstraints) > 0:
            # self.PWTakeOff = self.aircraft.performance.TakeOff_Finger(WTOoS,self.TakeOffConstraints['Beta'], self.TakeOffConstraints['Altitude'], self.TakeOffConstraints['kTO'], self.TakeOffConstraints['sTO'], DISA, self.TakeOffConstraints['Speed'], self.TakeOffConstraints['Speed Type'])
            self.PWTakeOff = self.aircraft.performance.TakeOff(
                WTOoS,
                self.TakeOffConstraints['Beta'], 
                self.TakeOffConstraints['Altitude'], 
                self.TakeOffConstraints['kTO'], 
                self.TakeOffConstraints['sTO'], 
                DISA, 
                self.TakeOffConstraints['Speed'], 
                self.TakeOffConstraints['Speed Type']
                )
        else:
            self.PWTakeOff = np.zeros(len(self.WTOoS)) 

        # =============================================================
        # 3. AEO (ALL ENGINES OPERATING) CLIMB
        # =============================================================
        if len(self.AEOClimbConstraints) > 0:
            # self.PWAEOClimb = (1.0/self.aircraft.powertrain.PowerLapse(self.AEOClimbConstraints['Altitude'],DISA)) * self.aircraft.performance.ClimbFinger(self.WTOoS, self.AEOClimbConstraints['Beta'], self.AEOClimbConstraints['ROC'], 1., self.AEOClimbConstraints['Altitude'], DISA, self.AEOClimbConstraints['Speed'], self.AEOClimbConstraints['Speed Type'])
            self.PWAEOClimb = (1.0/self.aircraft.powertrain.PowerLapse(
                self.AEOClimbConstraints['Altitude'],
                DISA)
                               ) * self.aircraft.performance.PoWTO(
                                   self.WTOoS, 
                                   self.AEOClimbConstraints['Beta'], 
                                   self.AEOClimbConstraints['ROC'], 
                                   1., 
                                   self.AEOClimbConstraints['Altitude'], 
                                   DISA, 
                                   self.AEOClimbConstraints['Speed'], 
                                   self.AEOClimbConstraints['Speed Type']
                                   )
        else:
            self.PWClimb = np.zeros(len(self.WTOoS))
        
        # =============================================================
        # 4. ONE-ENGINE-INOPERATIVE (OEI) CLIMB
        # =============================================================
        if len(self.OEIClimbConstraints) > 0:
            # self.PWOEIClimb = (1.0/self.aircraft.powertrain.PowerLapse(self.OEIClimbConstraints['Altitude'],DISA)) * self.aircraft.performance.OEIClimbFinger(self.WTOoS, self.OEIClimbConstraints['Beta'], self.OEIClimbConstraints['Speed'] * self.OEIClimbConstraints['Climb Gradient'], 1., self.OEIClimbConstraints['Altitude'], DISA, self.OEIClimbConstraints['Speed'], self.OEIClimbConstraints['Speed Type'])
            self.PWOEIClimb = (1.0/self.aircraft.powertrain.PowerLapse(
                self.OEIClimbConstraints['Altitude'],
                DISA)
                ) * self.aircraft.performance.OEIClimb(
                    self.WTOoS, 
                    self.OEIClimbConstraints['Beta'], 
                    self.OEIClimbConstraints['Speed'] * self.OEIClimbConstraints['Climb Gradient'],
                    1., 
                    self.OEIClimbConstraints['Altitude'], 
                    DISA, 
                    self.OEIClimbConstraints['Speed'], 
                    self.OEIClimbConstraints['Speed Type']
                    )
        else:
            self.PWOEIClimb = np.zeros(len(self.WTOoS)) 
        
        # =============================================================
        # 5. ACCELERATION CONSTRAINT (ΔM over Δt)
        # =============================================================
        if len(self.AccelerationConstraints) > 0:
            Mavg = (self.AccelerationConstraints['Mach 1'] + self.AccelerationConstraints['Mach 2'])/2.0
            PsAcceleration = Speed.Mach2TAS(Mavg, self.AccelerationConstraints['Altitude'],self.DISA) * (Speed.Mach2TAS(self.AccelerationConstraints['Mach 2'], self.AccelerationConstraints['Altitude'],self.DISA) - Speed.Mach2TAS(self.AccelerationConstraints['Mach 1'], self.AccelerationConstraints['Altitude'],self.DISA))/(self.AccelerationConstraints['DT'] * 9.81)  

            self.PWAcceleration = (1.0/self.aircraft.powertrain.PowerLapse(
                self.AccelerationConstraints['Altitude'],
                DISA)
                ) * self.aircraft.performance.PoWTO(
                    self.WTOoS,
                    self.AccelerationConstraints['Beta'], 
                    PsAcceleration, 
                    1., 
                    self.AccelerationConstraints['Altitude'], 
                    DISA, 
                    Mavg, 
                    'Mach'
                    )
        else:
            self.PWAcceleration = np.zeros(len(self.WTOoS))

        # =============================================================
        # 6. TURN CONSTRAINT (load-factor turn)
        # =============================================================
        if len(self.TurnConstraints) > 0:
            self.PWTurn = (1.0/self.aircraft.powertrain.PowerLapse(
                self.TurnConstraints['Altitude'],
                DISA)
                ) * self.aircraft.performance.PoWTO(
                    self.WTOoS, 
                    self.TurnConstraints['Beta'], 
                    0, 
                    self.TurnConstraints['Load Factor'], 
                    self.TurnConstraints['Altitude'], 
                    DISA, 
                    self.TurnConstraints['Speed'], 
                    self.TurnConstraints['Speed Type']
                    )
        else:
            self.PWTurn = np.zeros(len(self.WTOoS))

        # =============================================================
        # 7. SERVICE CEILING CONSTRAINT
        # =============================================================
        if len(self.CeilingConstraints) > 0:
            self.PWCeiling = (1.0/self.aircraft.powertrain.PowerLapse(
                self.CeilingConstraints['Altitude'],
                DISA)
                ) * self.aircraft.performance.Ceiling(
                    WTOoS, 
                    self.CeilingConstraints['Beta'], 
                    self.CeilingConstraints['HT'], 
                    1., 
                    self.CeilingConstraints['Altitude'], 
                    DISA, 
                    self.CeilingConstraints['Speed']
                    )
        else:
            self.PWCeiling = np.zeros(len(self.WTOoS))

        # =============================================================
        # 8. LANDING CONSTRAINT (limits W/S)
        # =============================================================
        if len(self.LandingConstraints) > 0:
            self.PWLanding, self.WTOoSLanding = self.aircraft.performance.Landing(
                WTOoS, 
                self.LandingConstraints['Altitude'], 
                self.LandingConstraints['Speed'], 
                self.LandingConstraints['Speed Type'], 
                DISA
            )
        else:
            self.PWLanding = np.linspace(0, 400, num= len(WTOoS))
            self.WTOoSLanding = np.ones(len(WTOoS))*1.e4

        # self.PWCruise = (1.0/self.aircraft.powertrain.PowerLapse(self.ConstraintsAltitude[0],DISA)) * self.aircraft.performance.PoWTO(self.WTOoS, self.ConstraintsBeta[0], 0, self.ConstraintsN[0], self.ConstraintsAltitude[0], DISA, self.ConstraintsSpeed[0], self.ConstraintsSpeedtype[0])
        # self.PWTakeOff = self.aircraft.performance.TakeOff(WTOoS,self.ConstraintsBeta[1], self.ConstraintsAltitude[1], kTO, sTO, DISA, self.ConstraintsSpeed[1], self.ConstraintsSpeedtype[1])
        # self.PWOEIClimb = self.aircraft.performance.OEIClimb(self.WTOoS,self.ConstraintsBeta[1], CB*self.ConstraintsSpeed[1], self.ConstraintsN[2], self.ConstraintsAltitude[1], DISA, self.ConstraintsSpeed[1], self.ConstraintsSpeedtype[1])
        # self.PWAEOClimb = (1.0/self.aircraft.powertrain.PowerLapse(self.ConstraintsAltitude[2],DISA)) * self.aircraft.performance.PoWTO(self.WTOoS,self.ConstraintsBeta[2], ROC, self.ConstraintsN[2], self.ConstraintsAltitude[2], DISA, self.ConstraintsSpeed[2], self.ConstraintsSpeedtype[2])
        # self.PWTurn = (1.0/self.aircraft.powertrain.PowerLapse(self.ConstraintsAltitude[3],DISA)) * self.aircraft.performance.PoWTO(self.WTOoS, self.ConstraintsBeta[3], 0, self.ConstraintsN[3], self.ConstraintsAltitude[3], DISA, self.ConstraintsSpeed[3], self.ConstraintsSpeedtype[3])
        # self.PWCeiling = (1.0/self.aircraft.powertrain.PowerLapse(self.ConstraintsAltitude[4],DISA)) * self.aircraft.performance.Ceiling(WTOoS, self.ConstraintsBeta[4], ht, self.ConstraintsN[4], self.ConstraintsAltitude[4], DISA, self.ConstraintsSpeed[4])
        # self.PWAcceleration = (1.0/self.aircraft.powertrain.PowerLapse(self.ConstraintsAltitude[5],DISA)) * self.aircraft.performance.PoWTO(self.WTOoS,self.ConstraintsBeta[5], PsAcceleration, self.ConstraintsN[5], self.ConstraintsAltitude[5], DISA, self.Mavg, self.ConstraintsSpeedtype[5])
        # self.PWLanding, self.WTOoSLanding = self.aircraft.performance.Landing(WTOoS, self.ConstraintsAltitude[6], self.ConstraintsSpeed[6], self.ConstraintsSpeedtype[6], DISA)

        return None
    
    def FindDesignPoint(self):
        """
        Computes the aircraft design point (P/W, W/S) by taking the upper 
        envelope of all constraints and selecting the minimum feasible P/W.

        Procedure
        ---------
        1. Evaluate all constraint curves.
        2. Construct a matrix of P/W curves.
        3. For each W/S, find the maximum required P/W (the envelope).
        4. The design P/W is the minimum of this envelope, and the 
           associated W/S is the design wing loading.

        Results stored in aircraft object:
          - aircraft.DesignPW
          - aircraft.DesignWTOoS
        """

        self.EvaluateConstraints(self.WTOoS, self.DISA)
        
        PWMatrix = np.matrix([self.PWCruise, self.PWTakeOff, self.PWAEOClimb, self.PWTurn, self.PWCeiling, self.PWAcceleration, self.PWOEIClimb])
        WTOoSrange = self.WTOoS[self.WTOoS <= self.WTOoSLanding]
        self.MaxPW = np.zeros(len(WTOoSrange))
        for i in range(len(WTOoSrange)):
            self.MaxPW[i] = np.max(PWMatrix[:,i])

        self.aircraft.DesignPW = np.min(self.MaxPW)
        self.aircraft.DesignWTOoS = self.WTOoS[np.argmin(self.MaxPW)]
        return None