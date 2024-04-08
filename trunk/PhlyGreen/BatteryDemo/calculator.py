import BatteryConfigurator as bc

#define the mission requirements for the battery pack
#in the final version it will use the values from phlygreen
class Requirements:
    energy=50000
    power=12345
    voltage=600

#define the specs for the cells used
#in the final version it will use the values from the user input
class Cell:
    Vmin=2.5
    Vnom=3.7
    capacity=3
    rate=9
    mass=0.045 #kg
    volume=0.00001654048 #m^3

requirements=Requirements
cellspecs=Cell

configuration = bc.configure(cellspecs,requirements)
print("series",configuration.series_size)
print("parallel",configuration.parallel_size)
print("total cells",configuration.cells_total)
print("mass",configuration.cells_total*cellspecs.mass)

#in the future volume calculation will have to take into account cell dimensions and packing efficiency
print("volume",configuration.cells_total*cellspecs.volume)
