"""Execute a sinlge flight configuration"""

from validate_configurations import RunAll

configurations_list = {
    "Powerplant": ["Hybrid"],
    "Mission Name": ["Mission-FelixFinger"],  # "HybridCruiseOnly","HybridTOClimbOnly"
    "Cell Specific Energy": [2000], #[100, 1366, 2000],
    "Cell Specific Power":[8000], # if set to None the program will scale it with the specific energy
    "Range": [1280],#linspace(100, 2500, 25 , dtype=int).tolist(), # in km
    "Payload": [1325], #linspace(550, 1960, 11, dtype=int).tolist(),
    "Base Phi": [0.1],#(linspace(0, 100, 11, dtype=int) / 100.0).tolist(),
}

# Pick the name under which to save the plots and then run the flight
r = RunAll("ThreeFinger")
r.run_config(configurations_list)