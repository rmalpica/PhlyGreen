#import numpy as np
import math
import numbers
import numpy as np
import PhlyGreen.Systems.Battery.Cell_Models as Cell_Models
from scipy.optimize import brentq
class Battery:
    def __init__(self, aircraft):
        self.aircraft = aircraft
        self.controller_Vmax = 740 
        self.controller_Vmin = 420 #this range of voltages should be defined in the model of the motor controller, but ill do that later, for now its hardcoded


    """ Properties """

### pack energy
    @property
    def pack_energy(self):
        if self._pack_energy == None:
            raise ValueError("Initial pack_energy unset. Exiting")
        return self._pack_energy

    @pack_energy.setter
    def pack_energy(self,value):
        self._pack_energy = value
        if(not isinstance(value, numbers.Number) or (value <= 0 )):
            raise ValueError("Error: Illegal pack_energy: %e. Exiting" %value)

### S_number
    @property
    def S_number(self):
        if self._S_number == None:
            raise ValueError("Initial S_number unset. Exiting")
        return self._S_number

    @S_number.setter
    def S_number(self,value):
        self._S_number = value
        if(not isinstance(value, int) or (value <= 0 )):
            raise ValueError("Error: Illegal S_number: %e. Exiting" %value)

### P_number
    @property
    def P_number(self):
        if self._P_number == None:
            raise ValueError("Initial P_number unset. Exiting")
        return self._P_number

    @P_number.setter
    def P_number(self,value):
        self._P_number = value
        if(not isinstance(value, int) or (value <= 0 )):
            raise ValueError("Error: Illegal P_number: %e. Exiting" %value)

### cell_capacity
    @property
    def cell_capacity(self):
        if self._cell_capacity == None:
            raise ValueError("Initial cell_capacity unset. Exiting")
        return self._cell_capacity

    @cell_capacity.setter
    def cell_capacity(self,value):
        self._cell_capacity = value
        if(not isinstance(value, numbers.Number) or (value <= 0 )):
            raise ValueError("Error: Illegal cell_capacity: %e. Exiting" %value)

### cell_rate
    @property
    def cell_rate(self):
        if self._cell_rate == None:
            raise ValueError("Initial cell_rate unset. Exiting")
        return self._cell_rate

    @cell_rate.setter
    def cell_rate(self,value):
        self._cell_rate = value
        if(not isinstance(value, numbers.Number) or (value <= 0 )):
            raise ValueError("Error: Illegal cell_rate: %e. Exiting" %value)

### cell_Vmax
    @property
    def cell_Vmax(self):
        if self._cell_Vmax == None:
            raise ValueError("Initial cell_Vmax unset. Exiting")
        return self._cell_Vmax

    @cell_Vmax.setter
    def cell_Vmax(self,value):
        self._cell_Vmax = value
        if(not isinstance(value, numbers.Number) or (value <= 0 )):
            raise ValueError("Error: Illegal cell_Vmax: %e. Exiting" %value)

### cell_Vmin
    @property
    def cell_Vmin(self):
        if self._cell_Vmin == None:
            raise ValueError("Initial cell_Vmin unset. Exiting")
        return self._cell_Vmin

    @cell_Vmin.setter
    def cell_Vmin(self,value):
        self._cell_Vmin = value
        if(not isinstance(value, numbers.Number) or (value <= 0 )):
            raise ValueError("Error: Illegal cell_Vmin: %e. Exiting" %value)

### cell_Vnom
    @property
    def cell_Vnom(self):
        if self._cell_Vnom == None:
            raise ValueError("Initial cell_Vnom unset. Exiting")
        return self._cell_Vnom

    @cell_Vnom.setter
    def cell_Vnom(self,value):
        self._cell_Vnom = value
        if(not isinstance(value, numbers.Number) or (value <= 0 )):
            raise ValueError("Error: Illegal cell_Vnom: %e. Exiting" %value)

### cell_mass
    @property
    def cell_mass(self):
        if self._cell_mass == None:
            raise ValueError("Initial cell_mass unset. Exiting")
        return self._cell_mass

    @cell_mass.setter
    def cell_mass(self,value):
        self._cell_mass = value
        if(not isinstance(value, numbers.Number) or (value <= 0 )):
            raise ValueError("Error: Illegal cell_mass: %e. Exiting" %value)

### cell_volume
    @property
    def cell_volume(self):
        if self._cell_volume == None:
            raise ValueError("Initial cell_volume unset. Exiting")
        return self._cell_volume

    @cell_volume.setter
    def cell_volume(self,value):
        self._cell_volume = value
        if(not isinstance(value, numbers.Number) or (value <= 0 )):
            raise ValueError("Error: Illegal cell_volume: %e. Exiting" %value)

