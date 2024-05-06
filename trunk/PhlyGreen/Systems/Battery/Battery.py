import numpy as np
import PhlyGreen.Systems.Battery.Cell_Models as Cell_Models
class Battery:
    def __init__(self, aircraft):
        self.aircraft = aircraft
        self.cell_capacity = None 
        self.cell_rate = None
        self.cell_Vmax = None
        self.cell_Vmin = None
        self.cell_Vnom = None
        self.cell_mass = None
        self.cell_volume = None
        self.required_energy = None
        self.required_power = None
        self.parallel_stack_number = 1 #initial value so things can be calculated at all, does this work?
        self.pack_energy = None
        self.controller_Vmax = 740 
        self.controller_Vmin = 420 #this range of voltages should be defined in the model of the motor controller, but ill do that later, for now its hardcoded

#should define a bunch of property setters and getters that make sure that all values are positive, and that Vmax ≥ Vnom ≥ Vmin

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
        self.cell_volume = self.cell_model['Cell Volume'] #possibly substitute this for a cylinder & prism volume calculator that takes in cylinder/square and corresponding xyz dimensions to calculate volume that way

        self.cell_energy = 3600*self.cell_capacity*self.cell_Vnom # cell capacity in joules instead of amps hour

        #self.series_stack_size = np.max([np.floor(self.controller_Vmax/self.cell_Vmax), np.ceil(self.controller_Vmin/self.cell_Vmin) ])
        # ^^ replaced by version that only considers vmax, i believe that to be correct but i need to investigate to be sure
        self.series_stack_size = np.floor(self.controller_Vmax/self.cell_Vmax) #number of cells in series to achieve desired voltage
        self.pack_energy = self.parallel_stack_number*self.series_stack_size*self.cell_energy #initializing this at a non zero value

#determine battery configuration
    #def Configuration(self,required_energy, required_power): # cant work like this anymore, cells for power are calculated externally
    #must receive the number of cells in parallel for energy and power
    def Configuration(self, parallel_cells_energy, parallel_cells_power):

        '''
        #number of cells in series per stack, imposed by whatever motor controller we are using, as those have a fixed operational voltage range that cant be exceeded
        #is this the best way of doing it? or should the optimizer be able to tweak this? - find if there is an optimal way of choosing
        
        #is this even true? investigate if this is actually how you calculate energy per cell, or if its just an approximation

        #cell energy calculated outside of here using another function
        #self.parallel_cells_energy = np.ceil(total_cells_energy/self.series_stack_size)

        #cant work like this anymore, cells are calculated outside of here
        #self.parallel_nr_power = np.ceil(required_power/(self.controller_Vmax*self.cell_current))
        '''

        #number of cell stacks in parallel required while tracking which constraint is the driver
        if parallel_cells_energy > parallel_cells_power:
            self.parallel_stack_number = parallel_cells_energy
            self.energy_or_power = 'energy'
        else:
            self.parallel_stack_number = parallel_cells_power
            self.energy_or_power = 'power'

        #find the total number of cells in the whole pack
        self.cells_total = self.parallel_stack_number * self.series_stack_size
        self.pack_energy = self.cells_total * self.cell_energy
        
        self.pack_current = self.cell_current*self.parallel_stack_number #pretty sure this will have to be swapped out for something else since the current rating goes down with SOC but for now it suffices
        
        self.pack_Vmax = self.cell_Vmax*self.series_stack_size
        self.pack_Vmin = self.cell_Vmin*self.series_stack_size
        self.pack_Vnom = self.cell_Vnom*self.series_stack_size

        self.pack_weight = self.cell_mass*self.cells_total
        self.pack_volume = self.cell_volume*self.cells_total

        self.pack_type='S'+str(self.series_stack_size)+'P'+str(self.parallel_stack_number)
        return ()

    #calculate the SOC from the energy spent so far
    def Energy_2_SOC(self, E):
        Q_0 = self.pack_energy #total charge
        Q   = Q_0 - E          #remaining charge
        SOC = Q / Q_0          #SOC gives remaining charge %
        return SOC

    #convert SOC to open circuit voltage using the linear relation. possibly expand to include the exponential zones?
    def SOC_2_OC_Voltage(self, SOC):
        Cell_U_oc=(-0.7*SOC + 3.7) #linear variation of open circuit voltage with SOC, change it to use parameters of the battery instead of being hardcoded
        Pack_U_oc = Cell_U_oc * self.series_stack_size
        return Pack_U_oc

    #Calculates the open circuit voltage and current to enable calculating real power drain from the battery in function of useful output power. U_oc is the open circuit voltage, U_out is the measured battery output voltage
    def Power_2_Current(self, SOC, Power_out, nr_parallel_cells):
        Resistance = self.cell_resistance * self.series_stack_size / nr_parallel_cells #calculate total internal R of the pack
        U_oc = self.SOC_2_OC_Voltage(SOC)
        U_out = (U_oc + (U_oc**2 - 4 * Power_out * Resistance)**0.5)/2 #this comes from the analytical solution of P_out = U_out * I_out
        I_out = (U_oc - U_out)/Resistance
        return I_out

    #find the number of cells required to supply the requested current at the current SOC. Assumes that the motor controller will draw a higher current to compensate for the lower input voltage as SOC goes down. Power is useful power output to the motor controller.
    def Power_2_Parallel_Cells(self, SOC, Power_out):
        #iterates a couple times until the nr of cells doesnt change anymore since the current is affected by the nr of cells in parallel, and vice versa
        #should this be replaced with a brent function to ensure convergence?
        """U_oc = self.SOC_2_OC_Voltage(SOC)
        p_cells_0=
        parallel_cells = np.ceil(self.cell_resistance * self.series_stack_size*(4*Power_out)/U_oc**2)
        while (p_cells_0!=parallel_cells):
            p_cells_0=parallel_cells
            Resistance = self.cell_resistance * self.series_stack_size / p_cells_0 #calculate total internal R of the pack
            U_out = (U_oc + (U_oc**2 - 4 * Power_out * Resistance)**0.5)/2 #this comes from the analytical solution of P_out = U_out * I_out
            I_out = (U_oc - U_out)/Resistance
            parallel_cells = np.ceil(I_out/self.cell_current)
            parallel_cells = np.ceil(self.cell_resistance * self.series_stack_size*(4*Power_out)/U_oc**2)
            replace this with brent function????? idk
            """
        U_oc = self.SOC_2_OC_Voltage(SOC)
        parallel_cells = np.ceil(self.cell_resistance * self.series_stack_size*(4*Power_out)/U_oc**2)
        Resistance = self.cell_resistance * self.series_stack_size / parallel_cells
        U_out = (U_oc + (U_oc**2 - 4 * Power_out * Resistance)**0.5)/2
        I_out = (U_oc - U_out)/Resistance
        parallel_cells = np.ceil(I_out/self.cell_current)
        print(parallel_cells)
        return parallel_cells

    #find the number of cells in parallel required to obtain the total energy necessary assuming the number of cells in series is known
    def Energy_2_Parallel_Cells(self, Energy_out):
        total_cells = np.ceil(Energy_out/self.cell_energy) 
        parallel_cells = np.ceil(total_cells/self.series_stack_size)
        return parallel_cells

""" TODO_LIST:
consider changing the functions in this file to use arrays instead of single constant values? 
in Power_2_Parallel_Cells() FIX IT because its badly broken right now
"""