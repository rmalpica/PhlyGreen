from validate_configurations import RunAll
from numpy import linspace
ooi = [
    "Fuel Mass",
    "Empty Weight",
    #"Zero Fuel Weight",
    "Takeoff Weight",
    #"Total Iterations",
    #"Total Evaluations",
    "Battery Mass",
    #"Total Iterations",
    #"Wing Surface",
    #"TakeOff Engine Shaft PP",
    #"TakeOff Battery PP",
    #"Battery Pack Energy",
    #"Battery Pack Max Power",
    #"Battery Pack Specific Energy",
    #"Battery Pack Specific Power",
    #"Battery P number",
    #"Battery S number",
    #"Battery Pack Charge",
    # "Max Phi",
    # "Max SOC",
    # "Max Altitude",
    #"Max Fuel Energy",
    #"Max Total Power",
    #"Max Battery Energy",
    #"Max Battery current",
    #"Max Air Temperature",
    #"Max Battery Voltage",
    #"Max Cooling Flow Rate",
    #"Max Battery OC Voltage",
    #"Max Battery Temperature",
    #"Max Battery Spent Power",
    #"Max Battery Efficiency",
    #"Max Battery Delivered Power",
    # "Min Phi",
    #"Min SOC",
    # "Min Altitude",
    # "Min Fuel Energy",
    #"Min Total Power",
    #"Min Battery Energy",
    #"Min Battery current",
    #"Min Air Temperature",
    #"Min Battery Voltage",
    #"Min Cooling Flow Rate",
    #"Min Battery OC Voltage",
    #"Min Battery Temperature",
    #"Min Battery Spent Power",
    #"Min Battery Efficiency",
    #"Min Battery Delivered Power",
]

# # # # # #
ioi = ["Mission Name"]
configs = [
    (200, 1960, "Hybrid", "Finger-Cell-Thermal", 1500, 3000, 800, 0.1, "Mission-Dip-Electric"),
    (200, 1960, "Hybrid", "Finger-Cell-Thermal", 1500, 3000, 800, 0.1, "Mission-Dip-Half"),
    # (400, 1960, "Hybrid", "Finger-Cell-Thermal", 1500, 3000, 800, 0.5, "Mission-Temperature-Test"),
]
r = RunAll("Dip-20")
r.run_parallel(configs, ooi, ioi)


# # Sweep PHI
# configs = {
#     "Powerplant": ["Hybrid"],
#     "Mission Name": ["Mission-FelixFinger"],
#     "Cell": ["Finger-Cell-Thermal"],
#     "Cell Specific Energy": [1500], 
#     "Cell Specific Power": [6000],
#     "Range": [2361],
#     "Payload": [547],
#     "Base Phi": [0.1],
#     "Pack Voltage":[800],
# }

# r = RunAll("20SOC-OLD")
# r.run_config(configs,ooi=ooi)