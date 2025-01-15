"""main script for running sweeps in an ordered manner"""

from validate_configurations import RunAll
from numpy import linspace
aL = {
    "ArchList": ["Hybrid"],
    "MissionList": ["Mission-FelixFinger"],  # "HybridCruiseOnly","HybridTOClimbOnly"
    "CellsList": ["ThermalModel-Cell-Mega"],
    "RangesList": linspace(400, 2000, 3, dtype=int).tolist(),
    "PayloadsList": linspace(400, 2000, 3, dtype=int).tolist(),
    "PhisList": [0.2],
}

r = RunAll("TESTING")
r.run_parallel(aL)
