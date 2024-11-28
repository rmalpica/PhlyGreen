#import numpy as np
import math
import numbers
import numpy as np
import PhlyGreen.Systems.Battery.Cell_Models as Cell_Models
class Battery:
    def __init__(self, aircraft):
        self.aircraft = aircraft
        self._cell_rate = None  # Initialize private variables for all properties
        self._cell_exp_amplitude = None
        self._cell_exp_time_ctt = None
        self._cell_resistance = None
        self._cell_R_arrhenius = None
        self._cell_polarization_ctt = None
        self._cell_K_arrhenius = None
        self._cell_capacity = None
        self._cell_Q_slope = None
        self._cell_voltage_ctt = None
        self._cell_E_slope = None
        self._cell_Vmax = None
        self._cell_Vmin = None
        self._cell_current = None
        self._cell_mass = None
        self._cell_radius = None
        self._cell_height = None
        self.controller_Vmax = 740 
        self.controller_Vmin = 420 #this range of voltages should be defined in the model of the motor controller, but ill do that later, for now its hardcoded

    def _validate_positive(self, value, name):
        """small function to make the setters and getters neater"""
        if not isinstance(value, numbers.Number) or value <= 0:
            raise ValueError(f"Error: Illegal {name}: {value}. Must be a positive number.")

### Properties

    @property
    def S_number(self):
        if self._S_number == None:
            raise ValueError("Initial S_number unset. Exiting")
        return self._S_number

    @S_number.setter
    def S_number(self,value):
        self._validate_positive(value, 'S_number')
        self._S_number = value


    @property
    def P_number(self):
        if self._P_number == None:
            raise ValueError("Initial P_number unset. Exiting")
        return self._P_number

    @P_number.setter
    def P_number(self,value):
        self._validate_positive(value, 'P_number')
        self._P_number = value

    @property
    def cell_rate(self):
        if self._cell_rate is None:
            raise ValueError("Initial cell_rate unset. Exiting")
        return self._cell_rate

    @cell_rate.setter
    def cell_rate(self, value):
        self._validate_positive(value, 'cell_rate')
        self._cell_rate = value

    # Repeat the pattern for each property
    @property
    def cell_exp_amplitude(self):
        if self._cell_exp_amplitude is None:
            raise ValueError("Initial cell_exp_amplitude unset. Exiting")
        return self._cell_exp_amplitude

    @cell_exp_amplitude.setter
    def cell_exp_amplitude(self, value):
        self._validate_positive(value, 'cell_exp_amplitude')
        self._cell_exp_amplitude = value

    @property
    def cell_exp_time_ctt(self):
        if self._cell_exp_time_ctt is None:
            raise ValueError("Initial cell_exp_time_ctt unset. Exiting")
        return self._cell_exp_time_ctt

    @cell_exp_time_ctt.setter
    def cell_exp_time_ctt(self, value):
        self._validate_positive(value, 'cell_exp_time_ctt')
        self._cell_exp_time_ctt = value

    @property
    def cell_resistance(self):
        if self._cell_resistance is None:
            raise ValueError("Initial cell_resistance unset. Exiting")
        return self._cell_resistance

    @cell_resistance.setter
    def cell_resistance(self, value):
        self._validate_positive(value, 'cell_resistance')
        self._cell_resistance = value

    @property
    def cell_R_arrhenius(self):
        if self._cell_R_arrhenius is None:
            raise ValueError("Initial cell_R_arrhenius unset. Exiting")
        return self._cell_R_arrhenius

    @cell_R_arrhenius.setter
    def cell_R_arrhenius(self, value):
        self._validate_positive(value, 'cell_R_arrhenius')
        self._cell_R_arrhenius = value

    @property
    def cell_polarization_ctt(self):
        if self._cell_polarization_ctt is None:
            raise ValueError("Initial cell_polarization_ctt unset. Exiting")
        return self._cell_polarization_ctt

    @cell_polarization_ctt.setter
    def cell_polarization_ctt(self, value):
        self._validate_positive(value, 'cell_polarization_ctt')
        self._cell_polarization_ctt = value

    @property
    def cell_K_arrhenius(self):
        if self._cell_K_arrhenius is None:
            raise ValueError("Initial cell_K_arrhenius unset. Exiting")
        return self._cell_K_arrhenius

    @cell_K_arrhenius.setter
    def cell_K_arrhenius(self, value):
        self._validate_positive(value, 'cell_K_arrhenius')
        self._cell_K_arrhenius = value

    @property
    def cell_capacity(self):
        if self._cell_capacity is None:
            raise ValueError("Initial cell_capacity unset. Exiting")
        return self._cell_capacity

    @cell_capacity.setter
    def cell_capacity(self, value):
        self._validate_positive(value, 'cell_capacity')
        self._cell_capacity = value

    @property
    def cell_Q_slope(self):
        if self._cell_Q_slope is None:
            raise ValueError("Initial cell_Q_slope unset. Exiting")
        return self._cell_Q_slope

    @cell_Q_slope.setter
    def cell_Q_slope(self, value):
        self._validate_positive(value, 'cell_Q_slope')
        self._cell_Q_slope = value

    @property
    def cell_voltage_ctt(self):
        if self._cell_voltage_ctt is None:
            raise ValueError("Initial cell_voltage_ctt unset. Exiting")
        return self._cell_voltage_ctt

    @cell_voltage_ctt.setter
    def cell_voltage_ctt(self, value):
        self._validate_positive(value, 'cell_voltage_ctt')
        self._cell_voltage_ctt = value

    @property
    def cell_E_slope(self):
        if self._cell_E_slope is None:
            raise ValueError("Initial cell_E_slope unset. Exiting")
        return self._cell_E_slope

    @cell_E_slope.setter
    def cell_E_slope(self, value):
        self._validate_positive(value, 'cell_E_slope')
        self._cell_E_slope = value

    @property
    def cell_mass(self):
        if self._cell_mass is None:
            raise ValueError("Initial cell_mass unset. Exiting")
        return self._cell_mass

    @cell_mass.setter
    def cell_mass(self, value):
        self._validate_positive(value, 'cell_mass')
        self._cell_mass = value

    @property
    def cell_radius(self):
        if self._cell_radius is None:
            raise ValueError("Initial cell_radius unset. Exiting")
        return self._cell_radius

    @cell_radius.setter
    def cell_radius(self, value):
        self._validate_positive(value, 'cell_radius')
        self._cell_radius = value

    @property
    def cell_height(self):
        if self._cell_height is None:
            raise ValueError("Initial cell_height unset. Exiting")
        return self._cell_height

    @cell_height.setter
    def cell_height(self, value):
        self._validate_positive(value, 'cell_height')
        self._cell_height = value


