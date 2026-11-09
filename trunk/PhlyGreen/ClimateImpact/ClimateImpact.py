import os
import numpy as np
import numbers
import scipy.integrate as integrate
import matplotlib.pyplot as plt
import statistics
import PhlyGreen.Utilities.Atmosphere as ISA
from PhlyGreen.Systems.Powertrain.gas_turbine_surrogate import _isa_pressure_ratio


class ClimateImpact:
    """
    Computes the climate impact of an aircraft concept over a finite time horizon H,
    following the classical climate-chemistry impulse-response modelling framework
    used in global aviation climate assessments (e.g. Dallara et al. 2011, Sausen et al. 2000).

    The module evaluates:
        • Annual emissions of CO2, H2O, SO4, soot, and NOx
        • Radiative forcing contributions of all species:
              CO2, H2O, SO4, soot, CH4, O3 (short- and long-lived), contrails (AIC)
        • Temperature response ΔT(t) from convolution of RF *(t) with the climate kernel
        • ATR(H): Average Temperature Response over the time horizon H

    NOx is estimated either with the Filippone semi-empirical correlation or with the
    emission-index response surface of the engine class (``'Surrogate'``: PW127 turboprop map,
    or the CFM56-class map for a Turbofan), which also gives CO and UHC. Both integrate the
    flown mission and add the ground segments (taxi-out, take-off run, taxi-in) that
    ``Mission._ground_segments`` adds to the fuel, so NOx/CO/UHC and CO2 cover the same fuel.

    Inputs expected in `aircraft.ClimateImpactInput`:
        H             : time horizon [yr]
        N             : number of missions per year
        Y             : operative years
        Grid_CO2      : CO2 intensity of electricity [kg CO2 / MJ]
        WTW_CO2       : well-to-wake CO2 intensity of fuel [kg CO2 / MJ]
        EINOx_model   : {'unset', 'Filippone', 'Surrogate'}

    The class relies on mission profiles produced by the Mission module, including:
        • the continuous mission solution (``aircraft.MissionType = 'Continue'``, the default
          that ``build_aircraft`` sets; ``'Discrete'`` is the legacy discretised path)
        • power demand, beta schedule, supplied power ratio (Hybrid), etc.

    Outputs (stored internally):
        self.mission_emissions = dict with keys:
            'co2', 'h2o', 'so4', 'soot', 'nox' (+ 'co', 'uhc' with the surrogate)
        self.ground_emissions : the ground-segment share of the fuel and of NOx (CO, UHC)
        self.media_pesata_quote : altitude-weighted average cruise height
        self.frazioni_di_missione : altitude PDF over mission range
        ATR(H)                   : final climate metric [K]

    Notes
    -----
    • All forcings are normalized by RF_2CO2 to be expressed in CO2-equivalent units.
    • Impulse response functions follow simplified standard forms for climate metrics.
    """
    def __init__(self, aircraft):
        self.aircraft = aircraft
        self.H = None   # orizzonte temporale in anni
        self.N = None   # numero di voli all'anno (durante gli anni di attività)
        self.Y = None   # numero di anni di attività
        self.EINOx_model = 'unset'

        self.RF_2CO2 = 3.7  # [W/m^2]

        self.step = 100
        self.mission_data = None
        self.r_ch4_o3l_o3s = None
        self.frazioni_di_missione = None
        self.media_pesata_quote = None

        self.Altitudes_for_forcing = np.array([0.,17447.281192838538, 19453.378415830608, 21460.09644698188, 23467.346599412453, 25430.608059420214, 27438.30164625021, 29445.817859320436, 31497.588825453135, 33459.60866914251, 35463.488720137466, 37469.14250873012, 39476.83609556012, 41484.263621750455]) * 0.3048
        self.s_o3l_data = [0.8670472811928384, 0.8670472811928384, 0.9270217837148719, 0.9591633870997543, 0.9674482197956505, 0.9478927627810728, 0.9362969532361473, 0.9326534005875508, 0.9449217523049352, 0.9810320935646583, 1.1404098072908004, 1.2202649520536557, 1.2086691425087306, 1.209001718308298]
        self.s_o3s_data = [0.47341795539789, 0.47341795539789, 0.5612179664837501, 0.6211924690057832, 0.7129759991131311, 0.7172847033608635, 0.81702049036454, 0.9326534005875508, 1.0125085453504057, 1.1361011030430688, 1.4346433124549636, 1.6377584391109141, 1.805088409733385, 1.9406019621972175]
        self.s_aic_data = [0.02808417863015744, 0.02808417863015744, 0.0005838552925743201, 0.004892559540306318, 0.17619865861094175, 0.4031705559558786, 0.8011159765718826, 1.2547198048888641, 1.7123071522273343, 2.1102525728433386, 1.8282800288232357, 1.5423313563549694, 0.9740775640670324, 0.803429226022208]


        self.mission_emissions_calculated = False  # Flag per indicare se le emissioni della missione sono state calcolate
        self.mission_emissions = {
            'co2': None,
            'h2o': None,
            'so4': None,
            'soot': None,
            'nox': None
        }

        # Optional state-dependent emission-index surrogate (see
        # Systems.Powertrain.emissions_surrogate.EmissionSurrogate). When attached, the opt-in
        # method mission_emissions_from_surrogate() integrates EI(alt, Mach, power) x fuel-flow
        # over the mission for NOx/CO/UHC, as an alternative to the Filippone NOx correlation.
        # Default None -> existing behaviour is unchanged.
        self.emission_surrogate = None
        # Ground-segment (taxi-out, take-off run, taxi-in) share of the mission emissions [kg],
        # filled by calculate_mission_emissions: {'fuel', 'nox'} (+ 'co', 'uhc' with the surrogate).
        self.ground_emissions = {}
    

    """ Properties """

    @property
    def EINOx_model(self):
        """Selected emissions model: {'unset', 'Filippone', 'Surrogate'}.

        ``'Filippone'`` — semi-empirical gas-turbine NOx correlation (default). ``'Surrogate'`` —
        the packaged emission-index response surface of the engine class (PW127 turboprop map,
        or the CFM56-class map for a Turbofan), which provides NOx, CO and UHC as a function of
        altitude, Mach and load fraction along the mission (see
        :class:`PhlyGreen.Systems.Powertrain.emissions_surrogate.EmissionSurrogate`). Both add
        the ground segments.
        """
        return self._EINOx_model

    @EINOx_model.setter
    def EINOx_model(self,value):
        if value in ('Filippone', 'unset', 'Surrogate'):
            self._EINOx_model = value
        else:
            raise ValueError("Error: %s EINOx model not implemented. Exiting" %value)

    @property
    def H(self):
        if self._H == None:
            raise ValueError("Time horizon unset. Exiting")
        return self._H
          
    @H.setter
    def H(self,value):
        self._H = value
        if(isinstance(value, numbers.Number) and value <= 0):
            raise ValueError("Error: Illegal time horizon: %e. Exiting" %value)
        
    @property
    def N(self):
        if self._N == None:
            raise ValueError("Number of missions per year unset. Exiting")
        return self._N
          
    @N.setter
    def N(self,value):
        self._N = value
        if(isinstance(value, numbers.Number) and value <= 0):
            raise ValueError("Error: Illegal number of missions per year %e. Exiting" %value)
        
    @property
    def Y(self):
        if self._Y == None:
            raise ValueError("Number of operative years unset. Exiting")
        return self._Y
          
    @Y.setter
    def Y(self,value):
        self._Y = value
        if(isinstance(value, numbers.Number) and value <= 0):
            raise ValueError("Error: Illegal number of operative years %e. Exiting" %value)





    """ Methods """

    def SetInput(self):
        """
        Load climate-impact parameters from aircraft.ClimateImpactInput.

        Expected fields:
            H, N, Y, Grid_CO2, WTW_CO2, EINOx_model
        """
        required_keys = {'H', 'N', 'Y', 'EINOx_model'}
        if required_keys.issubset(self.aircraft.ClimateImpactInput.keys()):
            self.H = self.aircraft.ClimateImpactInput.get("H")
            self.N = self.aircraft.ClimateImpactInput.get("N")
            self.Y = self.aircraft.ClimateImpactInput.get("Y")
            self.Grid_CO2 = self.aircraft.ClimateImpactInput.get("Grid_CO2")
            self.WTW_CO2 = self.aircraft.ClimateImpactInput.get("WTW_CO2")
            self.EINOx_model = self.aircraft.ClimateImpactInput.get("EINOx_model")
        else:
            raise ValueError("Error: Missing required climate impact input keys")

        
    # prossimi passi:
    # - definire la funzione U(t) del numero di voli (i valori di t sono anni);
    # - definire le emissioni annuali E_i con i = co2, nox, h2o, so4, soot;
    # - definire i forcing factor s(h) di ch4, o3l, o3s;
    # - definire i forzanti radiativi RF*_i(t) (che sono normalizzati e moltiplicati per l'efficacia) con i = co2, 
    #   ch4, o3l, o3s, h2o, so4, soot;
    # - sommare gli RF*_i(t) per ottenere RF*(t);
    # - fare la convoluzione di RF*(t) con G_T per ottenere DeltaTemp(t);
    # - ATR_H è la media temporale di DeltaTemp in H anni.

    # NB: dato che non posso usare * nel nome di funzioni o variabili, di seguito gli RF* saranno indicati come rf
        


    # NUMERO DI VOLI ALL'ANNO

    def U(self,year):
        """
        Annual mission count function U(t).

        Model:
            • Ramp-up from 0 to N over 30 years
            • Steady operation for 5 years
            • Linear phase-out to 0 over 30 years
        """

        if year >= 0 and year <= 30:

            U = np.interp(year, [0, 30], [0, self.N])

        elif year > 30 and year <= 35:

            U = self.N

        elif year > 35 and year <= 65:

            U = np.interp(year, [35, 65], [self.N, 0]) 

        else:
            
            U = 0

        # if year >= 0 and year <= self.Y:
        #     U = self.N
        # else:
        #     U = 0
        return U



    # EMISSIONI ANNUALI

    # Emission indices [kg / kg fuel]. Hydrocarbon (Jet-A) values are the ones the model was
    # set up with. Hydrogen: no carbon or sulphur, so no CO2, SO4 or soot; the water is the
    # stoichiometric product of H2 + 1/2 O2 -> H2O, M(H2O)/M(H2) = 18.015/2.016 = 8.94.
    EI_HYDROCARBON = {'co2': 3.16, 'h2o': 1.26, 'so4': 2e-4, 'soot': 4e-5}
    EI_HYDROGEN = {'co2': 0.0, 'h2o': 8.94, 'so4': 0.0, 'soot': 0.0}

    # Filippone NOx correlation coefficients, one row per LTO phase: climb-out, idle, approach.
    # The flown mission uses climb-out for the climbs, idle for the cruises and approach for
    # the descents; the ground segments use climb-out for the take-off run and idle for taxi.
    FILIPPONE_COEFF = np.array([
        [0.7194e+1, 0.5609e+0, -0.1059e-1, -0.3223e+1, 0.2889e+0, 0.2591e+0],
        [0.1605e+0, 0.2412e+0, -0.1650e-2, -0.8818e+1, 0.3714e+2, -0.2268e+0],
        [ 0.3699e+0, 0.5470e+0, -0.7445e-2, -0.6914e+1, 0.6782e+1, 0.1138e+0]
    ])

    def _burns_hydrogen(self):
        """True for the configurations whose fuel is hydrogen (fuel cell, with or without battery)."""
        return self.aircraft.Configuration in ('Hydrogen', 'FuelCellBattery')

    def _fuel_mass_burnt(self):
        """Fuel burnt over the mission (incl. diversion and ground segments) [kg].

        Hydrocarbon paths: ``weight.Wf``, which is exactly the burnt fuel. Hydrogen paths:
        ``weight.Wf`` also carries the H2 sizing margin (``h2_fuel_margin``), which is loaded
        but not burnt, so the burnt mass is taken from the mission energy instead.
        """
        if self._burns_hydrogen():
            return self.aircraft.weight.TotalEnergies[0] / self.aircraft.weight.ef
        return self.aircraft.weight.Wf

    def _upstream_fuel_co2(self, fuel_mass):
        """Well-to-tank CO2 of the fuel [kg]: ``WTW_CO2`` [kg CO2 / MJ] times the fuel energy.

        The fuel energy is ``fuel_mass * Ef``, with ``Ef`` the specific energy set in
        ``EnergyInput`` (43.5 MJ/kg Jet-A in the turboprop examples, the HHV for the fuel-cell
        configurations), so ``WTW_CO2`` must be expressed per MJ of that same basis.
        """
        if self.WTW_CO2 is None:
            raise ValueError("ClimateImpactInput needs 'WTW_CO2' (upstream CO2 of the fuel, "
                             "kg CO2 per MJ of EnergyInput['Ef']).")
        return self.WTW_CO2 * fuel_mass * self.aircraft.weight.ef * 1e-6

    def _grid_battery_co2(self):
        """CO2 of the grid electricity that charged the battery [kg] (0 without a battery).

        Counted for every configuration that draws battery energy (Hybrid and
        FuelCellBattery). The charger and grid efficiencies come from the well-to-wake module
        when ``WellToTankInput`` is given; otherwise the pathway is lossless (1.0), as in
        :class:`~PhlyGreen.WellToWake.WellToWake`.
        """
        energies = np.atleast_1d(getattr(self.aircraft.weight, 'TotalEnergies', 0.0))
        if energies.size < 2 or not energies[1]:
            return 0.0
        if self.Grid_CO2 is None:
            raise ValueError("ClimateImpactInput needs 'Grid_CO2' (kg CO2 per MJ of grid "
                             "electricity) because this design draws battery energy.")
        eta_source_to_battery = getattr(self.aircraft.welltowake, 'EtaSourceToBattery', 1.0)
        source_battery_MJ = energies[1] * 1e-6 / eta_source_to_battery
        return self.Grid_CO2 * source_battery_MJ

    def calculate_mission_emissions(self):
        """
        Compute single-mission emitted mass of:
            CO₂, H₂O, SO₄, soot, and NOx.

        CO₂ includes:
            • Tank-to-wake emissions (zero for hydrogen)
            • Upstream WTW fuel CO₂ (``WTW_CO2`` per MJ of ``EnergyInput['Ef']``)
            • Upstream grid CO₂ for battery energy (Hybrid and FuelCellBattery)

        NOx is computed using the Filippone empirical model (or the EI surrogate, which also
        gives CO and UHC) for the gas-turbine configurations, over the flown mission plus the
        ground segments (taxi-out, take-off run, taxi-in; see :meth:`_ground_legs`). A fuel
        cell emits no NOx. The contrail term (``rf_AIC``)
        keeps its kerosene-derived parametrisation for every configuration; for a fuel cell,
        whose exhaust is cool and water-rich, it is a placeholder, not a model.
        """
        Wf = self._fuel_mass_burnt()  # [kg]
        EI = self.EI_HYDROGEN if self._burns_hydrogen() else self.EI_HYDROCARBON

        # CO2
        self.mission_emissions['co2'] = (EI['co2'] * Wf + self._upstream_fuel_co2(Wf)
                                         + self._grid_battery_co2())

        # H2O
        self.mission_emissions['h2o'] = EI['h2o'] * Wf

        # SO4
        self.mission_emissions['so4'] = EI['so4'] * Wf

        # SOOT
        self.mission_emissions['soot'] = EI['soot'] * Wf

        # NOX: a fuel cell has no combustion, hence no thermal NOx.
        if self._burns_hydrogen():
            if self.EINOx_model == 'Surrogate':
                raise ValueError("The NOx emission-index surrogate is for gas turbines; a fuel "
                                 "cell emits no NOx (use EINOx_model 'Filippone' or 'unset').")
            self.mission_emissions['nox'] = 0.0
            self.mission_emissions_calculated = True
            return

        # NOX
        def E_nox_1m():  # emissione di NOx in kg della singola missione
                
                if self.EINOx_model == 'Filippone':
                    times = np.array([])
                    beta = np.array([])
                    for array in self.aircraft.mission.integral_solution:
                        times = np.concatenate([times, array.t])
                        if self.aircraft.Configuration in ('Traditional', 'Turbofan'):
                            beta = np.concatenate([beta, array.y[1]])
                        elif self.aircraft.Configuration == 'Hybrid':
                            beta = np.concatenate([beta, array.y[2]])

                    # times = self.aircraft.mission.MissionTimes
                    # beta = self.aircraft.mission.Beta_Output 
                    
                    v0 = self.aircraft.mission.profile.Velocity(times)  # [m/s]
                    alt = self.aircraft.mission.profile.Altitude(times)  # [m]

                    if self.aircraft.Configuration == 'Hybrid':
                        spr = [self.aircraft.mission.profile.SuppliedPowerRatio(t) for t in times]


                    # calculate breakpoint times
                    breakpoint_times = np.zeros(5)
                    alt_cruise = self.aircraft.MissionStages['Cruise']['input']['Altitude']
                    alt_start_diversion = self.aircraft.DiversionStages['Climb1']['input']['StartAltitude']
                    alt_diversion_cruise = self.aircraft.DiversionStages['Cruise']['input']['Altitude']
                    indices_alt_cruise = np.where(alt == alt_cruise)
                    breakpoint_times[0] = times[indices_alt_cruise[0][0]]
                    breakpoint_times[1] = times[indices_alt_cruise[0][-1]]
                    indices_alt_start_diversion = np.where(alt == alt_start_diversion)
                    for index in indices_alt_start_diversion[0]:
                        if times[index] > breakpoint_times[1]:
                            breakpoint_times[2] = times[index]
                            break
                    indices_alt_diversion_cruise = np.where(alt == alt_diversion_cruise)
                    for index in indices_alt_diversion_cruise[0]:
                        if times[index] > breakpoint_times[2]:
                            breakpoint_times[3] = times[index]
                            break
                    breakpoint_times[4] = times[indices_alt_diversion_cruise[0][-1]]


                    portata = np.zeros(len(times))  # [kg(fuel)/s]
                    coeff = self.FILIPPONE_COEFF
                    # coeff sono i coefficienti del metodo di Filippone per climbout, idle e approach

                    EI_NOx = np.zeros(len(times))  # [g/kg(fuel)]
                    # Overall pressure ratio and engine count drive the Filippone correlation.
                    # Both were hard-coded to a 2-engine PW127 turboprop; a turbofan runs at
                    # OPR ~30, which roughly doubles the predicted EINOx. Defaults preserve
                    # the previous numbers for every configuration that does not set them.
                    OPR = self._opr()
                    n_eng = self._n_engines()
                

                    for t in range(len(times)):
                        power = (self.aircraft.weight.WTO) * self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,beta[t],self.aircraft.mission.profile.PowerExcess(times[t]),1,alt[t],self.aircraft.mission.DISA,v0[t],'TAS')
                        if self.aircraft.Configuration in ('Traditional', 'Turbofan'):
                            PRatio = self.aircraft.powertrain.Traditional(alt[t],v0[t],power) 
                        elif self.aircraft.Configuration == 'Hybrid':
                            PRatio = self.aircraft.powertrain.Hybrid(spr[t],alt[t],v0[t],power)
                        portata[t] = power * PRatio[0]/self.aircraft.weight.ef


           


                        if times[t] <= breakpoint_times[0] or (times[t] <= breakpoint_times[3] and times[t] >= breakpoint_times[2]):
                            c = coeff[0]
                        elif (times[t] > breakpoint_times[0] and times[t] < breakpoint_times[1]) or (times[t] > breakpoint_times[3] and times[t] < breakpoint_times[4]):
                            c = coeff[1]
                        else:
                            c = coeff[2]

                        mfuel = portata[t] / n_eng  # fuel flow of a single engine
                        
                    

                        EI_NOx[t] =  2*(c[0] + c[1]*OPR + c[2]*(OPR)**2 + c[3]*mfuel + c[4]*(mfuel)**2 + c[5]*OPR*mfuel)


                    # plt.figure(2)
                    # plt.plot(times/60, EI_NOx, 'b')
                    # plt.grid(visible=True)
                    # plt.xlabel('t [min]')
                    # plt.ylabel('EI_NOx [g/kg(fuel)]')
                    # plt.show()    

                    integranda = portata*EI_NOx
                    massa_di_NOx = integrate.cumulative_trapezoid(integranda, times, initial=0.0)
                    # l'elemento n-esimo del vettore massa_di_NOx è l'integrale definito dell'integranda tra t = 0 e t = times[n]
                    E_nox_1m = massa_di_NOx[-1]


                    return E_nox_1m* 10**(-3)



        def E_nox_1m_DISCRETO():  # emissione di NOx in kg della singola missione
                
                if self.EINOx_model == 'Filippone':

                    beta = self.aircraft.mission.beta_values
                    times = self.aircraft.mission.profile.DiscretizedTime
                   

                    v0 = self.aircraft.mission.profile.DiscretizedVelocities  # [m/s]
                    alt = self.aircraft.mission.profile.DiscretizedAltitudes  # [m]

                    if self.aircraft.Configuration == 'Hybrid':
                        spr = [self.aircraft.mission.profile.SuppliedPowerRatio(t) for t in times]


                    breakpoint_times = np.zeros(5)

                    breakpoint_times[0] = self.aircraft.mission.profile.BreaksClimb[-1]
                    breakpoint_times[1] = self.aircraft.mission.profile.TimesCruise[-1] 
                    breakpoint_times[2] = self.aircraft.mission.profile.BreaksDescent[-1]
                    breakpoint_times[3] = self.aircraft.mission.profile.BreaksClimbDiversion[-1]
                    breakpoint_times[4] = self.aircraft.mission.profile.TimesCruiseDiversion[-1]
                    

                    portata = np.zeros(len(times))  # [kg(fuel)/s]
                    coeff = self.FILIPPONE_COEFF
                    # coeff sono i coefficienti del metodo di Filippone per climbout, idle e approach

                    EI_NOx = np.zeros(len(times))  # [g/kg(fuel)]
                    # Overall pressure ratio and engine count drive the Filippone correlation.
                    # Both were hard-coded to a 2-engine PW127 turboprop; a turbofan runs at
                    # OPR ~30, which roughly doubles the predicted EINOx. Defaults preserve
                    # the previous numbers for every configuration that does not set them.
                    OPR = self._opr()
                    n_eng = self._n_engines()
                

                    for t in range(len(times)):
                        power = (self.aircraft.weight.WTO) * self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,beta[t],self.aircraft.mission.profile.DiscretizedPowerExcess[t],1,alt[t],self.aircraft.mission.DISA,v0[t],'TAS')
                        if self.aircraft.Configuration in ('Traditional', 'Turbofan'):
                            PRatio = self.aircraft.powertrain.Traditional(alt[t],v0[t],power) 
                        elif self.aircraft.Configuration == 'Hybrid':
                            PRatio = self.aircraft.powertrain.Hybrid(spr[t],alt[t],v0[t],power)
                        portata[t] = power * PRatio[0]/self.aircraft.weight.ef


           


                        if times[t] <= breakpoint_times[0] or (times[t] <= breakpoint_times[3] and times[t] >= breakpoint_times[2]):
                            c = coeff[0]
                        elif (times[t] > breakpoint_times[0] and times[t] < breakpoint_times[1]) or (times[t] > breakpoint_times[3] and times[t] < breakpoint_times[4]):
                            c = coeff[1]
                        else:
                            c = coeff[2]

                        mfuel = portata[t] / n_eng  # fuel flow of a single engine
                        
                        

                        EI_NOx[t] =  2*(c[0] + c[1]*OPR + c[2]*(OPR)**2 + c[3]*mfuel + c[4]*(mfuel)**2 + c[5]*OPR*mfuel)


                    # plt.figure(2)
                    # plt.plot(times/60, EI_NOx, 'b')
                    # plt.grid(visible=True)
                    # plt.xlabel('t [min]')
                    # plt.ylabel('EI_NOx [g/kg(fuel)]')
                    # plt.show()    

                    integranda = portata*EI_NOx
                    massa_di_NOx = integrate.cumulative_trapezoid(integranda, times, initial=0.0)
                    # l'elemento n-esimo del vettore massa_di_NOx è l'integrale definito dell'integranda tra t = 0 e t = times[n]
                    E_nox_1m = massa_di_NOx[-1]


                    return E_nox_1m* 10**(-3)



        if self._mission_type() == 'Continue':
            nox = E_nox_1m()
        elif self._mission_type() == 'Discrete':
            nox = E_nox_1m_DISCRETO()

        # Ground segments (taxi-out, take-off run, taxi-in): their fuel is in weight.Wf (hence
        # in CO2) but not in the flown mission integrated above.
        self.ground_emissions = {}
        if self.EINOx_model == 'Filippone':
            self.ground_emissions = self._ground_emissions_filippone()
            nox = nox + self.ground_emissions['nox']

        self.mission_emissions['nox'] = nox

        # With the gas-turbine emission-index surrogate selected, override NOx and add CO/UHC from
        # the response surface (CO2/H2O/SO4/soot keep their fixed-EI values computed above).
        if self.EINOx_model == 'Surrogate':
            self._integrate_surrogate_emissions()

        self.mission_emissions_calculated = True


    def _opr(self):
        """Overall pressure ratio for the Filippone NOx correlation.

        Defaults to 15.77 (the PW127-class turboprop the correlation was set up with) so
        existing designs are unchanged; a turbofan should set ``EnergyConfig.opr``.
        """
        energy = getattr(self.aircraft, 'EnergyInput', None) or {}
        return float(energy.get('OPR') or 15.77)

    def _n_engines(self):
        """Number of engines the fuel flow is split over (the correlation is per engine).

        The powertrain's engine count (``powertrain.n_engines``, the one count of the model),
        or 2 if the powertrain does not carry one.
        """
        n_engines = getattr(self.aircraft.powertrain, 'n_engines', None)
        if n_engines is None:
            return 2
        return max(int(n_engines), 1)

    def _mission_type(self):
        """``aircraft.MissionType``: 'Continue' (default) or the legacy 'Discrete'."""
        return getattr(self.aircraft, 'MissionType', 'Continue')

    def _filippone_einox(self, phase_row, mfuel_engine):
        """Filippone EINOx [g/kg] for one coefficient row and a fuel flow per engine [kg/s]."""
        c = self.FILIPPONE_COEFF[phase_row]
        OPR = self._opr()
        return 2 * (c[0] + c[1] * OPR + c[2] * OPR ** 2 + c[3] * mfuel_engine
                    + c[4] * mfuel_engine ** 2 + c[5] * OPR * mfuel_engine)

    def _ground_legs(self):
        """The ground segments of the sized mission, one dict per leg.

        Read-only use of the Mission. The legs, their durations [s] and their fuel chemical
        powers [W] are ``mission._ground_fuel_legs_out`` / ``_ground_fuel_legs_in``, the same
        numbers ``Mission._ground_segments`` adds to the mission fuel (hence to ``weight.Wf``).
        All legs are flown at the take-off condition (``mission._ground_condition``), at
        ``takeoff_power_fraction`` (take-off run) or ``taxi_power_fraction`` (taxi) of the
        take-off-field propulsive power ``mission._takeoff_power(WTO)``; this is rebuilt here
        to call the powertrain at the same point and read its gas-turbine shaft power.

        Each dict: ``name``, ``duration`` [s], ``fuel_flow`` [kg/s], ``altitude`` [m],
        ``velocity`` [m/s TAS] of the powertrain call, ``mach`` for the emission query (0 for
        taxi, the take-off Mach for the run), ``mach_takeoff`` (the Mach of the powertrain
        call), ``propulsive_power`` [W], ``shaft_power`` [W]
        (gas-turbine shaft, all engines) and ``filippone_row`` (0 = climb-out for the take-off
        run, 1 = idle for taxi). Returns [] if the mission has no ground segments.
        """
        m = self.aircraft.mission
        legs = (list(getattr(m, '_ground_fuel_legs_out', None) or [])
                + list(getattr(m, '_ground_fuel_legs_in', None) or []))
        if not legs:
            return []
        alt, vel = m._ground_condition()
        P_TO = m._takeoff_power(self.aircraft.weight.WTO)
        T = ISA.atmosphere.Tstd(float(alt)) + m.DISA
        mach_takeoff = vel / (20.0468 * np.sqrt(T))
        out = []
        for name, duration, fuel_chemical_power in legs:
            is_takeoff = (name == 'Takeoff')
            fraction_of_takeoff = m.takeoff_power_fraction if is_takeoff else m.taxi_power_fraction
            phi = m._takeoff_phi() if is_takeoff else m._taxi_phi()
            P = fraction_of_takeoff * P_TO
            if self.aircraft.Configuration == 'Hybrid':
                PRatio = self.aircraft.powertrain.Hybrid(phi, alt, vel, P)
            else:
                PRatio = self.aircraft.powertrain.Traditional(alt, vel, P)
            # shaft power = fuel chemical power x (shaft / fuel) of the powertrain at this point
            shaft = fuel_chemical_power * PRatio[1] / PRatio[0] if PRatio[0] > 0 else 0.0
            out.append({'name': name, 'duration': float(duration),
                        'fuel_flow': fuel_chemical_power / self.aircraft.weight.ef,
                        'altitude': float(alt), 'velocity': float(vel),
                        'mach': float(mach_takeoff) if is_takeoff else 0.0,
                        'mach_takeoff': float(mach_takeoff),
                        'propulsive_power': float(P), 'shaft_power': float(shaft),
                        'filippone_row': 0 if is_takeoff else 1})
        return out

    def _ground_emissions_filippone(self):
        """Fuel [kg] and NOx [kg] of the ground segments with the Filippone correlation."""
        n_eng = self._n_engines()
        fuel, nox_g = 0.0, 0.0
        for leg in self._ground_legs():
            ei = self._filippone_einox(leg['filippone_row'], leg['fuel_flow'] / n_eng)
            fuel += leg['fuel_flow'] * leg['duration']
            nox_g += ei * leg['fuel_flow'] * leg['duration']
        return {'fuel': float(fuel), 'nox': float(nox_g) * 1e-3}

    def _ensure_emission_surrogate(self):
        """Attach the packaged EmissionSurrogate matching this configuration, if none was set.

        A combustor calibration is engine-specific: the turboprop artifact is keyed on a
        shaft-power fraction and a lean combustor, the turbofan one on a thrust fraction and a
        CFM56-class combustor. Selecting by configuration stops the wrong one being used silently.
        """
        if self.emission_surrogate is None:
            from PhlyGreen.Systems.Powertrain.emissions_surrogate import (
                EmissionSurrogate, default_model_path)
            self.emission_surrogate = EmissionSurrogate(
                default_model_path(self.aircraft.Configuration))
        return self.emission_surrogate

    def _surrogate_load_fraction(self, alt, mach, propulsive_power, shaft_power, velocity, rating):
        """Third coordinate of the emission map at the given points (arrays).

        Each artifact is read at the coordinate it was generated at:

        * Turboprop (PW127 map, 'Traditional'/'Hybrid'): the gas-turbine SHAFT power over the
          power available at the altitude, ``P_shaft / (engineRating * delta(h))``, with
          ``delta`` the ISA pressure ratio. ``emissions_pipeline/pw127_partpower.py`` runs the
          deck at a gross power ``G(f) * delta(h)`` for a useful-power fraction ``f``, so
          ``f`` is a fraction of the rated power lapsed by ``delta`` (the same lapse as the
          turboshaft efficiency map). The shaft power is ``PRatio[1] * P``: in a Hybrid it is
          the thermal share only, the battery share does not pass through the combustor.
          ``engineRating`` is rated with ``Powertrain.PowerLapse``. With the Class-II
          gas-turbine map that is ``delta`` itself, so the fraction peaks at exactly 1 at the
          sizing point. With constant efficiencies it is Ruijgrok's density ratio ** 0.75,
          which lapses less than ``delta``: at altitude the fraction then exceeds 1 (up to 1.75
          on the turboprop reference of examples/common.py) and the surrogate clips it to the
          map edge (full power).
        * Turbofan (CFM56-class map): the THRUST ``F = P / V`` over the lapsed available thrust
          ``engineRating * ThrustLapse(h, M)``, the map's ``ThrustFraction`` (``F / F_max(h, M)``
          of ``data/HBTF_turbofan.py``, with ``ThrustLapse = F_max(h, M) / F_SLS``).

        ``rating`` is the whole-aircraft value (all engines); the fraction is the same per
        engine.
        """
        if self.aircraft.Configuration == 'Turbofan':
            thrust = propulsive_power / np.maximum(velocity, 1e-6)
            lapse = np.array([self.aircraft.powertrain.ThrustLapse(alt[i], mach[i],
                                                                   self.aircraft.mission.DISA)
                              for i in range(len(alt))])
            return thrust / np.maximum(rating * lapse, 1e-9)
        delta = np.array([_isa_pressure_ratio(float(a) / 0.3048) for a in alt])
        return shaft_power / np.maximum(rating * delta, 1e-9)

    def _surrogate_rating(self, power_fraction_basis, alt, propulsive_power, shaft_power, velocity):
        """Rating the load fraction is taken against: ``engineRating`` (shaft power [W], SLS
        thrust [N] for a Turbofan). Without one (or with another ``power_fraction_basis``), the
        peak of the mission, so that the most loaded point reads as full power."""
        rating = getattr(self.aircraft.powertrain, 'engineRating', None) \
            if power_fraction_basis == 'engineRating' else None
        if rating and rating > 0:
            return rating
        if self.aircraft.Configuration == 'Turbofan':
            return float(np.max(propulsive_power / np.maximum(velocity, 1e-6))) or 1.0
        delta = np.array([_isa_pressure_ratio(float(a) / 0.3048) for a in alt])
        return float(np.max(shaft_power / delta)) or 1.0

    def _integrate_surrogate_emissions(self, power_fraction_basis='engineRating'):
        """Set ``mission_emissions['nox'|'co'|'uhc']`` from the EI surrogate; return them.

        Walks the (continuous) mission exactly as the Filippone path does — recovering, at each
        solver point, the altitude, true airspeed and required propulsive power, hence the fuel
        mass flow ``portata = power * PRatio[0] / ef`` and the gas-turbine shaft power
        ``PRatio[1] * power`` — then queries the surrogate for ``EI(alt_ft, Mach, fraction)``
        and integrates ``EI * portata`` over time. The fraction is the coordinate of the map
        (:meth:`_surrogate_load_fraction`): shaft power over ``engineRating * delta(h)`` for
        the turboprop map, thrust over the lapsed available thrust for a Turbofan. Inputs
        outside the map box are clipped to it by the surrogate.

        The ground segments (taxi-out, take-off run, taxi-in, :meth:`_ground_legs`) are added
        at their constant fuel flows; their share is stored in ``self.ground_emissions``. Taxi
        runs at 7 % of the take-off power by default, below the 0.3 lower edge of both maps,
        so it is read at the map edge (approach EI): the taxi NOx is then overestimated and the
        taxi CO underestimated relative to an idle index. Does not touch CO2 (the caller
        handles it). Thermal-engine configs only.
        """
        if self.aircraft.Configuration not in ('Traditional', 'Hybrid', 'Turbofan'):
            raise ValueError("The EI surrogate path applies to thermal-engine configurations "
                             "(Traditional / Hybrid / Turbofan) only.")
        if self._mission_type() != 'Continue':
            raise ValueError("The EI surrogate path requires MissionType == 'Continue'.")
        self._ensure_emission_surrogate()

        # --- 1. walk the mission (same recovery as the Filippone path) ---
        times = np.array([])
        beta = np.array([])
        for arr in self.aircraft.mission.integral_solution:
            times = np.concatenate([times, arr.t])
            beta = np.concatenate([beta, arr.y[1] if self.aircraft.Configuration in ('Traditional', 'Turbofan')
                                   else arr.y[2]])
        v0 = self.aircraft.mission.profile.Velocity(times)   # [m/s] TAS
        alt = self.aircraft.mission.profile.Altitude(times)  # [m]
        spr = ([self.aircraft.mission.profile.SuppliedPowerRatio(t) for t in times]
               if self.aircraft.Configuration == 'Hybrid' else None)

        DISA = self.aircraft.mission.DISA
        power = np.zeros(len(times))
        shaft = np.zeros(len(times))     # gas-turbine shaft power [W], all engines
        portata = np.zeros(len(times))   # [kg fuel / s]
        for t in range(len(times)):
            p = self.aircraft.weight.WTO * self.aircraft.performance.PoWTO(
                self.aircraft.DesignWTOoS, beta[t],
                self.aircraft.mission.profile.PowerExcess(times[t]), 1, alt[t], DISA, v0[t], 'TAS')
            if self.aircraft.Configuration in ('Traditional', 'Turbofan'):
                PRatio = self.aircraft.powertrain.Traditional(alt[t], v0[t], p)
            else:
                PRatio = self.aircraft.powertrain.Hybrid(spr[t], alt[t], v0[t], p)
            power[t] = p
            shaft[t] = p * PRatio[1]
            portata[t] = p * PRatio[0] / self.aircraft.weight.ef

        # --- 2. operating-point coordinates for the surrogate ---
        T = np.array([ISA.atmosphere.Tstd(float(a)) for a in alt]) + DISA   # static temp [K]
        mach = v0 / (20.0468 * np.sqrt(T))           # a = sqrt(gamma R T), gamma R ~ 401.9
        alt_ft = alt / 0.3048
        rating = self._surrogate_rating(power_fraction_basis, alt, power, shaft, v0)
        power_fraction = self._surrogate_load_fraction(alt, mach, power, shaft, v0, rating)

        # --- 3. EI(alt, Mach, fraction) along the mission, then integrate EI * fuel-flow ---
        X = np.column_stack([alt_ft, mach, power_fraction])
        ei = self.emission_surrogate.predict(X)      # {'EINOX','EICO','EIUHC'} in g/kg fuel

        # --- 4. ground segments at constant fuel flow ---
        legs = self._ground_legs()
        species = {'nox': 'EINOX', 'co': 'EICO', 'uhc': 'EIUHC'}
        ground = {'fuel': float(sum(leg['fuel_flow'] * leg['duration'] for leg in legs))}
        ei_ground = {}
        if legs:
            g_alt = np.array([leg['altitude'] for leg in legs])
            g_mach = np.array([leg['mach'] for leg in legs])
            g_power = np.array([leg['propulsive_power'] for leg in legs])
            g_shaft = np.array([leg['shaft_power'] for leg in legs])
            g_vel = np.array([leg['velocity'] for leg in legs])
            # The thrust lapse of every leg is taken at the take-off Mach, where Mission flies
            # them; only the emission query uses Mach 0 for taxi.
            g_mach_lapse = np.array([leg['mach_takeoff'] for leg in legs])
            g_fraction = self._surrogate_load_fraction(g_alt, g_mach_lapse, g_power, g_shaft,
                                                       g_vel, rating)
            ei_ground = self.emission_surrogate.predict(
                np.column_stack([g_alt / 0.3048, g_mach, g_fraction]))
        g_mass = np.array([leg['fuel_flow'] * leg['duration'] for leg in legs])

        out = {}
        for key, col in species.items():
            if col in ei:
                grams = integrate.cumulative_trapezoid(np.asarray(ei[col]) * portata, times,
                                                       initial=0.0)[-1]
                grams_ground = float(np.sum(np.asarray(ei_ground[col]) * g_mass)) if legs else 0.0
                ground[key] = grams_ground * 1e-3
                self.mission_emissions[key] = (float(grams) + grams_ground) * 1e-3   # g -> kg
                out[key] = self.mission_emissions[key]
        self.ground_emissions = ground
        return out

    def mission_emissions_from_surrogate(self, power_fraction_basis='engineRating'):
        """Single-mission NOx/CO/UHC (+ CO2) mass [kg] from the EI surrogate (standalone helper).

        Convenience that runs :meth:`_integrate_surrogate_emissions` and also fills CO2. For the
        integrated accounting, set ``ClimateImpactInput['EINOx_model'] = 'Surrogate'`` and call
        :meth:`calculate_mission_emissions` (which keeps CO2/H2O/SO4/soot consistent). Attaches the
        packaged surrogate of the configuration (PW127, or the turbofan map for a Turbofan)
        automatically if ``self.emission_surrogate`` is unset.
        """
        self._integrate_surrogate_emissions(power_fraction_basis)   # thermal engines only
        Wf = self._fuel_mass_burnt()
        self.mission_emissions['co2'] = (self.EI_HYDROCARBON['co2'] * Wf
                                         + self._upstream_fuel_co2(Wf) + self._grid_battery_co2())
        self.mission_emissions_calculated = True
        return self.mission_emissions


    # ----------------------------------------------------------------------
    #                   EMISSION FUNCTIONS E_i(year)
    # ----------------------------------------------------------------------
    #         
    def E_co2(self,year):
        if not self.mission_emissions_calculated:
            self.calculate_mission_emissions()

        Eco2 = self.mission_emissions['co2']*self.U(year)
        return Eco2
    

    def E_h2o(self,year):
        if not self.mission_emissions_calculated:
            self.calculate_mission_emissions()

        Eh2o = self.mission_emissions['h2o']*self.U(year)
        return Eh2o
    

    def E_so4(self,year):
        if not self.mission_emissions_calculated:
            self.calculate_mission_emissions()

        Eso4 = self.mission_emissions['so4']*self.U(year)
        return Eso4
    

    def E_soot(self,year):
        if not self.mission_emissions_calculated:
            self.calculate_mission_emissions()

        Esoot = self.mission_emissions['soot']*self.U(year)
        return Esoot
    
            
    def E_nox(self,year):
        if not self.mission_emissions_calculated:
            self.calculate_mission_emissions()

        Enox = self.mission_emissions['nox']*self.U(year)
        return Enox
        


    # FORCING FACTOR DI CH4, O3L, O3S
        

    def calculate_mission_data(self):
        d = self.aircraft.mission.profile.Distances
        dd = self.aircraft.mission.profile.DistancesDiversion
        l_cruise = self.aircraft.mission.profile.MissionRange - np.sum(d)  
        l_dcruise = self.aircraft.mission.profile.DiversionRange - np.sum(dd)

        contatore = 0
        low_alt = np.array([])
        high_alt = np.array([])
        v_len =  np.array([])
        h_len =  np.array([])

        for phase, details in self.aircraft.MissionStages.items():

            if phase.startswith('Climb'):

                low_altitude = details['input']['StartAltitude']
                high_altitude = details['input']['EndAltitude']
                vl = high_altitude - low_altitude   # variazione di quota della salita
                hl = d[contatore]   # distanza orizzontale percorsa in salita
                contatore += 1

                low_alt = np.append(low_alt, low_altitude)
                high_alt = np.append(high_alt, high_altitude)
                v_len = np.append(v_len, vl)
                h_len = np.append(h_len, hl)


            elif phase.startswith('Descent'):
                low_altitude = details['input']['EndAltitude']
                high_altitude = details['input']['StartAltitude']
                vl = high_altitude - low_altitude   # variazione di quota della salita
                hl = d[contatore]   # distanza orizzontale percorsa in salita
                contatore += 1

                low_alt = np.append(low_alt, low_altitude)
                high_alt = np.append(high_alt, high_altitude)
                v_len = np.append(v_len, vl)
                h_len = np.append(h_len, hl)

            
            elif phase.startswith('Cruise'):
                low_altitude = details['input']['Altitude']
                high_altitude = details['input']['Altitude']
                vl = high_altitude - low_altitude   # variazione di quota della salita
                hl = l_cruise   # distanza orizzontale percorsa in salita

                low_alt = np.append(low_alt, low_altitude)
                high_alt = np.append(high_alt, high_altitude)
                v_len = np.append(v_len, vl)
                h_len = np.append(h_len, hl)


        contatore = 0
        for phase, details in self.aircraft.DiversionStages.items():

            if phase.startswith('Climb'):

                low_altitude = details['input']['StartAltitude']
                high_altitude = details['input']['EndAltitude']
                vl = high_altitude - low_altitude   # variazione di quota della salita
                hl = dd[contatore]   # distanza orizzontale percorsa in salita
                contatore += 1

                low_alt = np.append(low_alt, low_altitude)
                high_alt = np.append(high_alt, high_altitude)
                v_len = np.append(v_len, vl)
                h_len = np.append(h_len, hl)


            elif phase.startswith('Descent'):
                low_altitude = details['input']['EndAltitude']
                high_altitude = details['input']['StartAltitude']
                vl = high_altitude - low_altitude   # variazione di quota della salita
                hl = dd[contatore]   # distanza orizzontale percorsa in salita
                contatore += 1

                low_alt = np.append(low_alt, low_altitude)
                high_alt = np.append(high_alt, high_altitude)
                v_len = np.append(v_len, vl)
                h_len = np.append(h_len, hl)

            
            elif phase.startswith('Cruise'):
                low_altitude = details['input']['Altitude']
                high_altitude = details['input']['Altitude']
                vl = high_altitude - low_altitude   # variazione di quota della salita
                hl = l_dcruise   # distanza orizzontale percorsa in salita

                low_alt = np.append(low_alt, low_altitude)
                high_alt = np.append(high_alt, high_altitude)
                v_len = np.append(v_len, vl)
                h_len = np.append(h_len, hl)


        mission_data = np.stack((low_alt, high_alt, v_len, h_len))
        self.mission_data = mission_data



    def l(self,h):
        step = self.step
        TotalRange = self.aircraft.mission.profile.MissionRange + self.aircraft.mission.profile.DiversionRange

        if self.mission_data is None:
            self.calculate_mission_data()       
        mission_data = self.mission_data
        
        L = 0
        for i in range(len(mission_data[0])):

            if mission_data[0][i] == mission_data[1][i]:  # crociera
                if h <= mission_data[0][i] and h + step > mission_data[0][i]:
                    L = L + mission_data[3][i]

            else:
                if h >= mission_data[0][i] and h <= mission_data[1][i]:
                    if h + step <= mission_data[1][i]:
                        L = L + step * mission_data[3][i]/mission_data[2][i]
                    else:
                        L = L + (mission_data[1][i] - h) * mission_data[3][i]/mission_data[2][i]
                
                else:
                    if h + step >= mission_data[0][i] and h + step <= mission_data[1][i]:
                        L = L + (h + step - mission_data[0][i]) * mission_data[3][i]/mission_data[2][i]
        
        return L/TotalRange
    


    def calculate_frazioni_di_missione(self):

        if self.mission_data is None:
            self.calculate_mission_data()

        quote = np.arange(0, max(self.mission_data[1])+self.step, self.step)
        l = np.array([])
        for h in quote:
            l = np.append(l, self.l(h))

        frazioni_di_missione = np.stack((quote, l))
        self.frazioni_di_missione = frazioni_di_missione



    def calculate_media_pesata_quote(self):

        # if self.frazioni_di_missione is None:
        #     self.calculate_frazioni_di_missione()
        

        if self.aircraft.MissionType == 'Continue':
            self.calculate_frazioni_di_missione()
            self.media_pesata_quote = 0
            for i in range(len(self.frazioni_di_missione[0])):
                self.media_pesata_quote = self.media_pesata_quote + self.frazioni_di_missione[0][i]*self.frazioni_di_missione[1][i]
            self.media_pesata_quote = self.media_pesata_quote/sum(self.frazioni_di_missione[1])
            # times = np.linspace(0,self.aircraft.mission.profile.MissionTime2,num=1000)
            # alt = self.aircraft.mission.profile.Altitude(times)
            # self.media_pesata_quote = statistics.mean(alt)

        elif self.aircraft.MissionType == 'Discrete':
            # alt = self.aircraft.mission.profile.DiscretizedAltitudes
            # times = self.aircraft.mission.profile.DiscretizedTime
            # self.media_pesata_quote = statistics.mean(alt)
            self.calculate_frazioni_di_missione()
            self.media_pesata_quote = 0
            for i in range(len(self.frazioni_di_missione[0])):
                self.media_pesata_quote = self.media_pesata_quote + self.frazioni_di_missione[0][i]*self.frazioni_di_missione[1][i]
            self.media_pesata_quote = self.media_pesata_quote/sum(self.frazioni_di_missione[1])

        
    # RF*

    def rf_co2(self,year):

        def G_xco2(year):
            # qui G_xco2 non ha le dimensioni corrette perchè manca un fattore 10^-12, che aggiungerò a valle
            # della convoluzione per diminuire il tempo d'esecuzione dell'integrale
            alpha = np.array([0.1135, 0.152, 0.0970, 0.041])  # [moltiplicato per 10^-12 sarebbe ppmv/kg(CO2)]
            tau = np.array([313.8, 79.8, 18.8, 1.7])  # [anni]
            G_xco2 = 0.067e-12  # [moltiplicato per 10^-12 sarebbe ppmv/kg(CO2)]
            for i in range(len(alpha)):
                G_xco2 = G_xco2 + alpha[i]*np.exp(-year/tau[i])
            return G_xco2
        
        # def DeltaXCO2(year):
            
        #     integrand = lambda k: G_xco2(year - k) * self.E_co2(k)
        #     result, _ = integrate.quad(integrand, 0, year, epsabs=1e-4, epsrel=1e-3)
        #     return result*10**(-12)
        
        discretized_time = np.linspace(0,year,100)

        discretized_func = [G_xco2(year - time) * self.E_co2(time) for time in discretized_time]


        discretized_integral = integrate.trapezoid(discretized_func, x = discretized_time)

        XCO2_0 = 380 # concentrazione di background [ppmv]
        # rf_co2 = np.log((XCO2_0 + DeltaXCO2(year))/XCO2_0)/np.log(2)
        rf_co2 = np.log((XCO2_0 + discretized_integral*1e-12)/XCO2_0)/np.log(2)

        return rf_co2
    

    def rf_h2o(self,year):

        c_h2o = 7.43e-15 # [(w/m^2)/kg(h2o)]
        RF_h2o = c_h2o * self.E_h2o(year)
        eff_h2o = 1.14
        rf_h2o = RF_h2o * eff_h2o/self.RF_2CO2

        return rf_h2o
    

    def rf_so4(self,year):

        c_so4 = -1e-10 # [(w/m^2)/kg(so4)]
        RF_so4 = c_so4 * self.E_so4(year)
        eff_so4 = 0.9
        rf_so4 = RF_so4 * eff_so4/self.RF_2CO2

        return rf_so4
    

    def rf_soot(self,year):

        c_soot = 5e-10 # [(w/m^2)/kg(soot)]
        RF_soot = c_soot * self.E_soot(year)
        eff_soot = 0.7
        rf_soot = RF_soot * eff_soot/self.RF_2CO2

        return rf_soot
    

    def rf_ch4(self, year):

        # if self.media_pesata_quote is None:
        #     self.calculate_media_pesata_quote()

        def G_ch4(year):
            # qui G_ch4 non ha le dimensioni corrette perchè manca un fattore 10^-13, che aggiungerò a valle
            # della convoluzione per diminuire il tempo d'esecuzione dell'integrale
            A = -5.16  # [moltiplicato per 10^-13 sarebbe (W/m^2)/kg(NOx)]
            tau = 12  # [anni]
            G_ch4 = A*np.exp(-year/tau)
            return G_ch4
        

        discretized_time = np.linspace(0,year,100)

        discretized_func = [G_ch4(year - time) * self.E_nox(time) for time in discretized_time]

        discretized_integral = integrate.trapezoid(discretized_func, x = discretized_time)

        # integrand = lambda k: G_ch4(year - k) * self.E_nox(k)
        # result, _ = integrate.quad(integrand, 0, year, epsabs=1e-3, epsrel=1e-2)
        s_ch4 = np.interp(self.media_pesata_quote,self.Altitudes_for_forcing,self.s_o3l_data)
        # RF_ch4 = discretized_integral * 1e-13 * self.s_ch4(self.media_pesata_quote)
        RF_ch4 = discretized_integral * 1e-13 * s_ch4
        eff_ch4 = 1.18
        rf_ch4 = RF_ch4 * eff_ch4/self.RF_2CO2
        return rf_ch4
    

    def rf_o3l(self, year):

        # if self.media_pesata_quote is None:
        #     self.calculate_media_pesata_quote()

        def G_o3l(year):
            # qui G_o3l non ha le dimensioni corrette perchè manca un fattore 10^-13, che aggiungerò a valle
            # della convoluzione per diminuire il tempo d'esecuzione dell'integrale
            A = -1.21  # [moltiplicato per 10^-13 sarebbe (W/m^2)/kg(NOx)]
            tau = 12  # [anni]
            G_o3l = A*np.exp(-year/tau)
            return G_o3l
        
        discretized_time = np.linspace(0,year,100)

        discretized_func = [G_o3l(year - time) * self.E_nox(time) for time in discretized_time]

        discretized_integral = integrate.trapezoid(discretized_func, x = discretized_time)


        # integrand = lambda k: G_o3l(year - k) * self.E_nox(k)
        # result, _ = integrate.quad(integrand, 0, year, epsabs=1e-4, epsrel=1e-3)
        s_o3l = np.interp(self.media_pesata_quote,self.Altitudes_for_forcing,self.s_o3l_data)
        # RF_o3l = discretized_integral * 1e-13 * self.s_o3l(self.media_pesata_quote)
        RF_o3l = discretized_integral * 1e-13 * s_o3l
        eff_o3 = 1.37
        rf_o3l = RF_o3l * eff_o3/self.RF_2CO2

        

        return rf_o3l
    

    def rf_o3s(self,year):

        # if self.media_pesata_quote is None:
        #     self.calculate_media_pesata_quote()

        c_o3s = 1.01e-11 # [(w/m^2)/kg(NOx)]
        s_o3s = np.interp(self.media_pesata_quote,self.Altitudes_for_forcing,self.s_o3s_data)
        # RF_o3s = c_o3s * self.E_nox(year) * self.s_o3s(self.media_pesata_quote)
        RF_o3s = c_o3s * self.E_nox(year) * s_o3s
        eff_o3 = 1.37
        rf_o3s = RF_o3s * eff_o3/self.RF_2CO2

        return rf_o3s
    

    def rf_AIC(self,year):
        if ISA.atmosphere.Tstd(self.media_pesata_quote) < 235. :
            c_AIC = 2.21e-12
            s_AIC = np.interp(self.media_pesata_quote,self.Altitudes_for_forcing,self.s_aic_data)
            rf = s_AIC * c_AIC * self.aircraft.mission.profile.MissionRange * self.U(year) 
        else:
            rf = 0
        return rf



    def rf(self,year):
        rf = self.rf_co2(year) + self.rf_h2o(year) + self.rf_so4(year) + self.rf_soot(year) + self.rf_ch4(year) + self.rf_o3l(year) + self.rf_o3s(year) + self.rf_AIC(year)
        return rf    
    
    

    # DeltaT(t)

    def DeltaT(self,year):
            
        
        def Function(k, year):
            
            alpha = 2.246/36.8  # [K/yr]
            tau = 36.8  # [anni]
            G_T = alpha*np.exp(-(year - k)/tau)

            integrand = G_T * self.rf(k)
            return integrand



        # DeltaT, _ = integrate.quad(integrand, 0, year, epsabs=1e-8, epsrel=1e-3)   # [K]
        DeltaT, _ = integrate.quad(Function, 0, year, args=(year,),epsabs=1e-7, epsrel=1e-3)   # [K]

        # def integrand_1(k, year=year):
        #     return G_T(year - k) * self.rf(k)

        # def integrand_2(k, year=year):
        #     return G_T(year - k) * self.rf(k)

        # Y =  self.Y

        # DeltaT_1, _ = integrate.quad(integrand_1, 0, Y, epsabs=1e-8, epsrel=1e-3)

        # DeltaT_2, _ = integrate.quad(integrand_2, Y, year, epsabs=1e-8, epsrel=1e-3)
        
        # DeltaT = DeltaT_1 + DeltaT_2
        return DeltaT

    

    # ATR

    def ATR(self):   # [K]
        self.calculate_media_pesata_quote()
        integrand = lambda k: self.DeltaT(k)
        ATR, _ = integrate.quad(integrand, 0, self.H, epsabs=1e-2, epsrel=1e-1)   

        # print(ATR/self.H)

        return ATR/self.H