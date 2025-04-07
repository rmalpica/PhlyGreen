"""Run parametric sweeps on the aircraft configurations in parallel"""

from validate_configurations import RunAll
from numpy import linspace

configurations_list = {
    "Powerplant": ["Hybrid"],
    "Mission Name": ["Mission-FelixFinger"],  # "HybridCruiseOnly","HybridTOClimbOnly"
    "Cell Specific Energy": [1500],  # linspace(100, 2000, 2 , dtype=int).tolist(),
    "Cell Specific Power": [6000],
    "Range": linspace(500, 1500, 3, dtype=int).tolist(),  # in km
    "Payload": linspace(500, 1500, 3, dtype=int).tolist(),
    "Base Phi": [0.1],
}

ooi = [
    "Fuel Mass",
    "Block Fuel Mass",
    "Structure Mass",
    "Powertrain Mass",
    "Empty Weight",
    "Zero Fuel Weight",
    "Takeoff Weight",
    "Wing Surface",
    "TakeOff Engine Shaft PP",
    "Climb Cruise Engine Shaft PP",
    "Battery Mass",
    "Takeoff Weight",
    "TakeOff Battery PP",
    "Climb Cruise Battery PP",
]


r = RunAll("MultiTest")
r.run_config(configurations_list, ooi)
