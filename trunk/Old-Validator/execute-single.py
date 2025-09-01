# from validate_configurations import RunAll

# ooi = [
#     "Fuel Mass",
#     "Empty Weight",
#     #"Zero Fuel Weight",
#     "Takeoff Weight",
#     #"Total Iterations",
#     #"Total Evaluations",
#     "Battery Mass",
#     #"Total Iterations",
#     #"Wing Surface",
#     #"TakeOff Engine Shaft PP",
#     #"TakeOff Battery PP",
#     #"Battery Pack Energy",
#     #"Battery Pack Max Power",
#     #"Battery Pack Specific Energy",
#     #"Battery Pack Specific Power",
#     #"Battery P number",
#     #"Battery S number",
#     #"Battery Pack Charge",
#     # "Max Phi",
#     # "Max SOC",
#     # "Max Altitude",
#     #"Max Fuel Energy",
#     #"Max Total Power",
#     #"Max Battery Energy",
#     #"Max Battery current",
#     #"Max Air Temperature",
#     #"Max Battery Voltage",
#     #"Max Cooling Flow Rate",
#     #"Max Battery OC Voltage",
#     #"Max Battery Temperature",
#     #"Max Battery Spent Power",
#     #"Max Battery Efficiency",
#     #"Max Battery Delivered Power",
#     # "Min Phi",
#     #"Min SOC",
#     # "Min Altitude",
#     # "Min Fuel Energy",
#     #"Min Total Power",
#     #"Min Battery Energy",
#     #"Min Battery current",
#     #"Min Air Temperature",
#     #"Min Battery Voltage",
#     #"Min Cooling Flow Rate",
#     #"Min Battery OC Voltage",
#     #"Min Battery Temperature",
#     #"Min Battery Spent Power",
#     #"Min Battery Efficiency",
#     #"Min Battery Delivered Power",
# ]

# # # # # # # Run the three example flights that should have the same mtow
# ioi = ["Range", "Base Phi"]
# configs = [
#     (396, 1960, "Traditional", "Finger-Cell-Thermal", 1500, 6000, 800, 0, "Mission-FelixFinger"),
#     (1280, 1325, "Traditional", "Finger-Cell-Thermal", 1500, 6000, 800, 0, "Mission-FelixFinger"),
#     (2361, 547, "Traditional", "Finger-Cell-Thermal", 1500, 6000, 800, 0, "Mission-FelixFinger"),
# ]
# r = RunAll("val")
# r.run_parallel(configs, ooi, ioi)
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

pn = 1500
btt.Configure(pn)
btt.T = 300
btt.it = 28.7*pn
btt.i=0
print(f"Vmin={btt.cell_Vmin} Vout={btt.cell_Vout}  SOC={btt.SOC}")