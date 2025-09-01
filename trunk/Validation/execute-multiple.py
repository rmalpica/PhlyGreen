"""Run parametric sweeps on the aircraft configurations in parallel"""

from validate_configurations import RunAll
from numpy import linspace

configurations_list = {
    "Powerplant": ["Hybrid"],
    "Mission Name": ["Mission-FelixFinger"],  # "HybridCruiseOnly","HybridTOClimbOnly"
    "Cell": [
        "Finger-Cell-Thermal",
    ],
    "Cell Specific Energy":  [1500],#linspace(100, 2000, 2 , dtype=int).tolist(),
    "Cell Specific Power": [6000],  # if set to None the program will scale it with the specific energy
    "Range": linspace(100, 2500, 25, dtype=int).tolist(),  # in km
    "Payload": linspace(500, 2500, 21, dtype=int).tolist(),
    "Base Phi": [0.1],#(linspace(0, 100, 3, dtype=int) / 100.0).tolist(),
    "Pack Voltage": [800],
}


outputs_of_interest = [
    "Fuel Mass",
    "Empty Weight",
    "Zero Fuel Weight",
    "Takeoff Weight",
    "Battery Mass",
    "Total Iterations",
    "Total Evaluations",
    "Wing Surface",
    "TakeOff Engine Shaft PP",
    "TakeOff Battery PP",
    "Battery Pack Energy",
    "Battery Pack Max Power",
    "Battery Pack Specific Energy",
    "Battery Pack Specific Power",
     "Battery P number",
    "Battery S number",
    "Battery Pack Charge",
    "Max Phi",
    "Max SOC",
    "Max Altitude",
    "Max Fuel Energy",
    "Max Total Power",
    "Max Battery Energy",
    "Max Battery current",
    "Max Air Temperature",
    "Max Battery Voltage",
    "Max Cooling Flow Rate",
    "Max Battery OC Voltage",
     "Max Battery Temperature",
    "Max Battery Spent Power",
    "Max Battery Efficiency",
    "Max Battery Delivered Power",
    "Min Phi",
    "Min SOC",
    "Min Altitude",
    "Min Fuel Energy",
    "Min Total Power",
    "Min Battery Energy",
    "Min Battery current",
    "Min Air Temperature",
     "Min Battery Voltage",
    "Min Cooling Flow Rate",
     "Min Battery OC Voltage",
    "Min Battery Temperature",
    "Min Battery Spent Power",
     "Min Battery Efficiency",
    "Min Battery Delivered Power",
]

r = RunAll("Examples-NOTEMP")
r.run_config(configurations_list, outputs_of_interest)