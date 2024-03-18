import os
import numpy as np
import numbers
import scipy.integrate as integrate
import joblib
from sklearn.preprocessing import PolynomialFeatures
import matplotlib.pyplot as plt



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
        if year >= 0 and year <= self.Y:
            U = self.N
        else:
            U = 0
        return U



    # EMISSIONI ANNUALI

    def calculate_mission_emissions(self):
        Wf = self.aircraft.weight.Wf  # [kg]
        
        # CO2
        EI_co2 = 3.16 # [kg/kg]
        self.mission_emissions['co2'] = EI_co2*Wf

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
                    return 0  # da completare
                if self.EINOx_model == 'GasTurb':
                    times = np.array([])
                    beta = np.array([])
                    for array in self.aircraft.mission.integral_solution:
                        times = np.concatenate([times, array.t])
                        beta = np.concatenate([beta, array.y[1]])
                    
                    v0 = self.aircraft.mission.profile.Velocity(times)  # [m/s]
                    alt = self.aircraft.mission.profile.Altitude(times)  # [m]
                    pwsd = np.zeros(len(times))  # [kW]
                    EI_NOx = np.zeros(len(times))  # [g/kg(fuel)]
                    portata = np.zeros(len(times))  # [kg(fuel)/s]
                    
                    # power = np.zeros(len(times))
                    # rend = np.zeros(len(times))
                    # PowerExcess = np.zeros(len(times))

                    for t in range(len(times)):
                        power = (self.aircraft.weight.WTO) * self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,beta[t],self.aircraft.mission.profile.PowerExcess(times[t]),1,alt[t],self.aircraft.mission.DISA,v0[t],'TAS')
                        pwsd[t]= 1e-3*0.5*self.aircraft.powertrain.EtaPPmodel(alt[t],v0[t],power)*power

                        # power[t] = (self.aircraft.weight.WTO) * self.aircraft.performance.PoWTO(self.aircraft.DesignWTOoS,beta[t],self.aircraft.mission.profile.PowerExcess(times[t]),1,alt[t],self.aircraft.mission.DISA,v0[t],'TAS')
                        # pwsd[t]= 1e-3*0.5*self.aircraft.powertrain.EtaPPmodel(alt[t],v0[t],power[t])*power[t]
                        # rend[t] = self.aircraft.powertrain.EtaPPmodel(alt[t],v0[t],power[t])
                        # PowerExcess[t] = self.aircraft.mission.profile.PowerExcess(times[t])

                        data_for_prediction = np.array([[pwsd[t], v0[t], alt[t]]])
                        poly_features = PolynomialFeatures(degree=4)
                        data_for_prediction_poly = poly_features.fit_transform(data_for_prediction)
                        EI_NOx[t] = self.model.predict(data_for_prediction_poly)[0]

                        PRatio = self.aircraft.powertrain.Traditional(alt[t],v0[t],power)
                        portata[t] = power * PRatio[0]/self.aircraft.weight.ef
                        
                        # PRatio = self.aircraft.powertrain.Traditional(alt[t],v0[t],power[t])
                        # portata[t] = power[t] * PRatio[0]/self.aircraft.weight.ef

                    # plt.figure(1)
                    # plt.plot(times/60, power, 'b')
                    # plt.grid(visible=True)
                    # plt.xlabel('t [min]')
                    # plt.ylabel('power')
                    # plt.show()

                    # plt.figure(2)
                    # plt.plot(times/60, PowerExcess, 'b')
                    # plt.grid(visible=True)
                    # plt.xlabel('t [min]')
                    # plt.ylabel('Power Excess')
                    # plt.show()


                    # print(self.aircraft.weight.WTO)
                    # print(self.aircraft.DesignWTOoS)
                    # print(self.aircraft.mission.DISA)

                    integranda = portata*EI_NOx
                    massa_di_NOx = integrate.cumtrapz(integranda, times, initial=0.0)
                    # l'elemento n-esimo del vettore massa_di_NOx è l'integrale definito dell'integranda tra t = 0 e t = times[n]
                    E_nox_1m = massa_di_NOx[-1]

                
                    return E_nox_1m* 10**(-3)
                
        self.mission_emissions['nox'] = E_nox_1m()

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

        if self.frazioni_di_missione is None:
            self.calculate_frazioni_di_missione()
        
        media_pesata_quote = 0
        for i in range(len(self.frazioni_di_missione[0])):
            media_pesata_quote = media_pesata_quote + self.frazioni_di_missione[0][i]*self.frazioni_di_missione[1][i]
        media_pesata_quote = media_pesata_quote/sum(self.frazioni_di_missione[1])

        self.media_pesata_quote = media_pesata_quote

        

    def calculate_r_ch4_o3l_o3s(self):
        IntervalliQuote = np.array([0, 5.6, 6.3, 6.9, 7.5, 8.1, 8.7, 9.3, 9.9, 10.5, 11.1, 11.7, 12.4, 13.0, 13.6, 14.2])*10**3  # [m]
        r_ch4 = np.array([-29.4, -31.3, -32.5, -32.7, -32.1, -31.6, -31.5, -31.9, -33.1, -38.5, -41.4, -26.9, -29.8, -27.8, -29.5, -39.0])
        r_o3l = r_ch4*0.59
        r_o3s = np.array([25.4, 30.1, 33.5, 38.4, 38.5, 43.7, 50.3, 54.5, 61.1, 77.3, 88.0, 64.1, 76.6, 59.6, 90.1, 174.6])
        # le dimensioni degli elementi di r_ch4, r_o3l e r_o3s sono (mW/m^2)/(Tg(N)/yr)

        r_ch4_o3l_o3s = np.stack((IntervalliQuote, r_ch4, r_o3l, r_o3s))
        self.r_ch4_o3l_o3s = r_ch4_o3l_o3s

      

    # NB: gli r_i sono quelli che in "impatto climatico_Delft.pdf" sono chiamati RF_i/E_NOx
        
    def s_ch4(self,h):

        if self.r_ch4_o3l_o3s is None:
            self.calculate_r_ch4_o3l_o3s()
        r_ch4_o3l_o3s = self.r_ch4_o3l_o3s

        if self.frazioni_di_missione is None:
            self.calculate_frazioni_di_missione()
        frazioni_di_missione = self.frazioni_di_missione

        denominatore = 0
        for i in range(len(frazioni_di_missione[0])):
            index = np.searchsorted(r_ch4_o3l_o3s[0], frazioni_di_missione[0][i], side='right')
            denominatore = denominatore + frazioni_di_missione[1][i] * r_ch4_o3l_o3s[1][index - 1]
        
        index_h = np.searchsorted(r_ch4_o3l_o3s[0], h, side='right')
        s = r_ch4_o3l_o3s[1][index_h - 1]*sum(frazioni_di_missione[1])/denominatore

        return s
    

    def s_o3l(self,h):

        if self.r_ch4_o3l_o3s is None:
            self.calculate_r_ch4_o3l_o3s()
        r_ch4_o3l_o3s = self.r_ch4_o3l_o3s

        if self.frazioni_di_missione is None:
            self.calculate_frazioni_di_missione()
        frazioni_di_missione = self.frazioni_di_missione

        denominatore = 0
        for i in range(len(frazioni_di_missione[0])):
            index = np.searchsorted(r_ch4_o3l_o3s[0], frazioni_di_missione[0][i], side='right')
            denominatore = denominatore + frazioni_di_missione[1][i] * r_ch4_o3l_o3s[2][index - 1]
        
        index_h = np.searchsorted(r_ch4_o3l_o3s[0], h, side='right')
        s = r_ch4_o3l_o3s[2][index_h - 1]*sum(frazioni_di_missione[1])/denominatore

        return s
    

    def s_o3s(self,h):

        if self.r_ch4_o3l_o3s is None:
            self.calculate_r_ch4_o3l_o3s()
        r_ch4_o3l_o3s = self.r_ch4_o3l_o3s

        if self.frazioni_di_missione is None:
            self.calculate_frazioni_di_missione()
        frazioni_di_missione = self.frazioni_di_missione

        denominatore = 0
        for i in range(len(frazioni_di_missione[0])):
            index = np.searchsorted(r_ch4_o3l_o3s[0], frazioni_di_missione[0][i], side='right')
            denominatore = denominatore + frazioni_di_missione[1][i] * r_ch4_o3l_o3s[3][index - 1]
        
        index_h = np.searchsorted(r_ch4_o3l_o3s[0], h, side='right')
        s = r_ch4_o3l_o3s[3][index_h - 1]*sum(frazioni_di_missione[1])/denominatore

        return s

        


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
        
        def DeltaXCO2(year):
            
            integrand = lambda k: G_xco2(year - k) * self.E_co2(k)
            result, _ = integrate.quad(integrand, 0, year, epsabs=1e-4, epsrel=1e-3)
            return result*10**(-12)
        
        XCO2_0 = 380 # concentrazione di background [ppmv]
        rf_co2 = np.log((XCO2_0 + DeltaXCO2(year))/XCO2_0)/np.log(2)

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

        if self.media_pesata_quote is None:
            self.calculate_media_pesata_quote()

        def G_ch4(year):
            # qui G_ch4 non ha le dimensioni corrette perchè manca un fattore 10^-13, che aggiungerò a valle
            # della convoluzione per diminuire il tempo d'esecuzione dell'integrale
            A = -5.16  # [moltiplicato per 10^-13 sarebbe (W/m^2)/kg(NOx)]
            tau = 12  # [anni]
            G_ch4 = A*np.exp(-year/tau)
            return G_ch4
        
        integrand = lambda k: G_ch4(year - k) * self.E_nox(k)
        result, _ = integrate.quad(integrand, 0, year, epsabs=1e-4, epsrel=1e-3)
        RF_ch4 = result * 10**(-13) * self.s_ch4(self.media_pesata_quote)
        eff_ch4 = 1.18
        rf_ch4 = RF_ch4 * eff_ch4/self.RF_2CO2
        return rf_ch4
    

    def rf_o3l(self, year):

        if self.media_pesata_quote is None:
            self.calculate_media_pesata_quote()

        def G_o3l(year):
            # qui G_o3l non ha le dimensioni corrette perchè manca un fattore 10^-13, che aggiungerò a valle
            # della convoluzione per diminuire il tempo d'esecuzione dell'integrale
            A = -1.21  # [moltiplicato per 10^-13 sarebbe (W/m^2)/kg(NOx)]
            tau = 12  # [anni]
            G_o3l = A*np.exp(-year/tau)
            return G_o3l
        
        integrand = lambda k: G_o3l(year - k) * self.E_nox(k)
        result, _ = integrate.quad(integrand, 0, year, epsabs=1e-4, epsrel=1e-3)
        RF_o3l = result * 10**(-13) * self.s_o3l(self.media_pesata_quote)
        eff_o3 = 1.37
        rf_o3l = RF_o3l * eff_o3/self.RF_2CO2
        return rf_o3l
    

    def rf_o3s(self,year):

        if self.media_pesata_quote is None:
            self.calculate_media_pesata_quote()

        c_o3s = 1.01e-11 # [(w/m^2)/kg(NOx)]
        RF_o3s = c_o3s * self.E_nox(year) * self.s_o3s(self.media_pesata_quote)
        eff_o3 = 1.37
        rf_o3s = RF_o3s * eff_o3/self.RF_2CO2

        return rf_o3s
    

    def rf(self,year):
        rf = self.rf_co2(year) + self.rf_h2o(year) + self.rf_so4(year) + self.rf_soot(year) + self.rf_ch4(year) + self.rf_o3l(year) + self.rf_o3s(year)
        return rf    
    
    

    # DeltaT(t)

    def DeltaT(self,year):
        def G_T(year):
            
            alpha = 2.246/36.8  # [K/yr]
            tau = 36.8  # [anni]
            G_T = alpha*np.exp(-year/tau)
            return G_T
        
        integrand = lambda k, year=year: G_T(year - k) * self.rf(k) 
        
        DeltaT, _ = integrate.quad(integrand, 0, year, epsabs=1e-8, epsrel=1e-3)   # [K]
        return DeltaT

    

    # ATR

    def ATR(self):   # [K]
        integrand = lambda k: self.DeltaT(k)
        ATR, _ = integrate.quad(integrand, 0, self.H, epsabs=1e-4, epsrel=1e-3)   
        
        return ATR/self.H