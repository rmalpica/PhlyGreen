"""Run parametric sweeps on the aircraft configurations in parallel"""

from validate_configurations import RunAll
from numpy import linspace

# configurations_list = {
#     "Powerplant": ["Hybrid"],
#     "Mission Name": ["Mission-FelixFinger"],
#     "Cell": ["Finger-Cell-Thermal"],
#     "Cell Specific Energy":  [1500],
#     "Cell Specific Power": [6000],
#     "Range": linspace(500, 2500, 3, dtype=int).tolist(),
#     "Payload": linspace(500, 2500, 3, dtype=int).tolist(),
#     "Base Phi": [0.3],
#     "Pack Voltage": [740],
# }

configurations_list = {
    "Powerplant": ["Hybrid"],
    "Mission Name": ["Mission-FelixFinger"],
    "Cell": ["Finger-Cell-Thermal"],
    "Cell Specific Energy":  [1500],
    "Cell Specific Power": [6000],
    "Range": linspace(500, 2500, 5, dtype=int).tolist(),
    "Payload": linspace(500, 2500, 5, dtype=int).tolist(),
    "Base Phi": [0.3],
    "Pack Voltage": [740],
}

outputs_of_interest = [
    "Fuel Mass",
    "Takeoff Weight",
    "Battery Mass",
    "Total Iterations",
    "Total Evaluations",
    "Battery P number",
]

# fixed guess - A
# use last as guess - B
# scale last as guess - C
# scale last as guess, bounded - D

r = RunAll("Multi-A")
r.run_config(configurations_list, outputs_of_interest)
