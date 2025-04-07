"""Run parametric sweeps on the aircraft configurations in parallel"""

from validate_configurations import RunAll
from numpy import linspace
ooi = [
    "Fuel Mass",
    "Block Fuel Mass",
    "Structure Mass",
    "Powertrain Mass",
    "Empty Weight",
    "Zero Fuel Weight",
    "Takeoff Weight",
    "Wing Surface",
    "Battery Mass",
    "Takeoff Weight",
]

configurations_list = {
    "Powerplant": ["Traditional"],
    "Mission Name": ["Mission-FelixFinger"],  # "HybridCruiseOnly","HybridTOClimbOnly"
    "Cell Specific Energy": [1500],  # linspace(100, 2000, 2 , dtype=int).tolist(),
    "Cell Specific Power": [6000],
    "Range": linspace(100, 2500, 25, dtype=int).tolist(),  # in km
    "Payload": [1960],
    "Base Phi": [0.1],
}

r = RunAll("TRAD-RangeSweep")
r.run_config(configurations_list, ooi)

configurations_list = {
    "Powerplant": ["Traditional"],
    "Mission Name": ["Mission-FelixFinger"],  # "HybridCruiseOnly","HybridTOClimbOnly"
    "Cell Specific Energy": [1500],  # linspace(100, 2000, 2 , dtype=int).tolist(),
    "Cell Specific Power": [6000],
    "Range": [1500],  # in km
    "Payload": linspace(100, 2000, 20, dtype=int).tolist(),
    "Base Phi": [0.1],
}

r = RunAll("TRAD-PayloadSweep")
r.run_config(configurations_list, ooi)