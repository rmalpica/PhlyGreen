from validate_configurations import RunAll
from numpy import linspace
# program = "class2new"
program = "-DO228-class1old"

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

# # # # # # Run the three example flights that should have the same mtow
ioi = ["Range", "Base Phi"]
configs = [
    (396, 1960, "Hybrid", "Finger-Cell-Thermal", 1500, 6000, 800, 0.1, "Mission-FelixFinger"),
    (1280, 1325, "Hybrid", "Finger-Cell-Thermal", 1500, 6000, 800, 0.1, "Mission-FelixFinger"),
    (2361, 547, "Hybrid", "Finger-Cell-Thermal", 1500, 6000, 800, 0.1, "Mission-FelixFinger"),
        (396, 1960, "Hybrid", "Finger-Cell-Thermal", 1500, 6000, 800, 1, "Mission-FelixFinger"),
    (1280, 1325, "Hybrid", "Finger-Cell-Thermal", 1500, 6000, 800, 1, "Mission-FelixFinger"),
    (2361, 547, "Hybrid", "Finger-Cell-Thermal", 1500, 6000, 800, 1, "Mission-FelixFinger"),
    (396, 1960, "Traditional", "Finger-Cell-Thermal", 1500, 6000, 800, 0, "Mission-FelixFinger"),
    (1280, 1325, "Traditional", "Finger-Cell-Thermal", 1500, 6000, 800, 0, "Mission-FelixFinger"),
    (2361, 547, "Traditional", "Finger-Cell-Thermal", 1500, 6000, 800, 0, "Mission-FelixFinger"),
]
r = RunAll("HybTradEle-sample"+program)
r.run_parallel(configs, ooi, ioi)

# # # # # Traditional vs hybrid sweeps

configs = {
    "Powerplant": ["Hybrid"],
    "Mission Name": ["Mission-FelixFinger"],
    "Cell": ["Finger-Cell-Thermal"],
    "Cell Specific Energy": [1500],  # linspace(100, 2000, 2 , dtype=int).tolist(),
    "Cell Specific Power": [6000],
    "Range": [396],  # linspace(100, 2500, 2, dtype=int).tolist(),  # in km
    "Payload": [1960],  # linspace(550, 1960, 11, dtype=int).tolist(),
    "Base Phi": [0.1],  # (linspace(0, 100, 21, dtype=int) / 100.0).tolist(),
    "Pack Voltage": [800],
}


# Sweep RANGE
configs["Cell Specific Energy"] = [1500]
configs["Cell Specific Power"] = [6000]
configs["Range"] = linspace(100, 2500, 25, dtype=int).tolist()
configs["Payload"] = [1960]
configs["Base Phi"] =[0.1]
r = RunAll("Sweep-Range-Hybrid"+program)
r.run_config(configs, ooi)

configs["Powerplant"] = ["Traditional"]
r = RunAll("Sweep-Range-Traditional"+program)
r.run_config(configs, ooi)

# Sweep RANGE
configs["Powerplant"] = ["Hybrid"]
configs["Base Phi"] =[1]
r = RunAll("Sweep-Range-Electric"+program)
r.run_config(configs, ooi)



# Sweep ENERGY
configs["Powerplant"] = ["Hybrid"]
configs["Cell Specific Energy"] = linspace(100, 2000, 20 , dtype=int).tolist()
configs["Cell Specific Power"] = [None]
configs["Range"] = [396]
configs["Payload"] = [1960]
configs["Base Phi"] =[0.1]
r = RunAll("Sweep-Energy-Hybrid"+program)
r.run_config(configs, ooi)

configs["Powerplant"] = ["Hybrid"]
configs["Base Phi"] =[1]
r = RunAll("Sweep-Energy-Electric"+program)
r.run_config(configs, ooi)

# Sweep PHI
configs = {
    "Powerplant": ["Hybrid"],
    "Mission Name": ["Mission-FelixFinger"],
    "Cell": ["Finger-Cell-Thermal"],
    "Cell Specific Energy": [1500], 
    "Cell Specific Power": [6000],
    "Range": [396],
    "Payload": [1960],
    "Base Phi": (linspace(0, 100, 11, dtype=int) / 100.0).tolist(),
    "Pack Voltage": [800],
}
r = RunAll("Sweep-Phi"+program)
r.run_config(configs, ooi)