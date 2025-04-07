import os
import numpy as np
import numbers
import scipy.integrate as integrate
import joblib
from sklearn.preprocessing import PolynomialFeatures
import matplotlib.pyplot as plt
import statistics
import PhlyGreen.Utilities.Atmosphere as ISA


class ClimateImpact:
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
    

    """ Properties """

    @property
    def EINOx_model(self):
        return self._EINOx_model
          
    @EINOx_model.setter
    def EINOx_model(self,value):
        if value == 'GasTurb' or value == 'Filippone' or value == 'unset':
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
        required_keys = {'H', 'N', 'Y', 'EINOx_model'}
        if required_keys.issubset(self.aircraft.ClimateImpactInput.keys()):
            self.H = self.aircraft.ClimateImpactInput.get("H")
            self.N = self.aircraft.ClimateImpactInput.get("N")
            self.Y = self.aircraft.ClimateImpactInput.get("Y")
            self.Grid_CO2 = self.aircraft.ClimateImpactInput.get("Grid_CO2")
            self.WTW_CO2 = self.aircraft.ClimateImpactInput.get("WTW_CO2")
            self.EINOx_model = self.aircraft.ClimateImpactInput.get("EINOx_model")
            if self.EINOx_model == 'GasTurb':
                file_path = os.path.join(os.path.dirname(__file__), 'EINOx_gasturb.joblib')
                self.model = joblib.load(file_path)
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

    def calculate_mission_emissions(self):
        Wf = self.aircraft.weight.Wf  # [kg]
        
        # CO2
        EI_co2 = 3.16 # [kg/kg]
        self.mission_emissions['co2'] = EI_co2*Wf + self.WTW_CO2*43.5*Wf
        if self.aircraft.Configuration == 'Hybrid':
            SourceBattery = self.aircraft.weight.TotalEnergies[1] * 1e-6 / self.aircraft.welltowake.EtaSourceToBattery
            self.mission_emissions['co2'] += self.Grid_CO2*SourceBattery


        # H2O
        EI_h2o = 1.26 # [kg/kg]
        self.mission_emissions['h2o'] = EI_h2o*Wf

        # SO4
        EI_so4 = 2e-4 # [kg/kg]
        self.mission_emissions['so4'] = EI_so4*Wf

        # SOOT
        EI_soot = 4e-5 # [kg/kg]
        self.mission_emissions['soot'] = EI_soot*Wf

        # NOX
        def E_nox_1m():  # emissione di NOx in kg della singola missione
                
                if self.EINOx_model == 'Filippone':
                    times = np.array([])
                    beta = np.array([])
                    for array in self.aircraft.mission.integral_solution:
                        times = np.concatenate([times, array.t])
                        if self.aircraft.Configuration == 'Traditional':
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
                    coeff = np.array([
                        [0.7194e+1, 0.5609e+0, -0.1059e-1, -0.3223e+1, 0.2889e+0, 0.2591e+0],
                        [0.1605e+0, 0.2412e+0, -0.1650e-2, -0.8818e+1, 0.3714e+2, -0.2268e+0],
                        [ 0.3699e+0, 0.5470e+0, -0.7445e-2, -0.6914e+1, 0.6782e+1, 0.1138e+0]
                    ])
                    # coeff sono i coefficienti del metodo di Filippone per climbout, idle e approach

                    EI_NOx = np.zeros(len(times))  # [g/kg(fuel)]
                    OPR = 15.77
                

                    for t in range(len(times)):
                        power = (self.aircraft.weight.WTO) * self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,beta[t],self.aircraft.mission.profile.PowerExcess(times[t]),1,alt[t],self.aircraft.mission.DISA,v0[t],'TAS')
                        if self.aircraft.Configuration == 'Traditional':
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

                        mfuel = 0.5*portata[t]  # portata di combustibile del singolo motore
                        
                    

                        EI_NOx[t] =  2*(c[0] + c[1]*OPR + c[2]*(OPR)**2 + c[3]*mfuel + c[4]*(mfuel)**2 + c[5]*OPR*mfuel)


                    # plt.figure(2)
                    # plt.plot(times/60, EI_NOx, 'b')
                    # plt.grid(visible=True)
                    # plt.xlabel('t [min]')
                    # plt.ylabel('EI_NOx [g/kg(fuel)]')
                    # plt.show()    

                    integranda = portata*EI_NOx
                    massa_di_NOx = integrate.cumtrapz(integranda, times, initial=0.0)
                    # l'elemento n-esimo del vettore massa_di_NOx è l'integrale definito dell'integranda tra t = 0 e t = times[n]
                    E_nox_1m = massa_di_NOx[-1]

                
                    return E_nox_1m* 10**(-3)
                    
                
                
                if self.EINOx_model == 'GasTurb':
                    times = np.array([])
                    beta = np.array([])
                    for array in self.aircraft.mission.integral_solution:
                        times = np.concatenate([times, array.t])
                        if self.aircraft.Configuration == 'Traditional':
                            beta = np.concatenate([beta, array.y[1]])
                        elif self.aircraft.Configuration == 'Hybrid':
                            beta = np.concatenate([beta, array.y[2]])  

                    v0 = self.aircraft.mission.profile.Velocity(times)  # [m/s]
                    alt = self.aircraft.mission.profile.Altitude(times)  # [m]
                    if self.aircraft.Configuration == 'Hybrid':
                        spr = [self.aircraft.mission.profile.SuppliedPowerRatio(t) for t in times]

                    pwsd = np.zeros(len(times))  # [kW]
                    EI_NOx = np.zeros(len(times))  # [g/kg(fuel)]
                    portata = np.zeros(len(times))  # [kg(fuel)/s]
                    

                    for t in range(len(times)):
                        power = (self.aircraft.weight.WTO) * self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,beta[t],self.aircraft.mission.profile.PowerExcess(times[t]),1,alt[t],self.aircraft.mission.DISA,v0[t],'TAS')
                        pwsd[t]= 1e-3*0.5*self.aircraft.powertrain.EtaPPmodel(alt[t],v0[t],power)*power

                        data_for_prediction = np.array([[pwsd[t], v0[t], alt[t]]])
                        poly_features = PolynomialFeatures(degree=4)
                        data_for_prediction_poly = poly_features.fit_transform(data_for_prediction)
                        EI_NOx[t] = self.model.predict(data_for_prediction_poly)[0]

                    
                        if self.aircraft.Configuration == 'Traditional':
                            PRatio = self.aircraft.powertrain.Traditional(alt[t],v0[t],power) 
                        elif self.aircraft.Configuration == 'Hybrid':
                            PRatio = self.aircraft.powertrain.Hybrid(spr[t],alt[t],v0[t],power)
                        portata[t] = power * PRatio[0]/self.aircraft.weight.ef

                    integranda = portata*EI_NOx
                    massa_di_NOx = integrate.cumtrapz(integranda, times, initial=0.0)
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
                    coeff = np.array([
                        [0.7194e+1, 0.5609e+0, -0.1059e-1, -0.3223e+1, 0.2889e+0, 0.2591e+0],
                        [0.1605e+0, 0.2412e+0, -0.1650e-2, -0.8818e+1, 0.3714e+2, -0.2268e+0],
                        [ 0.3699e+0, 0.5470e+0, -0.7445e-2, -0.6914e+1, 0.6782e+1, 0.1138e+0]
                    ])
                    # coeff sono i coefficienti del metodo di Filippone per climbout, idle e approach

                    EI_NOx = np.zeros(len(times))  # [g/kg(fuel)]
                    OPR = 15.77
                

                    for t in range(len(times)):
                        power = (self.aircraft.weight.WTO) * self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,beta[t],self.aircraft.mission.profile.DiscretizedPowerExcess[t],1,alt[t],self.aircraft.mission.DISA,v0[t],'TAS')
                        if self.aircraft.Configuration == 'Traditional':
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

                        mfuel = 0.5*portata[t]  # portata di combustibile del singolo motore
                        
                        

                        EI_NOx[t] =  2*(c[0] + c[1]*OPR + c[2]*(OPR)**2 + c[3]*mfuel + c[4]*(mfuel)**2 + c[5]*OPR*mfuel)


                    # plt.figure(2)
                    # plt.plot(times/60, EI_NOx, 'b')
                    # plt.grid(visible=True)
                    # plt.xlabel('t [min]')
                    # plt.ylabel('EI_NOx [g/kg(fuel)]')
                    # plt.show()    

                    integranda = portata*EI_NOx
                    massa_di_NOx = integrate.cumtrapz(integranda, times, initial=0.0)
                    # l'elemento n-esimo del vettore massa_di_NOx è l'integrale definito dell'integranda tra t = 0 e t = times[n]
                    E_nox_1m = massa_di_NOx[-1]

                
                    return E_nox_1m* 10**(-3)
                    
                
                
                if self.EINOx_model == 'GasTurb':
                    beta = self.aircraft.mission.beta_values
                    times = self.aircraft.mission.profile.DiscretizedTime
                   

                    v0 = self.aircraft.mission.profile.DiscretizedVelocities  # [m/s]
                    alt = self.aircraft.mission.profile.DiscretizedAltitudes  # [m]

                    if self.aircraft.Configuration == 'Hybrid':
                        spr = [self.aircraft.mission.profile.SuppliedPowerRatio(t) for t in times]


                    pwsd = np.zeros(len(times))  # [kW]
                    EI_NOx = np.zeros(len(times))  # [g/kg(fuel)]
                    portata = np.zeros(len(times))  # [kg(fuel)/s]
                    

                    for t in range(len(times)):
                        power = (self.aircraft.weight.WTO) * self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,beta[t],self.aircraft.mission.profile.DiscretizedPowerExcess[t],1,alt[t],self.aircraft.mission.DISA,v0[t],'TAS')      
                        pwsd[t]= 1e-3*0.5*self.aircraft.powertrain.EtaPPmodel(alt[t],v0[t],power)*power

                        data_for_prediction = np.array([[pwsd[t], v0[t], alt[t]]])
                        poly_features = PolynomialFeatures(degree=4)
                        data_for_prediction_poly = poly_features.fit_transform(data_for_prediction)
                        EI_NOx[t] = self.model.predict(data_for_prediction_poly)[0]

                    
                        if self.aircraft.Configuration == 'Traditional':
                            PRatio = self.aircraft.powertrain.Traditional(alt[t],v0[t],power) 
                        elif self.aircraft.Configuration == 'Hybrid':
                            PRatio = self.aircraft.powertrain.Hybrid(spr[t],alt[t],v0[t],power)
                        portata[t] = power * PRatio[0]/self.aircraft.weight.ef

                    integranda = portata*EI_NOx
                    massa_di_NOx = integrate.cumtrapz(integranda, times, initial=0.0)
                    # l'elemento n-esimo del vettore massa_di_NOx è l'integrale definito dell'integranda tra t = 0 e t = times[n]
                    E_nox_1m = massa_di_NOx[-1]

                
                    return E_nox_1m* 10**(-3)



        if self.aircraft.MissionType == 'Continue':
            nox = E_nox_1m()
        elif self.aircraft.MissionType == 'Discrete': 
            nox = E_nox_1m_DISCRETO()  



        self.mission_emissions['nox'] = nox

        self.mission_emissions_calculated = True


        
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