"""main script for running sweeps in an ordered manner"""

import validate_configurations as vc
from numpy import linspace
aL = {
    "ArchList": ["Hybrid"],
    "MissionList": ["Mission-FelixFinger"],  # "HybridCruiseOnly","HybridTOClimbOnly"
    "CellsList": ["ThermalModel-Cell-Mega"],
    "RangesList": linspace(400, 2000, 1, dtype=int).tolist(),
    "PayloadsList": linspace(400, 2000, 2, dtype=int).tolist(),
    "PhisList": [0.2],
}

# specify the list and name to use,
# specify a non empty varsOfInterest
# in order to run the extra plots
vc.run_all(aL, "TESTING")
