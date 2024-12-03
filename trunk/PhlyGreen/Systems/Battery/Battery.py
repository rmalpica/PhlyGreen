#import numpy as np
import math
import numbers
import numpy as np
import PhlyGreen.Systems.Battery.Cell_Models as Cell_Models
class Battery:
    def __init__(self, aircraft):
        self.aircraft = aircraft

        self.controller_Vmax = 740 
        self.controller_Vmin = 420 #this range of voltages should be defined in the model of the motor controller, but ill do that later, for now its hardcoded
        self.SOC_min = None
        self.SOC = 1
        self.it = 0
        self._i = 0
        self.Vout = None
        self.Voc = None
        self._T = None

    @property
    def i(self):
        return self._i

    @i.setter
    def i(self,value):
        self._i = value
        if value == None:
            raise ValueError(f'No real valued solution found for battery current.\nBattery underpowered.')
    
    @property
    def it(self):
        return self._it

    @it.setter
    def it(self,value):
        self._it = value
        _soc = 1-value/(self.capacity*self.P_number)
        if not ( self.SOC_min <= _value <= 1):
            raise ValueError(f'SOC outside of allowed range:\nSOC:{_soc} Range:{self.SOC_min} ~ 1')

    @property
    def T(self):
        return self._T

    @T.setter
    def T(self,value):
        self._T = value
        if value < 0 :
            raise ValueError(f'Battery temperature must be positive:\nTemperature:{value}')

    @property
    def SOC_min(self):
        if self._SOC_min == None:
            raise ValueError("Minimum SOC unset. Exiting")
        return self._SOC_min
      
    @SOC_min.setter
    def SOC_min(self,value):
        self._SOC_min = value
        if not (0 <= value <= 1):
            raise ValueError(f'Minimum SOC outside of allowed range:\nSOC:{value} Range:{0} ~ {1}')

    @property
    def cell_Vout(self) -> float:
        _value = self._voltageModel(self.T , self.cell_it , self.cell_i)
        if not ( self.Vmin <= _value <=  self.Vmax):
            raise ValueError(f'Cell voltage outside of allowed range:\nVoltage:{_value} Range:{self.Vmin} ~ {self.Vmax}')
        return _value

    @property
    def cell_Voc(self) -> float:
        return self._voltageModel(self.T , self.cell_it , 0)

    @property
    def Vout(self) -> float:
        _value = self.cell_Vout*self.S_number
        if not ( self.controller_Vmin <= _value <=  self.controller_Vmax):
            raise ValueError(f'Pack voltage outside of allowed range:\nVoltage:{_value} Range:{self.controller_Vmin} ~ {self.controller_Vmax}')
        return _value

    @property
    def Voc(self) -> float:
        return self.cell_Voc*self.S_number

    @property
    def cell_it(self) -> float:
        return self.it/self.P_number

    @property
    def cell_i(self) -> float:
        _value = self.i/self.P_number
        if _value > self.max_current:
            raise ValueError(f'Cell current outside of allowed range:\Current:{_value} Range:- ~ {self.max_current}')
        return _value

    @property
    def SOC(self) -> float:
        _value = 1-self.cell_it/self.capacity
        if not ( self.SOC_min <= _value <= 1):
            raise ValueError(f'SOC outside of allowed range:\nSOC:{_value} Range:{self.SOC_min} ~ 1')
        return _value

    @property
    def E0(self) -> float:
        return self.voltage_ctt + self.E_slope*(self.T-self.Tref)

    @property
    def Q(self) -> float:
        return self.capacity + self.Q_slope*(self.T-self.Tref)

    @property
    def K(self) -> float:
        return self.polarization_ctt * math.exp(self.K_arrhenius * (1/self.T - 1/self.Tref))

    @property
    def R(self) -> float:
        return self.resistance * math.exp(self.R_arrhenius * (1/self.T - 1/self.Tref))

# Thermal electric model of the voltage
    def _voltageModel(self,it,i):
        '''Model that determines the voltage from the present battery state.
           It receives i and it in order to be able to provide 
           peak voltage and open circuit voltage values at any desired state
        Receives: 
            - it - battery current integral, aka charge spent so far
            - i  - current draw from the battery
        Returns:
            - V - battery voltage output
        '''
        E0 , R , K , Q = self.E0 , self.R , self.K , self.Q
        A  , B  = self.exp_amplitude ,self.exp_time_ctt

        V = E0 -i*K*(Q/(Q-it)) -it*K*(Q/(Q-it)) +A*np.exp(-B * it) -i*R
        return V

