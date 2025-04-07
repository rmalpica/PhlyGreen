"""Run parametric sweeps on the aircraft configurations in parallel"""

from validate_configurations import RunAll
from numpy import linspace

configurations_list = {
    "Powerplant": ["Hybrid"],
    "Mission Name": ["Mission-FelixFinger"],  # "HybridCruiseOnly","HybridTOClimbOnly"
    "Cell Specific Energy":  [1500],#linspace(100, 2000, 2 , dtype=int).tolist(),
    "Cell Specific Power": [None],  # if set to None the program will scale it with the specific energy
    "Range": linspace(100, 2500, 2, dtype=int).tolist(),  # in km
    "Payload": [1960],  # linspace(550, 1960, 11, dtype=int).tolist(),
    "Base Phi": (linspace(0, 100, 3, dtype=int) / 100.0).tolist(),
}

ooi = [
    "Fuel Mass",
    "Empty Weight",
    "Zero Fuel Weight",
    "Takeoff Weight",
    "Battery Mass",
    "Total Iterations",
    "Wing Surface",
    "TakeOff Engine Shaft PP",
    "TakeOff Battery PP",
]


r = RunAll("MultiExperiment")
r.run_config(configurations_list, ooi)