# Set inputs from cell model chosen
    def SetInput(self):
        '''
        This gathers all the battery parameters from the cell_models.py file for the chosen battery.
        The chosen battery is read from the aircraft class and is defined by the user elsewhere
        the parameters are all input and some extra ones are calculated right away for later convenience
        '''
        # Get the cell model from the aircraft class
        self.cell_model = Cell_Models[self.aircraft.CellModel]

        # Get all parameters of the battery
        self.cell_exp_amplitude     = self.cell_model['Exp Amplitude']                  # in volts
        self.cell_exp_time_ctt      = self.cell_model['Exp Time constant']              # in Ah^-1 
        self.cell_resistance        = self.cell_model['Internal Resistance']            # in ohms
        self.cell_R_arrhenius       = self.cell_model['Resistance Arrhenius Constant']  # dimensionless
        self.cell_polarization_ctt  = self.cell_model['Polarization Constant']          # in Volts over amp hour
        self.cell_K_arrhenius       = self.cell_model['Polarization Arrhenius Constant']# dimensionless
        self.cell_capacity          = self.cell_model['Cell Capacity']                  # in Ah
        self.cell_Q_slope           = self.cell_model['Capacity Thermal Slope']         # in UNCLEAR per kelvin
        self.cell_voltage_ctt       = self.cell_model['Voltage Constant']               # in volts
        self.cell_E_slope           = self.cell_model['Voltage Thermal Slope']          # in volts per kelvin
        self.cell_Vmax              = self.cell_exp_amplitude + self.cell_voltage_ctt   # in volts
        self.cell_Vmin              = self.cell_model['Cell Voltage Min']               # in volts
        self.cell_current           = self.cell_rate * self.cell_capacity               # in amperes
        self.cell_mass              = self.cell_model['Cell Mass']                      # in kg
        self.cell_radius            = self.cell_model['Cell Radius']                    # in m
        self.cell_height            = self.cell_model['Cell Height']                    # in m

        if not (self.cell_Vmax > self.cell_Vmin):
            raise ValueError("Illegal cell voltages: Vmax must be greater than Vmin")

        self.cell_charge = 3600*self.cell_capacity #convert the capacity from Ah to Coulomb to keep everything SI
        self.cell_energy = self.cell_charge*self.cell_Vnom # cell capacity in joules
        self.S_number = math.floor(self.controller_Vmax/self.cell_Vmax) #number of cells in series to achieve desired voltage. max voltage is preferred as it minimizes losses due to lower current being needed for a larger portion of the flight
        ####################################################################
        ####################################################################
        ### NEEDS TO COME FROM AN INPUT SOMEWHERE, SHOULDNT BE HARDCODED ###
        ### thermal stuff for the thermal calculations:

        self.cell_heat_capacity= 1130 #joule kelvin kg


