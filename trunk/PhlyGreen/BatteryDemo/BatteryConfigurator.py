import numpy as np

class Configuration:
    def __init__(self, series_size, parallel_size, cells_total):
        self.series_size = series_size
        self.parallel_size = parallel_size
        self.cells_total = cells_total
        

#determine battery configuration
def configure(cell,requirements):
    #minimum nr of cells in series to meet voltage requirements
    series_stack_size = np.ceil(requirements.voltage/cell.Vmin) 

    #minimum nr of cells to meet energy demand
    cell_count = np.ceil(requirements.energy/(cell.capacity*cell.Vnom))
    #nr of stacks needed to meet energy demand and voltage requirements
    stack_count_energy=np.ceil(cell_count/series_stack_size)

    #current capacity of a single stack of cells in series
    stackCurrent = cell.rate*cell.capacity
    #minimum number of cell stacks needed in parallel to meet power demand
    stack_count_power = np.ceil(requirements.power/(stackCurrent*requirements.voltage)) 

    #determine number of stacks in parallel needed overall by picking the largest one
    stack_count=[stack_count_power,stack_count_energy]
    stack_count=np.max(stack_count)
    #stack_count=stack_count[stack_count_index]

    #update number of cells
    cell_count= stack_count * series_stack_size
    configuration = Configuration(series_stack_size,stack_count,cell_count)
    return configuration