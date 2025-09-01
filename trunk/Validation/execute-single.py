# """Execute a sinlge flight configuration"""

# from validate_configurations import RunAll

# # To be compaible with the parallel process script, this needs to be a dictionary
# # of lists, each containing a single value. Its a bit odd, but the alternative would
# # make the main script too complex only to solve this trivial edge case.
# configurations_list = {
#     "Powerplant": ["Hybrid"],
#     "Mission Name": ["Mission-FelixFinger"],  # "HybridCruiseOnly","HybridTOClimbOnly"
#     "Cell": ["Finger-Cell-Thermal",],
#     "Cell Specific Energy": [1500], #[100, 1366, 2000],
#     "Cell Specific Power":[6000], # if set to None the program will scale it with the specific energy
#     "Range": [2000],#linspace(100, 2500, 25 , dtype=int).tolist(), # in km
#     "Payload": [2000], #linspace(550, 1960, 11, dtype=int).tolist(),
#     "Base Phi": [0.1],#(linspace(0, 100, 11, dtype=int) / 100.0).tolist(),
#     "Pack Voltage":[740]
# }

# # Pick the name under which to save the plots and then run the flight
# r = RunAll("Iterator-Test-Scaled-Full")
# r.run_config(configurations_list)

import sys
sys.path.insert(0, "../")
import PhlyGreen as pg

class craft:
    BatteryInput = {
            "Model": "Finger-Cell-Thermal",
            "SpecificPower": 6000,
            "SpecificEnergy": 1500,
            "Minimum SOC": 0.0,
            "Pack Voltage": 800,
            "Class":"II"
        }

mycraft = craft
btt = pg.Systems.Battery.Battery(mycraft)
btt.SetInput()

pn = 23
btt.Configure(pn)
btt.T = 315
btt.it = 654.5480620572879
btt.i=160.1260422442075/pn
print(f"Vmin={btt.cell_Vmin} Vout={btt.cell_Vout}  SOC={btt.SOC}")