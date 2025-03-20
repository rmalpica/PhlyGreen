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
    "Cell Specific Energy":[1500],
    "Cell Specific Power":[8000], # if set to None the program will scale it with the specific energy
    "Range": linspace(396 / 1.852, 2361 / 1.852, 2, dtype=int).tolist(),
    "Payload": [550],  # linspace(550, 1960, 11, dtype=int).tolist(),
    "Base Phi": [0.1]#(linspace(0, 100, 3, dtype=int) / 100.0).tolist(),
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
r = RunAll("TESTING")
r.run_config(configurations_list, outputs_of_interest)
