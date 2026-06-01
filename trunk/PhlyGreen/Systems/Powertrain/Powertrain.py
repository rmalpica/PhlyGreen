import numpy as np
import numbers
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed
import PhlyGreen.Utilities.Units as Units
import os
from .propeller_hamilton import Propeller
from .graph import (traditional_graph, parallel_hybrid_graph, serial_hybrid_graph,
                    fuelcell_battery_graph)
from .efficiency import OperatingPoint, ConstantEfficiency
from scipy.optimize import brentq, brenth, ridder, newton

class Powertrain:
    """
    The Powertrain class.

    This class provides efficiency chains for several propulsive architectures. It also computes Class I estimates of the powertrain mass.
    Efficiency chains are computed by properly assembling user-provided efficiencies of each powertrain component. Components efficiencies can be constant or can depend on the operating condition. Also, Hamilton model for propeller efficiency is available.
    Several powertrain architectures are available (traditional, hybrid-series, hybrid-parallel), with reference to De Vries, R., Brown, M., and Vos, R., “Preliminary Sizing Method for Hybrid-Electric Distributed-Propulsion Aircraft,” Journal of Aircraft, Vol. 56, No. 6, 2019, pp. 2172–2188.
    In addition to the on-board efficiency chain, the well-to-tank chain can be also taken into account.

    """
    def __init__(self, aircraft):
        self.aircraft = aircraft
        #thermal powerplant efficiencies
        self.EtaGTmodelType = 'constant'
        self.EtaPPmodelType = 'constant'
        self.EtaGT = None
        self.EtaGB = None 
        self.EtaPP = None 
        #well-to-wake efficiencies
        self.EtaCH = None 
        self.EtaGR = None 
        self.EtaEX = None 
        self.EtaPR = None 
        self.EtaTR = None 
        self.EtaSourceToBattery = None 
        self.EtaSourceToFuel = None 
        #electric powerplant efficiencies 
        self.EtaPM = None
        self.EtaEM = None
        self.EtaEM1 = None
        self.EtaEM2 = None
        self.EtaFC = None  # fuel-cell system efficiency (constant; or use fc_model)
        #specific powers
        self.SPowerPT = None 
        self.SPowerPMAD = None  
        #components mass
        self.WThermal = None
        self.WElectric = None
        #components rating
        self.engineRating = None
        #optional Class-II efficiency models (EfficiencyModel objects). When set, they
        #make the corresponding graph efficiency depend on the operating point
        #(altitude, velocity, power). Left as None -> the constant Eta* values are used,
        #preserving legacy behavior.
        self.em_model = None   # electric motor (parallel hybrid / fuel-cell-battery)
        self.fc_model = None   # fuel-cell system efficiency (fuel-cell-battery)
        # Class-II nominal (design) powers [W], fixed before the mission (None for Class-I).
        self.gt_design_power = None
        self.em_design_power = None
        self.n_engines = 1


    """ Properties """

    @property
    def EtaGTmodelType(self):
        return self._EtaGTmodelType
      
    @EtaGTmodelType.setter
    def EtaGTmodelType(self,value):
        if value in ('constant', 'ResponseSurface'):
            self._EtaGTmodelType = value
        else:
            raise ValueError("Error: %s Eta GT model not implemented. Exiting" %value)

    @property
    def EtaPPmodelType(self):
        return self._EtaPPmodelType

    @EtaPPmodelType.setter
    def EtaPPmodelType(self,value):
        if value in ('constant', 'Hamilton', 'Surrogate', 'RBF'):
            self._EtaPPmodelType = value
        else:
            raise ValueError("Error: %s Eta PP model not implemented. Exiting" %value)


    @property
    def EtaGT(self):
        if self._EtaGT == None:
            raise ValueError("Eta Gas Turbine unset. Exiting")
        return self._EtaGT
      
    @EtaGT.setter
    def EtaGT(self,value):
        self._EtaGT = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Gas Turbine: %e. Exiting" %value)
    
    @property
    def EtaGB(self):
        if self._EtaGB == None:
            raise ValueError("Eta Gearbox unset. Exiting")
        return self._EtaGB
      
    @EtaGB.setter
    def EtaGB(self,value):
        self._EtaGB = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Gearbox: %e. Exiting" %value)

    @property
    def EtaPP(self):
        if self._EtaPP == None:
            raise ValueError("Eta Propulsive unset. Exiting")
        return self._EtaPP
      
    @EtaPP.setter
    def EtaPP(self,value):
        self._EtaPP = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Propulsive: %e. Exiting" %value)
 
    @property
    def EtaCH(self):
        if self._EtaCH == None:
            raise ValueError("Eta Charge unset. Exiting")
        return self._EtaCH
      
    @EtaCH.setter
    def EtaCH(self,value):
        self._EtaCH = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Charge: %e. Exiting" %value)

    @property
    def EtaGR(self):
        if self._EtaGR == None:
            raise ValueError("Eta Grid unset. Exiting")
        return self._EtaGR
      
    @EtaGR.setter
    def EtaGR(self,value):
        self._EtaGR = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Grid: %e. Exiting" %value)

    @property
    def EtaEX(self):
        if self._EtaEX == None:
            raise ValueError("Eta Extraction unset. Exiting")
        return self._EtaEX
      
    @EtaEX.setter
    def EtaEX(self,value):
        self._EtaEX = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Extraction: %e. Exiting" %value)

    @property
    def EtaPR(self):
        if self._EtaPR == None:
            raise ValueError("Eta Production unset. Exiting")
        return self._EtaPR
      
    @EtaPR.setter
    def EtaPR(self,value):
        self._EtaPR = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Production: %e. Exiting" %value)

    @property
    def EtaTR(self):
        if self._EtaTR == None:
            raise ValueError("Eta Transportation unset. Exiting")
        return self._EtaTR
      
    @EtaTR.setter
    def EtaTR(self,value):
        self._EtaTR = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Transportation: %e. Exiting" %value)

    @property
    def EtaSourceToBattery(self):
        if self._EtaSourceToBattery == None:
            raise ValueError("Eta Source-to-Battery unset. Exiting")
        return self._EtaSourceToBattery
      
    @EtaSourceToBattery.setter
    def EtaSourceToBattery(self,value):
        self._EtaSourceToBattery = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Source-to-battery: %e. Exiting" %value)

    @property
    def EtaSourceToFuel(self):
        if self._EtaSourceToFuel== None:
            raise ValueError("Eta Source-to-Fuel unset. Exiting")
        return self._EtaSourceToFuel
      
    @EtaSourceToFuel.setter
    def EtaSourceToFuel(self,value):
        self._EtaSourceToFuel = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Source-to-fuel: %e. Exiting" %value)

    @property
    def EtaPM(self):
        if self._EtaPM == None:
            raise ValueError("Eta PMAD unset. Exiting")
        return self._EtaPM
      
    @EtaPM.setter
    def EtaPM(self,value):
        self._EtaPM = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta PMAD: %e. Exiting" %value)

    @property
    def EtaEM(self):
        if self._EtaEM == None:
            raise ValueError("Eta Electric Motor unset. Exiting")
        return self._EtaEM
      
    @EtaEM.setter
    def EtaEM(self,value):
        self._EtaEM = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Electric Motor: %e. Exiting" %value)

    @property
    def EtaEM1(self):
        if self._EtaEM1 == None:
            raise ValueError("Eta Electric Motor-1 unset. Exiting")
        return self._EtaEM1
      
    @EtaEM1.setter
    def EtaEM1(self,value):
        self._EtaEM1 = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Electric Motor-1: %e. Exiting" %value)

    @property
    def EtaEM2(self):
        if self._EtaEM2 == None:
            raise ValueError("Eta Electric Motor-2 unset. Exiting")
        return self._EtaEM2
      
    @EtaEM2.setter
    def EtaEM2(self,value):
        self._EtaEM2 = value
        if(isinstance(value, numbers.Number) and (value <= 0 or value > 1.0)):
            raise ValueError("Error: Illegal Eta Electric Motor-2: %e. Exiting" %value)

    @property
    def SPowerPT(self):
        if self._SPowerPT == None:
            raise ValueError("Powertrain Specific Power unset. Exiting")
        return self._SPowerPT
      
    @SPowerPT.setter
    def SPowerPT(self,value):
        self._SPowerPT = value
        if(isinstance(value, numbers.Number) and (value <= 0)):
            raise ValueError("Error: Illegal Powertrain Specific Power: %e. Exiting" %value)

    @property
    def SPowerPMAD(self):
        if self._SPowerPMAD == None:
            raise ValueError("PMAD Specific Power unset. Exiting")
        return self._SPowerPMAD
      
    @SPowerPMAD.setter
    def SPowerPMAD(self,value):
        self._SPowerPMAD = value
        if(isinstance(value, numbers.Number) and (value <= 0)):
            raise ValueError("Error: Illegal PMAD Specific Power: %e. Exiting" %value)

    @property
    def WThermal(self):
        if self._WThermal == None:
            raise ValueError("Thermal powertrain Weight unset. Exiting")
        return self._WThermal
      
    @WThermal.setter
    def WThermal(self,value):
        self._WThermal = value
        if(isinstance(value, numbers.Number) and (value < 0)):
            raise ValueError("Error: Illegal Thermal powertrain Weight: %e. Exiting" %value)

    @property
    def WElectric(self):
        if self._WElectric == None:
            raise ValueError("Electric powertrain Weight unset. Exiting")
        return self._WElectric
      
    @WElectric.setter
    def WElectric(self,value):
        self._WElectric = value
        if(isinstance(value, numbers.Number) and (value < 0)):
            raise ValueError("Error: Illegal Electric powertrain Weight: %e. Exiting" %value)




    """ Methods """

    def SetInput(self):

        try:
            self.aircraft.EnergyInput['Eta Gas Turbine']
        except:
            print('Warning: Eta Gas Turbine value unset. Using Eta Gas Turbine Model.')
        else:
            self.EtaGT = self.aircraft.EnergyInput['Eta Gas Turbine']

        try:
            self.aircraft.EnergyInput['Eta Gas Turbine Model']
        except:
            print('Warning: Eta Gas Turbine model unset. Using constant model')
        else:
            self.EtaGTmodelType = self.aircraft.EnergyInput['Eta Gas Turbine Model']

        try:
            self.aircraft.EnergyInput['Eta Propulsive']
        except:
            print('Warning: Eta Propulsive value unset. Using Eta Eta Propulsive Model.')
        else:
            self.EtaPP = self.aircraft.EnergyInput['Eta Propulsive']

        try:
            self.aircraft.EnergyInput['Eta Propulsive Model'] 
        except:
            print('Warning: Eta Propulsive model unset. Using constant model')
        else: 
            self.EtaPPmodelType = self.aircraft.EnergyInput['Eta Propulsive Model'] 

        if self.EtaPPmodelType == 'Hamilton':
            self.Propeller = Propeller(self.aircraft)
            self.Propeller.SetInput()

        self.EtaGB = self.aircraft.EnergyInput['Eta Gearbox']
        self.SPowerPT = self.aircraft.EnergyInput['Specific Power Powertrain']
                
        if self.aircraft.WellToTankInput is not None:
            
            self.EtaCH = self.aircraft.WellToTankInput['Eta Charge']
            self.EtaGR = self.aircraft.WellToTankInput['Eta Grid']
            self.EtaEX = self.aircraft.WellToTankInput['Eta Extraction']
            self.EtaPR = self.aircraft.WellToTankInput['Eta Production']
            self.EtaTR = self.aircraft.WellToTankInput['Eta Transportation']
            
            self.EtaSourceToBattery = self.EtaCH * self.EtaGR
            self.EtaSourceToFuel = self.EtaEX * self.EtaPR * self.EtaTR


        
        # Optional fuel-cell system efficiency (used by PowerRatioFuelCellBattery).
        if 'Eta Fuel Cell' in self.aircraft.EnergyInput:
            self.EtaFC = self.aircraft.EnergyInput['Eta Fuel Cell']

        if (self.aircraft.Configuration == 'Hybrid'):

            self.EtaPM = self.aircraft.EnergyInput['Eta PMAD']
            # NOTE: SPowerPMAD is read and stored but not yet consumed by WeightPowertrain.
            # It is reserved for a future PMAD-mass term (SPowerPT is the one used today).
            self.SPowerPMAD = self.aircraft.EnergyInput['Specific Power PMAD']

            
            if (self.aircraft.HybridType == 'Parallel'):
        
                self.EtaEM = self.aircraft.EnergyInput['Eta Electric Motor']
                
            if (self.aircraft.HybridType == 'Serial'):

                self.EtaEM1 = self.aircraft.EnergyInput['Eta Electric Motor 1']
                self.EtaEM2 = self.aircraft.EnergyInput['Eta Electric Motor 2']

        self._build_efficiencies()
        return None

    def _build_efficiencies(self):
        """Assemble one :class:`EfficiencyModel` per powertrain component.

        Each component's efficiency is either Class-I (a constant, the default) or Class-II
        (a model that depends on the operating point). The choice is driven by the
        ``Eta <component> Model`` keys in ``EnergyInput`` (``'constant'`` |
        ``'ResponseSurface'`` for the gas turbine, ``'constant'`` | ``'Hamilton'`` |
        ``'Surrogate'`` for the propeller, ``'constant'`` | ``'Smart'`` for the motor).
        The result is stored in ``self.efficiency`` and read through :meth:`eta`.
        """
        e = self.aircraft.EnergyInput
        n_eng = 1
        if getattr(self.aircraft, 'PropellerInput', None):
            n_eng = int(self.aircraft.PropellerInput.get('Number of Engines', 1))

        # The constant Eta* are validating properties that raise when unset; read safely.
        def const(name, default):
            try:
                value = getattr(self, name)
            except Exception:
                return default
            return value if value is not None else default

        self.n_engines = n_eng
        # Class-II nominal (design) powers [W]; None for Class-I components. These are fixed
        # before the mission and used by the over/under-size check after sizing.
        self.gt_design_power = e.get('GT Design Power')
        self.em_design_power = e.get('EM Design Power')

        eff = {}
        eff['gearbox'] = ConstantEfficiency(const('EtaGB', 1.0))
        eff['pmad'] = ConstantEfficiency(const('EtaPM', 1.0))

        # Gas turbine: Class-I constant or Class-II response surface (needs a nominal power).
        if self.EtaGTmodelType == 'ResponseSurface':
            from .efficiency import GasTurbineEfficiencyModel
            if not self.gt_design_power:
                raise ValueError(
                    "Class-II gas turbine selected but 'GT Design Power' [W] is not set. "
                    "Size the engine before the mission (e.g. DesignPW * WTO) and pass it "
                    "in EnergyInput as 'GT Design Power'.")
            eff['gas_turbine'] = GasTurbineEfficiencyModel(
                design_power=self.gt_design_power, n_engines=n_eng)
        else:
            eff['gas_turbine'] = ConstantEfficiency(const('EtaGT', 0.30))

        # Propeller: Class-I constant, Class-II Hamilton, or Class-II RBF surrogate.
        if self.EtaPPmodelType == 'Hamilton':
            from .efficiency import HamiltonPropellerEfficiency
            eff['propeller'] = HamiltonPropellerEfficiency(self.Propeller)
        elif self.EtaPPmodelType in ('Surrogate', 'RBF'):
            from .efficiency import PropellerSurrogateEfficiency
            eff['propeller'] = PropellerSurrogateEfficiency(
                rpm=e.get('Propeller RPM', 1200.0), n_engines=n_eng)
        else:
            eff['propeller'] = ConstantEfficiency(const('EtaPP', 0.85))

        # Electric motor: Class-I constant or Class-II d-q model (needs a nominal power).
        if e.get('Eta Electric Motor Model') == 'Smart':
            from .efficiency import MotorEfficiencyModel
            if not self.em_design_power:
                raise ValueError(
                    "Class-II electric motor selected but 'EM Design Power' [W] is not set. "
                    "Size the motor before the mission (e.g. DesignPW * WTO) and pass it in "
                    "EnergyInput as 'EM Design Power'.")
            eff['electric_motor'] = MotorEfficiencyModel(
                (self.em_design_power / n_eng) / 1000.0, e.get('EM Design Voltage', 800.0),
                e.get('EM Design RPM', 11000.0), n_engines=n_eng)
        else:
            eff['electric_motor'] = ConstantEfficiency(const('EtaEM', 1.0))

        eff['fuel_cell'] = ConstantEfficiency(const('EtaFC', 0.50))
        self.efficiency = eff

    def _thermal_power_timeline(self):
        """Return (altitude[m], velocity[m/s], gas-turbine shaft power[W]) along the mission."""
        import numpy as np
        m = self.aircraft.mission
        sols = getattr(m, "integral_solution", None)
        if not sols:
            return None
        prof, perf = m.profile, self.aircraft.performance
        WTO, WS, DISA = self.aircraft.weight.WTO, self.aircraft.DesignWTOoS, m.DISA
        t = np.concatenate([s.t for s in sols])
        beta = np.concatenate([s.y[-1] for s in sols])
        alt = np.array([float(prof.Altitude(x)) for x in t])
        vel = np.array([float(prof.Velocity(x)) for x in t])
        pe = np.array([float(prof.PowerExcess(x)) for x in t])
        PP = np.array([WTO * perf.PoWTO(WS, beta[i], pe[i], 1, alt[i], DISA, vel[i], 'TAS')
                       for i in range(len(t))])
        cfg = self.aircraft.Configuration
        if cfg == 'Traditional':
            p_th = np.array([self.Traditional(alt[i], vel[i], PP[i])[1] * PP[i]
                             for i in range(len(t))])
        elif cfg == 'Hybrid':
            phi = np.array([float(prof.SuppliedPowerRatio(x)) for x in t])
            p_th = np.array([self.Hybrid(float(phi[i]), alt[i], vel[i], PP[i])[1] * PP[i]
                             for i in range(len(t))])
        else:
            p_th = np.zeros(len(t))
        return alt, vel, p_th

    def report_class_ii_sizing(self, raise_on_undersize=False):
        """Check the Class-II GT/EM nominal power against what the mission demands.

        Run after the weight-sizing loop. For the **gas turbine** the check is altitude
        aware: the available shaft power lapses with altitude, so a turbine whose *peak
        demand* is below its nominal can still be **power-limited** at altitude (unable to
        deliver the required power — the aircraft cannot sustain that flight condition). We
        walk the mission and compare the required power to the power *available* from the
        response surface at each point. For the **electric motor** (no altitude lapse) we
        compare the peak electric power to the nominal.

        Returns ``{component: {...}}`` (including ``power_limited`` and ``min_nominal`` — the
        nominal power needed to avoid power-limiting — for the GT) and warns (or raises) when
        a component is undersized.
        """
        import warnings
        import numpy as np
        import PhlyGreen.Utilities.Units as Units
        import PhlyGreen.Utilities.Speed as Speed
        from .efficiency import GasTurbineEfficiencyModel

        report = {}
        m = self.aircraft.mission

        def warn_or_raise(msg):
            if raise_on_undersize:
                raise ValueError(msg)
            warnings.warn(msg)

        # --- Gas turbine: altitude-aware power-limit check ---
        gt = getattr(self, "efficiency", {}).get("gas_turbine")
        if self.gt_design_power and isinstance(gt, GasTurbineEfficiencyModel):
            timeline = self._thermal_power_timeline()
            worst_ratio, peak_demand = 0.0, 0.0
            if timeline is not None:
                alt, vel, p_th = timeline
                design_hp = Units.wTohp(self.gt_design_power) / self.n_engines
                for i in range(len(alt)):
                    a = Speed.soundspeed(alt[i], 0.0)
                    mach = vel[i] / a if a > 0 else 0.0
                    req_hp = Units.wTohp(p_th[i]) / self.n_engines
                    _, _, pmax_hp, _ = gt.surrogate.predict(design_hp, Units.mToft(alt[i]),
                                                            mach, req_hp)
                    if pmax_hp > 0:
                        worst_ratio = max(worst_ratio, req_hp / pmax_hp)
                    peak_demand = max(peak_demand, float(p_th[i]))
            power_limited = worst_ratio > 1.0 + 1e-6
            min_nominal = self.gt_design_power * worst_ratio   # to make available >= demand
            # Status from the altitude-aware load ratio (peak required / peak available).
            status = "UNDERSIZED" if power_limited else ("oversized" if worst_ratio < 0.5 else "ok")
            report["gas turbine"] = {
                "nominal": self.gt_design_power, "peak_demand": peak_demand,
                "worst_load_ratio": worst_ratio, "power_limited": power_limited,
                "min_nominal": min_nominal, "status": status}
            if power_limited:
                warn_or_raise(
                    f"gas turbine is undersized (power-limited at altitude): required power "
                    f"exceeds the available power by up to {(worst_ratio-1)*100:.0f}% — the "
                    f"engine cannot sustain flight. Increase 'GT Design Power' to at least "
                    f"{min_nominal/1e3:.0f} kW.")

        # --- Electric motor: peak electric power vs nominal (no altitude lapse) ---
        if self.em_design_power:
            actual = getattr(m, "Max_PBat", 0.0) or 0.0
            ratio = actual / self.em_design_power
            status = "UNDERSIZED" if ratio > 1.0 else ("oversized" if ratio < 0.5 else "ok")
            report["electric motor"] = {"nominal": self.em_design_power, "peak_demand": actual,
                                        "worst_load_ratio": ratio, "status": status}
            if status == "UNDERSIZED":
                warn_or_raise(
                    f"electric motor is undersized: peak {actual/1e3:.1f} kW exceeds the "
                    f"nominal {self.em_design_power/1e3:.1f} kW. Increase 'EM Design Power'.")
        return report

    def eta(self, component, alt=0.0, vel=0.0, pwr=0.0, rpm=None):
        """Efficiency of ``component`` at the operating point (altitude, velocity, power).

        Components: ``'gas_turbine'``, ``'propeller'``, ``'gearbox'``, ``'electric_motor'``,
        ``'pmad'``, ``'fuel_cell'``. An externally-set ``em_model``/``fc_model`` overrides
        the electric-motor/fuel-cell entry (back-compatible Class-II injection).
        """
        op = OperatingPoint(altitude=alt, velocity=vel, power=pwr, rpm=rpm)
        if component == 'electric_motor' and self.em_model is not None:
            return self.em_model.eta(op)
        if component == 'fuel_cell' and self.fc_model is not None:
            return self.fc_model.eta(op)
        return self.efficiency[component].eta(op)

    def PowerLapse(self,altitude,DISA):
        """ Full throttle power lapse, to be used in constraint analysis. Source: Ruijgrok, Elements of airplane performance, Eq.(6.7-11)"""
        n = 0.75
        lapse = (ISA.atmosphere.RHOstd(altitude,DISA)/ISA.atmosphere.RHOstd(0.0,DISA))**n
        return lapse
    
    def Traditional(self, alt, vel, pwr):
        """Power ratios for the traditional gas-turbine chain.

        Delegates to the component-graph engine (:func:`graph.traditional_graph`); see
        :meth:`_traditional_legacy` for the original hand-coded 4x4 system that this
        reproduces. Output order: ``[Pf/Pp, Pgt/Pp, Pgb/Pp, Pp/Pp]``.
        """
        g = traditional_graph(self.eta('gas_turbine', alt, vel, pwr),
                              self.eta('gearbox', alt, vel, pwr),
                              self.eta('propeller', alt, vel, pwr))
        return g.solve()

    def Hybrid(self, phi, alt, vel, pwr):
        """Power ratios for the hybrid-electric chain (parallel or serial).

        Delegates to the component-graph engine; see :meth:`_hybrid_legacy` for the
        original hand-coded systems this reproduces. ``abs`` is applied to avoid ``-0``
        for the battery ratio when ``phi == 0``. Output order:
        parallel ``[Pf, Pgt, Pgb, Ps1, Pe1, Pbat, Pp1]`` / serial
        ``[Pf, Pgt, Pgb, Ps1, Pe1, Pbat, Pgen, Pp1]`` (all /Pp).
        """
        self.phi = phi
        if self.aircraft.HybridType == 'Parallel':
            g = parallel_hybrid_graph(self.eta('gas_turbine', alt, vel, pwr),
                                      self.eta('gearbox', alt, vel, pwr), self.eta('pmad', alt, vel, pwr),
                                      self.eta('electric_motor', alt, vel, pwr),
                                      self.eta('propeller', alt, vel, pwr), phi)
        elif self.aircraft.HybridType == 'Serial':
            g = serial_hybrid_graph(self.eta('gas_turbine', alt, vel, pwr), self.EtaEM1,
                                    self.eta('pmad', alt, vel, pwr), self.EtaEM2,
                                    self.eta('gearbox', alt, vel, pwr),
                                    self.eta('propeller', alt, vel, pwr), phi)
        else:
            raise Exception("Unknown hybrid type: %s" % self.aircraft.HybridType)
        return np.abs(g.solve())

    def PowerRatioFuelCellBattery(self, phi, alt, vel, pwr):
        """Power ratios for a fuel-cell + battery (gas-turbine-free) hybrid.

        Demonstrates an arbitrary hybridization assembled on the powertrain graph: a fuel
        cell and a battery share an electrical bus feeding the motor/gearbox/propeller.
        Requires ``EtaFC`` (or a ``fc_model``); ``em_model`` makes the motor efficiency
        operating-point dependent. Output order:
        ``[PfH2, Pfc, Pbat, Pe1, Pem, Pgb, Pp1]`` (all /Pp), so ``[0]`` is hydrogen power
        and ``[2]`` is battery power.
        """
        g = fuelcell_battery_graph(self.eta('fuel_cell', alt, vel, pwr),
                                   self.eta('pmad', alt, vel, pwr),
                                   self.eta('electric_motor', alt, vel, pwr),
                                   self.eta('gearbox', alt, vel, pwr),
                                   self.eta('propeller', alt, vel, pwr), phi)
        return np.abs(g.solve())

    def _traditional_legacy(self,alt,vel,pwr):
        """
        Compute the power ratios across a traditional gas-turbine propulsion
        chain.

        This function solves a 4x4 linear system representing the steady-state power
        balance between fuel power, gas-turbine shaft power, gearbox power, and
        delivered propulsive power. The solution is expressed in nondimensional
        form, normalized by the propulsive power P_p.

        Parameters
        ----------
        alt : float
            Aircraft altitude [m].
        vel : float
            True airspeed [m/s].
        pwr : float
            Requested shaft power.

        These inputs are required for quering the instantaneous values of the components efficiencies 
        if models are provided. Otherwise, the constant user-provided values are employed.

        Returns
        -------
        numpy.ndarray of shape (4,)
            Normalized power ratios, in the following order:

            - Pf/Pp : fuel power to propulsive power ratio 
            - Pgt/Pp : gas-turbine shaft power to propulsive power ratio 
            - Pgb/Pp : gearbox output power to propulsive power ratio 
            - Pp/Pp  : always equal to 1

        Notes
        -----
        The system matrix is upper-triangular and could be solved analytically.
        However, using ``np.linalg.solve`` keeps the expression general and ensures
        numerical robustness with negligible computational overhead.
        """
        

        A = np.array([[- self.eta('gas_turbine',alt,vel,pwr), 1, 0, 0],
                      [0, - self.EtaGB, 1, 0],
                      [0, 0, - self.eta('propeller',alt,vel,pwr), 1],
                      [0, 0, 0, 1]])
       
        b = np.array([0, 0, 0, 1])
        
        PowerRatio = np.linalg.solve(A,b)

        #Ordine output   Pf/Pp  Pgt/Pp   Pgb/Pp  Pp/Pp 
        return PowerRatio

    
    def _hybrid_legacy(self,phi,alt,vel,pwr):
        """
        Compute power ratios for hybrid-electric propulsion architectures.

        This function assembles and solves a linear system representing the steady-state
        power balance across all components of a hybrid propulsion system. Two
        architectures are supported:

        1. **Parallel hybrid**
           Includes:
           - Gas turbine (GT) engine
           - Gearbox (GB)
           - Electric motor/generator (EM)
           - Power electronics and/or management system(PM)
           - Propulsive device, e.g., propeller (PP)
           - Hybrid power-split defined by ``phi``

           The returned power ratios correspond to:
           ``[Pf/Pp, Pgt/Pp, Pgb/Pp, Ps1/Pp, Pe1/Pp, Pbat/Pp, Pp1/Pp]``

        2. **Serial hybrid**
           Includes:
           - Gas turbine (GT) engine
           - generator (EM1)
           - Power electronics and/or management system(PM)
           - Electric motor (EM2)
           - Gearbox (GB)
           - Propulsive device, e.g., propeller (PP)
           - Hybrid power-split constraint defined by ``phi``

           The returned power ratios correspond to:
           ``[Pf/Pp, Pgt/Pp, Pgb/Pp, Ps1/Pp, Pe1/Pp, Pbat/Pp, Pgen/Pp, Pp1/Pp]``

        Parameters
        ----------
        phi : float
            Hybrid power-split ratio.  
            - In parallel mode: fraction of propulsive power supplied electrically.  
            - In serial mode: fraction of generator/battery power routed to propulsion.
        alt : float
            Aircraft altitude [m].
        vel : float
            True airspeed [m/s].
        pwr : float
            Requested shaft power level.

        Returns
        -------
        numpy.ndarray
            Vector of nondimensional power ratios, normalized by propulsive power P_p.
            The output order depends on the hybrid configuration (parallel or serial).

        Notes
        -----
        - The function constructs a 7x7 (parallel) or 8x8 (serial) linear system and
          solves it using ``np.linalg.solve``.
        - The systems have block-triangular structure, but closed-form analytical
          expressions would be lengthy and less maintainable than the numerical solve.
        - All efficiencies (GT, GB, EM, PM, PP) are evaluated at the given flight
          condition, if models are available.
        """
        
        # phi = self.aircraft.mission.profile.SuppliedPowerRatio(t)
        self.phi = phi

        if (self.aircraft.HybridType == 'Parallel'):
        
            A = np.array([[- self.eta('gas_turbine',alt,vel,pwr), 1, 0, 0, 0, 0, 0],
                      [0, -self.EtaGB, -self.EtaGB, 1, 0, 0, 0],
                      [0, 0, 0, 0, 1, -self.EtaPM, 0],
                      [0, 0, 1, 0, - self.EtaEM, 0, 0],
                      [0, 0, 0, - self.eta('propeller',alt,vel,pwr), 0, 0, 1],
                      [phi, 0, 0, 0, 0, phi - 1, 0],
                      [0, 0, 0, 0, 0, 0, 1]])
       
            b = np.array([0, 0, 0, 0, 0, 0, 1])
            
            #Ordine output   Pf/Pp  Pgt/Pp   Pgb/Pp  Ps1/Pp  Pe1/Pp   Pbat/Pp    Pp1/Pp 

        
        elif (self.aircraft.HybridType == 'Serial'):
                        
            A = np.array([[- self.EtaGT, 1, 0, 0, 0, 0, 0, 0],
                      [0, - self.EtaEM1, 0, 1, 0, 0, 0, 0],
                      [0, 0, 0, -self.EtaPM, 1, -self.EtaPM, 0, 0],
                      [0, 0, 1, 0,  - self.EtaEM2, 0, 0, 0],
                      [0, 0, - self.EtaGB, 0, 0, 0, 1, 0],
                      [0, 0, 0, 0, 0, 0, - self.eta('propeller',alt,vel,pwr), 1],
                      [phi, 0, 0, 0, 0, phi - 1, 0, 0],
                      [0, 0, 0, 0, 0, 0, 0, 1]])
       
            b = np.array([0, 0, 0, 0, 0, 0, 0, 1])

        
        PowerRatio = np.linalg.solve(A,b)
        
    #Ordine output   Pf/Pp  Pgt/Pp   Pgb/Pp    Pe1/Pp  Pe2/Pp   Pbat/Pp   Ps2/Pp   Pp1/Pp 
        return np.abs(PowerRatio)  #here abs is used to avoid that Pbat/Pp = -0 when phi=0
        
        
    def WeightPowertrain(self,WTO):
        """
        This function estimates the total weight of the propulsion powertrain based on the aircraft
        configuration (traditional or hybrid) and the maximum required power level.

        This function inherits from the mission class the installed power requirements for the propulsion
        system and converts them into component weights using specific power
        coefficients (shaft-power-to-weight ratios). The methodology differs for
        traditional and hybrid-electric architectures:

        - **Traditional configuration**
          Only the thermal (gas-turbine) powertrain is present. The peak required
          shaft power is determined as the maximum between:
            1. Mission maximum engine power corrected by power lapse, and
            2. Take-Off (TO) required propulsive power.
          The thermal powertrain weight is obtained by dividing this peak shaft
          power by the thermal specific power ratio ``SPowerPT[0]``.

        - **Hybrid configuration**
          Both thermal and electric subsystems are sized independently:
            * Thermal subsystem: same criterion as in traditional case.
            * Electric subsystem: peak battery power is the maximum between mission
              maximum electric power and TO electric power.
          The total powertrain weight is the sum of thermal and electric subsystem
          weights, computed using ``SPowerPT[0]`` and ``SPowerPT[1]`` respectively.

        Parameters
        ----------
        WTO : float
            Take-off weight of the aircraft [kg].  
            (Currently unused inside the method but included for interface
            compatibility.)

        Returns
        -------
        float
            Total estimated powertrain weight [kg]. Fuel and Battery weights are not included.

        Attributes Updated
        ------------------
        engineRating : float
            Rated thermal shaft power required for the mission [W].
        WThermal : float
            Weight of the thermal propulsion subsystem [kg].
        WElectric : float, optional
            Weight of the electric power subsystem (only for hybrid configurations)
            [kg].

        Notes
        -----
        - ``SPowerPT`` is assumed to contain the specific power (W/kg) for thermal
          and electric powertrain components. 
        - ``PowerLapse(alt, vel)`` is used to compute the reduction in available
          GT power with altitude.
        - Raises an exception if an unsupported aircraft configuration is provided.
        """
        
        if self.aircraft.Configuration == 'Traditional':
        
                PeakPwr = np.max(
                    [self.aircraft.mission.Max_PEng / self.PowerLapse(self.aircraft.mission.Max_PEng_alt,0), 
                     self.aircraft.mission.TO_PP]
                     ) #maximum among take-off shaft power and mission shaft-power (adjusted with power-lapse)

                self.engineRating = PeakPwr #shaft power 
                self.WThermal = PeakPwr /self.SPowerPT[0]
                WPT = self.WThermal
                
        elif self.aircraft.Configuration == 'Hybrid':
   
                
                PeakPwrEng = np.max(
                    [self.aircraft.mission.Max_PEng / self.PowerLapse(self.aircraft.mission.Max_PEng_alt,0), 
                     self.aircraft.mission.TO_PP]
                     ) #maximum among take-off shaft power and mission shaft-power (adjusted with power-lapse)
                PeakPwrBat = np.max([self.aircraft.mission.Max_PBat, self.aircraft.mission.TO_PBat])

                self.engineRating = PeakPwrEng #shaft power

                self.WThermal = PeakPwrEng /self.SPowerPT[0]
                self.WElectric = PeakPwrBat /self.SPowerPT[1] 

                WPT = self.WThermal + self.WElectric 

        else:
             raise Exception("Unknown aircraft configuration: %s" %self.aircraft.Configuration)
                
        return WPT
    

