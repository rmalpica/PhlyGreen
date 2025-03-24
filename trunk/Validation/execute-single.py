"""Execute a sinlge flight configuration"""

from validate_configurations import RunAll

# To be compaible with the parallel process script, this needs to be a dictionary
# of lists, each containing a single value. Its a bit odd, but the alternative would
# make the main script too complex only to solve this trivial edge case.
configurations_list = {
    "Powerplant": ["Hybrid"],
    "Mission Name": ["Mission-FelixFinger"],  # "HybridCruiseOnly","HybridTOClimbOnly"
    "Cell": ["Finger-Cell-Thermal"],
    "Cell Specific Energy":[1500],
    "Cell Specific Power":[8000], # if set to None the program will scale it with the specific energy
    "Range": [1363], # in km
    "Payload": [1960],
    "Base Phi": [0.1],
}

# Pick the name under which to save the plots and then run the flight
r = RunAll("Stock-Finger")
r.run_config(configurations_list)
