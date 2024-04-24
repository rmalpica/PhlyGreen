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
        self.controller_Vmax = 740 
        self.controller_Vmin = 420 #this range of voltages should be defined in the model of the motor controller, but ill do that later, for now its hardcoded

#should define a bunch of property setters and getters that make sure that all values are positive, and that Vmax ≥ Vnom ≥ Vmin

    def SetInput(self):
        self.cell_model = Cell_Models[self.aircraft.CellModel]
        self.cell_capacity = self.cell_model['Cell Capacity']  #self.aircraft.CellInput['Cell Capacity']
        self.cell_rate = self.cell_model['Cell C rating']
        self.cell_current = self.cell_rate * self.cell_capacity
        self.cell_Vmax = self.cell_model['Cell Voltage Max']
        self.cell_Vmin = self.cell_model['Cell Voltage Min']
        self.cell_Vnom = self.cell_model['Cell Voltage Nominal']
        self.cell_mass = self.cell_model['Cell Mass']
        self.cell_volume = self.cell_model['Cell Volume'] #possibly substitute this for a cylinder & prism volume calculator that takes in cylinder/square and corresponding xyz dimensions to calculate volume that way
        

#determine battery configuration
    def Configuration(self,required_energy, required_power):
        
        #number of cells in series per stack, imposed by whatever motor controller we are using, as those have a fixed operational voltage range that cant be exceeded
        #is this the best way of doing it? or should the optimizer be able to tweak this? - find if there is an optimal way of choosing
        self.series_stack_size = np.max([np.floor(self.controller_Vmax/self.cell_Vmax), np.ceil(self.controller_Vmin/self.cell_Vmin) ]) 
        
        #is this even true? investigate if this is actually how you calculate energy per cell, or if its just an approximation
        self.total_cells_energy = np.ceil(required_energy/(3600*self.cell_capacity*self.cell_Vnom)) 

        self.parallel_nr_energy = np.ceil(self.total_cells_energy/self.series_stack_size)
        #maybe change later to be able to use power at different SOCs, but for now it assumes max power at minimum SOC, worst case scenario
        self.parallel_nr_power = np.ceil(required_power/(self.controller_Vmin*self.cell_current)) 

        #number of cell stacks in parallel required while tracking which constraint is the driver
        if self.parallel_nr_energy > self.parallel_nr_power:
            self.parallel_stack_number = self.parallel_nr_energy
            self.energy_or_power = 'energy'
        else:
            self.parallel_stack_number = self.parallel_nr_power
            self.energy_or_power = 'power'

        #find the total number of cells in the whole pack
        self.cells_total = self.parallel_stack_number * self.series_stack_size

        self.pack_current = self.cell_current*self.parallel_stack_number #pretty sure this will have to be swapped out for something else since the current rating goes down with SOC but for now it suffices
        self.pack_Vmax = self.cell_Vmax*self.series_stack_size
        self.pack_Vmin = self.cell_Vmin*self.series_stack_size
        self.pack_Vnom = self.cell_Vnom*self.series_stack_size

        self.pack_weight = self.cell_mass*self.cells_total
        self.pack_volume = self.cell_volume*self.cells_total

        self.pack_type='S'+str(self.series_stack_size)+'P'+str(self.parallel_stack_number)
        return ()


        """ ###########################################################
        #minimum nr of cells in series to meet voltage requirements
        series_stack_size = np.ceil(requirements['Voltage']/cell['Vmin']) 

        #minimum nr of cells to meet energy demand
        cell_count = np.ceil(requirements['Energy']/(cell['Capacity']*cell['Vnom']))
        #nr of stacks needed to meet energy demand and voltage requirements
        stack_count_energy=np.ceil(cell_count/series_stack_size)

        #current capacity of a single stack of cells in series
        stackCurrent = cell['Rate']*cell['Capacity']
        #minimum number of cell stacks needed in parallel to meet power demand
        stack_count_power = np.ceil(requirements['Peak Power']/(stackCurrent*requirements['Voltage'])) 

        #determine number of stacks in parallel needed overall by picking the largest one
        stack_count=[stack_count_power,stack_count_energy]
        stack_count=np.max(stack_count)
        #stack_count=stack_count[stack_count_index]

        #update number of cells
        cell_count= stack_count * series_stack_size
        configuration = Configuration(series_stack_size,stack_count,cell_count)

        return configuration """