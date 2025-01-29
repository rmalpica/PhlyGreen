"""main script for running sweeps in an ordered manner"""

from validate_configurations import RunAll

configurations_list = {
    "Powerplant": ["Hybrid"],
    "Mission Name": ["Mission-FelixFinger"],  # "HybridCruiseOnly","HybridTOClimbOnly"
    "Cell": ["ThermalModel-Cell-Ultra"],
    "Range": [1500],
    "Payload": [1500],
    "Base Phi": [0.2],
}

r = RunAll("Efficiency_Comparison-Basic")
r.run_config(configurations_list)
