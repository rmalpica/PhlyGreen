"""Run parametric sweeps on the aircraft configurations in parallel"""

from validate_configurations import RunAll
from numpy import linspace

configurations_list = {
    "Powerplant": ["Hybrid"],
    "Mission Name": ["Mission-FelixFinger"],  # "HybridCruiseOnly","HybridTOClimbOnly"
    "Cell": ["Finger-Cell-Thermal",],
    "Cell Specific Energy":linspace(100, 2000, 20, dtype=int).tolist(),
    "Cell Specific Power":[8000], # if set to None the program will scale it with the specific energy
    "Range": linspace(100, 2500, 25 , dtype=int).tolist(), # in km
    "Payload": [1960], #linspace(550, 1960, 11, dtype=int).tolist(),
    "Base Phi": [0.1]#(linspace(0, 100, 11, dtype=int) / 100.0).tolist(),
}
# print(configurations_list)
outputs_of_interest = [
    "Fuel Mass",
    "Empty Weight",
    "Zero Fuel Weight",
    "Takeoff Weight",
    "Battery Mass",
    "Total Iterations",
]
r = RunAll("SweepOfThings11")
r.run_config(configurations_list, outputs_of_interest)