#determine battery configuration
    #must receive the number of cells in parallel
    def Configure(self, parallel_cells):

        self.P_number=parallel_cells
        self.cells_total = self.P_number * self.S_number

        self.pack_charge = self.P_number * self.cell_charge
        self.pack_energy = self.cells_total * self.cell_energy
        self.pack_resistance = self.cell_resistance * self.S_number / self.P_number

        # empirical constants scaled for the whole pack:
        self.pack_polarization_ctt     = self.cell_polarization_ctt * self.S_number / self.P_number
        self.pack_exponential_amplitude     = self.cell_exponential_amplitude * self.S_number
        self.pack_exponential_time_ctt = self.cell_exponential_time_ctt * self.P_number
        self.pack_voltage_ctt          = self.cell_voltage_ctt * self.S_number

        # relevant pack voltages:
        self.pack_Vmax = self.cell_Vmax * self.S_number
        self.pack_Vmin = self.cell_Vmin * self.S_number
        self.pack_Vnom = self.cell_Vnom * self.S_number

        # peak current that can be delivered safely from the pack
        self.pack_current = self.cell_current * self.P_number 

        #max power that can be delivered at 100% SOC and peak current:
        self.pack_power_max = self.pack_current * self.Nrg_n_Curr_2_Volt(0,self.pack_current) 

        # physical characteristics of the whole pack:
        self.stack_length = self.cell_radius * math.ceil(self.S_number/2)
        self.stack_width = self.cell_radius * (2 + np.sqrt(3))
        self.pack_volume = self.cell_height * self.stack_width * self.stack_length
        self.pack_weight = self.cell_mass*self.cells_total

        self.pack_config=f'S{self.S_number} P{self.P_number}'


    def Nrg_n_Curr_2_Volt(self, it, i):
        '''Converts the current being drawn + the current
           spent so far into an output voltage'''
        E0 = self.pack_voltage_ctt
        R  = self.pack_resistance
        A  = self.pack_exponential_amplitude
        B  = self.pack_exponential_time_ctt
        K  = self.pack_polarization_ctt
        Q  = self.pack_charge

        return (E0 -i*R -i*K*(Q/(Q-it)) -it*K*(Q/(Q-it)) +A*np.exp(-B * it))

    def Power_2_V_A(self, it, P):
        '''Receives: 
              it - charge spent from the battery over time, the integral of the current
              P  - power demanded from the battery
           Returns:
              U_out - voltage at the battery terminals
              I_out - current output from the battery
        '''

        if P == 0: #skips all the math if power is zero
            I_out = 0
            U_out = self.Nrg_n_Curr_2_Volt( it, I_out)

        else:
            ''' V = E0 - i*R - i*K*(Q/(Q-it)) - it*K*(Q/(Q-it)) + A*exp(-B * it)
                V = E0 - I*R - I*Qr - it*Qr + ee <- with substitutions to make shorter
                P = V*I = E0*I - I^2*R - I^2*Qr - I*it*Qr + I*ee 
                P = I^2 *(-R-Qr) + I *(E0+ee-it*Qr)
                quadratic solve: 
                a*I^2 + b*I - P = 0
            '''
            E0 = self.pack_voltage_ctt
            R  = self.pack_resistance
            A  = self.pack_exponential_amplitude
            B  = self.pack_exponential_time_ctt
            K  = self.pack_polarization_ctt
            Q  = self.pack_charge
            Qr = K*Q/(Q-it)
            ee = A*np.exp(-B * it)
            a = (-R-Qr)
            b = (E0+ee-it*Qr)
            c = -P
            try:
                I_out = (-b+math.sqrt(b**2-4*a*c))/(2*a) # just the quadratic formula
                U_out = self.Nrg_n_Curr_2_Volt(it, I_out)
            except Exception as err:
                print(err)
                I_out = None
                U_out = None
        return U_out, I_out
