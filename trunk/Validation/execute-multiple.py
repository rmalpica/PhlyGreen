"""Run parametric sweeps on the aircraft configurations in parallel"""

from validate_configurations import RunAll
from numpy import linspace

configurations_list = {
    "Powerplant": ["Hybrid"],
    "Mission Name": ["Mission-FelixFinger"],  # "HybridCruiseOnly","HybridTOClimbOnly"
    "Cell": [
        "Finger-Cell-Thermal",
         "ThermalModel-Cell"
    ],
    "Cell Specific Energy":linspace(100, 2000, 20, dtype=int).tolist(),
    "Cell Specific Power":[8000], # if set to None the program will scale it with the specific energy
    "Range": linspace(100 / 1.852, 2500 / 1.852, 25, dtype=int).tolist(),
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
r = RunAll("SweepOf")
r.run_config(configurations_list, outputs_of_interest)
