from validate_configurations import RunAll
from numpy import linspace

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
    "Battery Pack Energy",
    "Battery Pack Max Power",
    "Battery Pack Specific Energy",
    "Battery Pack Specific Power",
    "Battery P number",
    "Battery S number",
    "Battery Pack Charge",
    # "Max Phi",
    # "Max SOC",
    # "Max Altitude",
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
    # "Min Phi",
    "Min SOC",
    # "Min Altitude",
    # "Min Fuel Energy",
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

# # # # # # Run the three example flights that should have the same mtow
ioi = ["Range", "Payload"]
configs = [
    (396, 1960, "Hybrid", "Finger-Cell-Thermal", 1500, 8000, 740, 0.1, "Mission-FelixFinger"),
    (1280, 1325, "Hybrid", "Finger-Cell-Thermal", 1500, 8000, 740, 0.1, "Mission-FelixFinger"),
    (2361, 547, "Hybrid", "Finger-Cell-Thermal", 1500, 8000, 740, 0.1, "Mission-FelixFinger"),
]
r = RunAll("Thesis-Sample")
r.run_parallel(configs, ooi, ioi)

# # # # # # Run the tables for the different ranges, energy densities, and phi

configs = {
    "Powerplant": ["Hybrid"],
    "Mission Name": ["Mission-FelixFinger"],
    "Cell": ["Finger-Cell-Thermal"],
    "Cell Specific Energy": [1500],  # linspace(100, 2000, 2 , dtype=int).tolist(),
    "Cell Specific Power": [8000],
    "Range": [396],  # linspace(100, 2500, 2, dtype=int).tolist(),  # in km
    "Payload": [1960],  # linspace(550, 1960, 11, dtype=int).tolist(),
    "Base Phi": [0.1],  # (linspace(0, 100, 21, dtype=int) / 100.0).tolist(),
    "Pack Voltage": [740],
}

configs["Cell Specific Energy"] = [1500]
configs["Range"] = linspace(100, 2500, 25, dtype=int).tolist()
configs["Base Phi"] =[0.1]
r = RunAll("Thesis-Sweep-Range")
r.run_config(configs, ooi)

configs["Cell Specific Energy"] = linspace(100, 2000, 20 , dtype=int).tolist()
configs["Range"] = [396]
configs["Base Phi"] =[0.1]
r = RunAll("Thesis-Sweep-Energy")
r.run_config(configs, ooi)

configs["Cell Specific Energy"] = [1500]
configs["Range"] = [396]
configs["Base Phi"] = (linspace(0, 100, 11, dtype=int) / 100.0).tolist()
r = RunAll("Thesis-Sweep-Phi")
r.run_config(configs, ooi)

# # # # # # Interesting Heatmaps

configs = {
    "Powerplant": ["Hybrid"],
    "Mission Name": ["Mission-FelixFinger"],
    "Cell": ["Finger-Cell-Thermal"],
    "Cell Specific Energy": linspace(100, 2000, 20 , dtype=int).tolist(),
    "Cell Specific Power": [8000],
    "Range": [396],  # linspace(100, 2500, 2, dtype=int).tolist(),  # in km
    "Payload": [1960],  # linspace(550, 1960, 11, dtype=int).tolist(),
    "Base Phi": (linspace(0, 100, 21, dtype=int) / 100.0).tolist(),
    "Pack Voltage": [740],
}

r = RunAll("Thesis-Sweep-Energy-v-Phi")
r.run_config(configs, ooi)


configs = {
    "Powerplant": ["Hybrid"],
    "Mission Name": ["Mission-FelixFinger"],
    "Cell": ["Finger-Cell-Thermal"],
    "Cell Specific Energy": [1500],  # linspace(100, 2000, 2 , dtype=int).tolist(),
    "Cell Specific Power": [8000],
    "Range": linspace(100, 2500, 25, dtype=int).tolist(),  # in km
    "Payload": linspace(500, 2500, 20, dtype=int).tolist(),
    "Base Phi": [0.1],  # (linspace(0, 100, 21, dtype=int) / 100.0).tolist(),
    "Pack Voltage": [740],
}

r = RunAll("Thesis-Sweep-Payload-v-Range")
r.run_config(configs, ooi)
