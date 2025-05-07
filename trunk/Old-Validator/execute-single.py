"""Execute a sinlge flight configuration"""

from validate_configurations import RunAll

configurations_list = {
    "Powerplant": ["Hybrid"],
    "Mission Name": ["Mission-FelixFinger"],
    "Cell Specific Energy": [1500],
    "Cell Specific Power":[8000],
    "Range": [396],
    "Payload": [1960],
    "Base Phi": [1],
}

# Pick the name under which to save the plots and then run the flight
r = RunAll("OldTest")
r.run_config(configurations_list)