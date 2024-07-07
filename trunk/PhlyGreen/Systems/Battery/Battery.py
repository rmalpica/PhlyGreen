#import numpy as np
import math
import numbers
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
        self.cell_volume = self.cell_model['Cell Volume'] #this will be replaced with height + radius dimensions later for the thermal model

        self.cell_charge = 3600*self.cell_capacity #convert the capacity from Ah to Coulomb to make the maths check out
        self.cell_energy = self.cell_charge*self.cell_Vnom # cell capacity in joules
        self.S_number = math.ceil(self.controller_Vmax/self.cell_Vmax) #number of cells in series to achieve desired voltage. max voltage is preferred as it minimizes losses due to lower current being needed for a larger portion of the flight

#determine battery configuration
    #must receive the number of cells in parallel
    def Configure(self, parallel_cells):

        self.P_number=parallel_cells
        self.cells_total = self.P_number * self.S_number

        self.pack_charge = self.cells_total * self.cell_charge
        self.pack_energy = self.cells_total * self.cell_energy
        self.pack_resistance = self.cell_resistance * self.S_number / self.P_number
        self.pack_current = self.cell_current * self.P_number
        self.pack_Vmax = self.cell_Vmax * self.S_number
        self.pack_Vmin = self.cell_Vmin * self.S_number
        self.pack_Vnom = self.cell_Vnom * self.S_number
        self.pack_power_max = self.pack_current * self.pack_Vmax - self.pack_resistance*self.pack_current**2

        self.pack_weight = self.cell_mass*self.cells_total
        self.pack_volume = self.cell_volume*self.cells_total

        self.pack_config='S'+str(self.S_number)+'P'+str(self.P_number)
        return ()

    #calculate the SOC from the charge spent so far
    def Energy_2_SOC(self, C):
        SOC = 1-C/self.pack_energy #single line definition like this
        return SOC

    # convert SOC to open circuit voltage 
    # possibly expand to include the exponential zones?
    def SOC_2_OC_Voltage(self, SOC):
        Cell_U_oc=(-0.7*SOC + 3.7) #linear variation of open circuit voltage with SOC, change it to use parameters of the battery instead of being hardcoded
        Pack_U_oc = Cell_U_oc * self.S_number
        return Pack_U_oc

    #Calculates the open circuit voltage and current to enable calculating real power drain from the battery in function of useful output power. U_oc is the open circuit voltage, U_out is the measured battery output voltage
    def Power_2_Current(self, SOC, Power_out):
        if Power_out == 0:
            I_out = 0

        else:
            U_oc = self.SOC_2_OC_Voltage(SOC)
            aux=U_oc**2 - 4 * Power_out * self.pack_resistance

            if (aux < 0):
                I_out=None
            else:
                U_out = (U_oc + math.sqrt(aux))/2 #from the math solution of P_out = U_out * I_out
                I_out = (U_oc - U_out)/self.pack_resistance
        return I_out

    #find the number of cells required to supply the requested current at the current SOC
    def Pwr_2_P_num(self, SOC, Power_out):
        if Power_out == 0:
            return 0
        U_oc = self.SOC_2_OC_Voltage(SOC) #open circuit voltage
        valid = False   #initializing
        P_number = math.floor(4 * Power_out * self.cell_resistance * self.S_number / U_oc**2) #initializing with minimum possible P number

        while not valid:
            Resistance = self.cell_resistance * self.S_number / P_number   #calculate equivalent pack R
            a = U_oc**2 - 4 * Power_out * Resistance #quadratic formula parameter, if its negative then the sqrt will be imaginary, so it just skips the maths in that case
            if a > 0:
                U_out = (U_oc + math.sqrt(a))/2     #find actual output voltage
                I_out = (U_oc - U_out)/Resistance   #find current output
                if (I_out < P_number * self.cell_current):
                    valid = True
            P_number = P_number+1
        return P_number

    #find the number of cells in parallel required to obtain the total energy necessary assuming the number of cells in series is known
    def Nrg_2_P_num(self, Energy_out):
        if Energy_out==0:
            return 0
        total_cells = math.ceil(Energy_out/self.cell_energy) 
        energy_P_number = math.ceil(total_cells/self.S_number)
        return energy_P_number