# Set inputs from cell model chosen
    def SetInput(self):
        self.cell_model = Cell_Models[self.aircraft.CellModel]
        self.cell_capacity = self.cell_model['Cell Capacity']
        self.cell_rate = self.cell_model['Cell C rating']
        self.cell_resistance = self.cell_model['Internal Resistance']
        self.cell_current = self.cell_rate * self.cell_capacity
        self.cell_Vmax = self.cell_model['Cell Voltage Max']
        self.cell_Vmin = self.cell_model['Cell Voltage Min']
        self.cell_Vnom = self.cell_model['Cell Voltage Nominal']
        self.cell_mass = self.cell_model['Cell Mass']
        self.cell_radius = self.cell_model['Cell Radius']
        self.cell_height = self.cell_model['Cell Height']

        self.cell_polarization_constant = self.cell_model['Polarization Ctt']/3600
        self.cell_exponential_amplitude = self.cell_model['Exp Amplitude']
        self.cell_exponential_time_constant = self.cell_model['Exp Time constant']/3600
        self.cell_voltage_constant = self.cell_model['Voltage Constant']


        if not (self.cell_Vmax > self.cell_Vnom and self.cell_Vnom > self.cell_Vmin):
            raise ValueError("Illegal cell voltages: Vmax must be greater than Vnom which must be greater than Vmin")

        self.cell_Vmax = self.cell_exponential_amplitude + self.cell_voltage_constant
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
        self.pack_polarization_constant     = self.cell_polarization_constant * self.S_number / self.P_number
        self.pack_exponential_amplitude     = self.cell_exponential_amplitude * self.S_number
        self.pack_exponential_time_constant = self.cell_exponential_time_constant * self.P_number
        self.pack_voltage_constant          = self.cell_voltage_constant * self.S_number

        # relevant pack voltages:
        self.pack_Vmax = self.cell_Vmax * self.S_number
        self.pack_Vmin = self.cell_Vmin * self.S_number
        self.pack_Vnom = self.cell_Vnom * self.S_number

        # peak current that can be delivered safely from the pack
        self.pack_current = self.cell_current * self.P_number 

        #max power that can be delivered at 100% SOC and peak current:
        self.pack_power_max = self.pack_current * self.Nrg_n_Curr_2_Volt(0,self.pack_current) 

        # if self.S_number % 2:
        #     self.stack_length = self.cell_radius * (self.S_number+1)/2
        # else:
        #     self.stack_length = self.cell_radius * (self.S_number)/2 + self.cell_radius * (sqrt3-1)
        # the difference is so small this is irrelevant, uncomment if it turns out to be relevant

        # physical characteristics of the whole pack:
        self.stack_length = self.cell_radius * math.ceil(self.S_number/2)
        self.stack_width = self.cell_radius * (2 + np.sqrt(3))
        self.pack_volume = self.cell_height * self.stack_width * self.stack_length
        self.pack_weight = self.cell_mass*self.cells_total

        self.pack_config=f'S{self.S_number} P{self.P_number}'


    def Nrg_n_Curr_2_Volt(self, it, i):
        '''Converts the current being drawn + the current
           spent so far into an output voltage'''
        E0 = self.pack_voltage_constant
        R  = self.pack_resistance
        A  = self.pack_exponential_amplitude
        B  = self.pack_exponential_time_constant
        K  = self.pack_polarization_constant
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
            E0 = self.pack_voltage_constant
            R  = self.pack_resistance
            A  = self.pack_exponential_amplitude
            B  = self.pack_exponential_time_constant
            K  = self.pack_polarization_constant
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

# /->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/->-/
# \-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\-<-\
# this is where the thermal model starts, it lives in the battery class for now because i dont expect it to be very big 
# but who knows maybe that will change? 

#C = self.S_number * self.cell_mass * 1130      # mass times specific heat capacity = heat capacity
#R = 1/(self.stack_length * self.cell_height * 1000) # 1/(wall area times convection coef) = thermal resistance of the walls
#Ti = 300 # ambient temperature in kelvin
#T = Ti   # initial temperature starts at ambient
#dTdt = 0 #T derivative being initialized
#P_t = []
#T_t = []
#dTdt_t = []

    # returns the heat dissipated IN A SINGLE STACK. this divides the current by the stacks in parallel
    def Curr2Heat(self,I):
        return (self.cell_resistance*self.S_number * I/self.P_number)

    def Heat2Temp(self, time, heatpwr ):
        coef_convection = 1000
        R = 1/(self.stack_length * self.cell_height * coef_convection )
        C = self.cell_mass * self.S_number * self.cell_heat_capacity
        #C = 8.85 * 1130    # mass times specific heat capacity = heat capacity
        #R = 1/(0.208 * 1000) # 1/(wall area times convection coef) = thermal resistance of the walls

        Ti = 300 # ambient temperature in kelvin, should come from the mission profile? maybe?
        T = Ti   # initial temperature starts at ambient
        dTdt = 0 #T derivative being initialized

        T_t = []    # temperature over time
        dTdt_t = [] # temperature derivative over time

        for i in range(len(time)-1):
            dt   = time[i+1] - time[i]
            P    = heatpwr[i]
            dTdt = P/C + (Ti - T)/(R*C) 
            T    = T + dTdt*dt

            T_t.append(T)# += [T]
            dTdt_t.append(dTdt)# += [dTdt]
        return T_t , dTdt_t



    def BatteryHeating(self, CurrentvsTime ):

        Time = []
        HeatPWR = []

        CurrentvsTime = np.array(CurrentvsTime)
        Time = CurrentvsTime[:,0]
        HeatPWR = self.Curr2Heat(CurrentvsTime[:,1])

        #catch if somehow time has become unsorted, bug that used to happen at some point before i changed the code
        #this is here mostly to prevent the same bug from resurfacing on accident
        if not np.all(Time[:-1] <= Time[1:]):
            print(CurrentvsTime)
            raise Exception('time array is unordered, is the time coming from the integrator solution?')


        #interpolate the data to allow iterative integration
        dt = 1
        samples = int(np.ceil((Time[-1]-Time[0])/dt))
        lin_time = np.linspace(Time[0], Time[-1], samples)
        lin_heat = np.interp(lin_time, Time, HeatPWR)

        T_t , dTdt_t = self.Heat2Temp(lin_time, lin_heat )

        heatData=[lin_time[1:],
                  lin_heat[1:],
                  T_t,
                  dTdt_t]

        return heatData