# Set inputs from cell model chosen
    def SetInput(self):
        '''
        This gathers all the battery parameters from the cell_models.py file for the chosen battery.
        The chosen battery is read from the aircraft class and is defined by the user elsewhere
        the parameters are all input and some extra ones are calculated right away for later convenience
        '''
        cell = Cell_Models[self.aircraft.CellModel]
        # Get all parameters of the cell
        self.Tref              = 273.15+23 #self.cell['Reference Temperature']
        self.exp_amplitude     = cell['Exp Amplitude']                  # in volts
        self.exp_time_ctt      = cell['Exp Time constant']              # in Ah^-1 
        self.resistance        = cell['Internal Resistance']            # in ohms
        self.R_arrhenius       = cell['Resistance Arrhenius Constant']  # dimensionless
        self.polarization_ctt  = cell['Polarization Constant']          # in Volts over amp hour
        self.K_arrhenius       = cell['Polarization Arrhenius Constant']# dimensionless
        self.capacity          = cell['Cell Capacity']                  # in Ah
        self.Q_slope           = cell['Capacity Thermal Slope']         # in Ah per kelvin
        self.voltage_ctt       = cell['Voltage Constant']               # in volts
        self.E_slope           = cell['Voltage Thermal Slope']          # in volts per kelvin
        self.Vmax              = self.exp_amplitude + self.voltage_ctt  # in volts
        self.Vmin              = cell['Cell Voltage Min']               # in volts
        self.rate              = cell['Cell C rating']                  # dimensionless
        self.max_current       = self.rate * self.capacity              # in amperes
        self.cell_mass         = cell['Cell Mass']                      # in kg
        self.cell_radius       = cell['Cell Radius']                    # in m
        self.cell_height       = cell['Cell Height']                    # in m

        if not (self.Vmax > self.Vmin):
            raise ValueError("Illegal cell voltages: Vmax must be greater than Vmin")
        self.S_number = math.floor(self.controller_Vmax/self.cell_Vmax) #number of cells in series to achieve desired voltage. max voltage is preferred as it minimizes losses due to lower current being needed for a larger portion of the flight

#determine battery configuration
    #must receive the number of cells in parallel
    def Configure(self, parallel_cells):
        ''' WIP 
            Configures the battery for the chosen P number

        Inputs:
            - parallel_cells - the chosen P number
        '''
        self.P_number = parallel_cells
        self.cells_total = self.P_number * self.S_number

        # physical characteristics of the whole pack:
        self.stack_length = self.cell_radius * math.ceil(self.S_number/2)
        self.stack_width = self.cell_radius * (2 + np.sqrt(3))
        self.pack_volume = self.cell_height * self.stack_width * self.stack_length
        self.pack_weight = self.cell_mass * self.cells_total

        self.pack_config=f'S{self.S_number} P{self.P_number}'

    def Power_2_current(self, P):
        ''' Calculates the current output from the battery.
            The calculations are for a single cell, as that
            is what the model is made for. The output is
            the current for the entire battery pack however.
            The power is simply divided by the total number of
            cells, as every cell delivers equal power regardless
            of the configuration of the battery.

        Receives:
            P - power demanded from the battery
        Returns:
            I_out - current output from the battery
        '''

        if P == 0: #skips all the math if power is zero
            return 0

        ''' V = E0 - I*R - I*K*(Q/(Q-it)) - it*K*(Q/(Q-it)) + A*exp(-B * it)
            V = E0 - I*R - I*Qr - it*Qr + ee <- with substitutions to make shorter
            P = V*I = E0*I - I^2*R - I^2*Qr - I*it*Qr + I*ee 
            P = I^2 *(-R-Qr) + I *(E0+ee-it*Qr)
            quadratic solve: 
            a*I^2 + b*I - P = 0
        '''
        E0 , R , K , Q = self.E0 , self.R , self.K , self.Q
        A  , B  = self.exp_amplitude , self.exp_time_ctt
        it = self.cell_it
        P = P/self.cells_total #all cells deliver the same power

        Qr = K*Q/(Q-it)
        ee = A*np.exp(-B * it)
        a = (-R-Qr)
        b = (E0+ee-it*Qr)
        c = -P
        try:
            I_out = (-b+math.sqrt(b**2-4*a*c))/(2*a) # just the quadratic formula
        except Exception as err:
            print(err)
            I_out = None
        return I_out * self.P_number

    def heatLoss(self,Ta):
        '''WIP Simple differential equation describing a simplified lumped element thermal
        model of the cells
        Receives: 
            - Ta - temperature of the ambient cooling air
        Returns:
            - dTdt - battery temperature derivative
            - P    - dissipated waste power per cell
        '''
        V , Voc  = self.cell_Vout , self.cell_Voc
        i , it   = self.cell_i    , self.cell_it
        T , dEdT = self.T         , self.E_slope

        P = (Voc-V)*i + dEdT*i*T
        tc = 4880
        Rth = 0.629
        Cth = tc/Rth
        dTdt = P/Cth + (Ta - T)/(Rth*Cth) 
        return dTdt,P
