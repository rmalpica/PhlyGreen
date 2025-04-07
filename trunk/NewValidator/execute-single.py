"""Execute a sinlge flight configuration"""

from validate_configurations import RunAll

configurations_list = {
    "Powerplant": ["Hybrid"],
    "Mission Name": ["Mission-FelixFinger"],
    "Cell Specific Energy": [1500*3600],
    "Cell Specific Power":[6000],
    "Range": [1280],
    "Payload": [1325],
    "Base Phi": [0.1],
}

# Pick the name under which to save the plots and then run the flight
r = RunAll("OldTest")
r.run_config(configurations_list)