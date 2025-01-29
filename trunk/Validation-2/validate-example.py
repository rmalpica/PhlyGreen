"""main script for running sweeps in an ordered manner"""

from validate_configurations import RunAll
from numpy import linspace

configurations_list = {
    "Powerplant": ["Hybrid"],
    "Mission Name": ["Mission-FelixFinger"],  # "HybridCruiseOnly","HybridTOClimbOnly"
    "Cell": [
        "ThermalModel-Cell-Mega",
        "ThermalModel-Cell",
        "ThermalModel-Cell-Super",
        "ThermalModel-Cell-Ultra",
    ],
    "Range": linspace(4000, 3000, 1, dtype=int).tolist(),
    "Payload": linspace(4000, 5000, 1, dtype=int).tolist(),
    "Base Phi": (linspace(5, 50, 16, dtype=int) / 100.0).tolist(),
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
