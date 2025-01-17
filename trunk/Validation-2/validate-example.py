"""main script for running sweeps in an ordered manner"""

from validate_configurations import RunAll
from numpy import linspace

configurations_list = {
    "Powerplant": ["Hybrid"],
    "Mission Name": ["Mission-FelixFinger"],  # "HybridCruiseOnly","HybridTOClimbOnly"
    "Cell": ["ThermalModel-Cell-Mega"],
    "Range": linspace(400,600, 2, dtype=int).tolist(),
    "Payload": linspace(400, 500, 2, dtype=int).tolist(),
    "Base Phi": [0.1],
}
outputs_of_interest = []
r = RunAll("TESTING")
r.run_parallel(configurations_list, outputs_of_interest)
