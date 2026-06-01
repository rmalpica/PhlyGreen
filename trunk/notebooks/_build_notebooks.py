"""Generate the workflow notebooks (run from trunk/: python notebooks/_build_notebooks.py).

Builds four narrative notebooks that each: build a typed config, show how to change inputs,
design the aircraft, print results, and plot every outcome (constraint diagram, mission
profile, energy time-series, mass breakdown; the fuel-cell ones also plot the tank state).
The notebooks are written un-executed; execute them with:

    jupyter nbconvert --to notebook --execute --inplace notebooks/*.ipynb
"""

import os
import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))


def md(text):
    return nbf.v4.new_markdown_cell(text)


def code(text):
    return nbf.v4.new_code_cell(text)


HEADER = """\
import sys, os
# reuse the baseline configs in examples/common.py (works whether the notebook is run
# from trunk/ or from trunk/notebooks/).
for _p in (os.path.join(os.getcwd(), 'examples'), os.path.join(os.getcwd(), '..', 'examples')):
    if os.path.isdir(_p):
        sys.path.insert(0, _p)
import matplotlib.pyplot as plt
import PhlyGreen as pg
from PhlyGreen import postprocess as pp
"""

PLOTS = """\
# Every outcome, including the time-resolved ones, via the generic post-processing helpers.
pp.plot_constraint_diagram(aircraft); plt.show()
pp.plot_mission_profile(aircraft);    plt.show()
pp.plot_energy_timeseries(aircraft);  plt.show()
pp.plot_mass_breakdown(aircraft);     plt.show()
"""


def write(name, cells):
    nb = nbf.v4.new_notebook()
    nb.cells = cells
    nb.metadata = {"kernelspec": {"name": "python3", "display_name": "Python 3",
                                  "language": "python"},
                   "language_info": {"name": "python"}}
    path = os.path.join(HERE, name)
    with open(path, "w") as f:
        nbf.write(nb, f)
    print("wrote", path)


# 1. ATR42 traditional reference -------------------------------------------------
write("01_ATR42_traditional_reference.ipynb", [
    md("# ATR42 — traditional turboprop (reference design)\n\n"
       "A conventional fuel-only regional turboprop, built with the **typed configuration**\n"
       "API. This notebook doubles as a numerical reference: the final cell checks the\n"
       "take-off weight against a frozen value."),
    code(HEADER + "from common import traditional_config"),
    md("## Build the design specification\n\n"
       "`traditional_config()` returns a validated `AircraftConfig` (see `examples/common.py`).\n"
       "Change any input by setting its field — e.g. design range and payload:"),
    code("config = traditional_config()\n"
         "config.mission.range_mission = 750     # [nm] try changing this\n"
         "config.mission.payload_weight = 4560   # [kg]\n"
         "print('configuration :', config.configuration)\n"
         "print('range         :', config.mission.range_mission, 'nm')\n"
         "print('payload       :', config.mission.payload_weight, 'kg')"),
    md("## Size the aircraft and read the results"),
    code("aircraft = pg.build_aircraft()\n"
         "aircraft.configure(config)\n"
         "r = aircraft.results()\n"
         "print(f'take-off weight : {r.WTO:8.1f} kg')\n"
         "print(f'block fuel      : {r.block_fuel:8.1f} kg')\n"
         "print(f'empty weight    : {r.empty_weight:8.1f} kg')\n"
         "print(f'wing area       : {r.WingSurface:8.1f} m^2')\n"
         "print(f'engine rating   : {r.engineRating/1000:8.1f} kW')"),
    md("## Plot every outcome"),
    code(PLOTS),
    md("## Reference check\n\n"
       "The ATR42 reference design (constant gas-turbine efficiency, new code structure)."),
    code("REFERENCE_WTO = 18327.5  # kg, frozen reference for this configuration\n"
         "assert abs(r.WTO - REFERENCE_WTO) < 5.0, f'WTO drifted: {r.WTO:.1f} kg'\n"
         "print(f'OK: WTO = {r.WTO:.1f} kg (reference {REFERENCE_WTO} kg)')"),
])

# 2. Hybrid-electric -------------------------------------------------------------
write("02_hybrid_electric.ipynb", [
    md("# Hybrid-electric turboprop\n\n"
       "A parallel hybrid: a battery-fed electric motor shares the propeller shaft with the\n"
       "gas turbine. The cruise battery share is set by the supplied-power ratio `phi`."),
    code(HEADER + "from common import hybrid_config"),
    md("## Build the design specification\n\n"
       "Raise the cruise `phi` to draw more power from the battery (heavier battery, less fuel)."),
    code("config = hybrid_config()\n"
         "for seg in config.mission_stages.segments:\n"
         "    if seg.name == 'Cruise':\n"
         "        seg.phi_end = 0.5     # battery supplies up to 50% of cruise power\n"
         "print('hybrid type:', config.hybrid_type)"),
    md("## Size the aircraft and read the results"),
    code("aircraft = pg.build_aircraft()\n"
         "aircraft.configure(config)\n"
         "r = aircraft.results()\n"
         "print(f'take-off weight : {r.WTO:8.1f} kg')\n"
         "print(f'mission fuel    : {r.Wf:8.1f} kg')\n"
         "print(f'battery mass    : {r.WBat:8.1f} kg')\n"
         "print(f'battery pack    : {r.pack_energy/3.6e6:6.1f} kWh, {r.pack_power_max/1000:6.1f} kW')"),
    md("## Plot every outcome (note the battery energy and state-of-charge traces)\n\n"
       "For a Class-II battery the state of charge is charge-based: it falls from 1 at the\n"
       "start of cruise to the minimum SOC by the end of the battery-assisted phase."),
    code(PLOTS),
    md("## Class-II propulsion models along the mission\n\n"
       "Beyond the design, we can look at the time-resolved behaviour of the Class-II\n"
       "propulsion components — the gas-turbine response surface, the d-q electric motor and\n"
       "the propeller RBF surrogate — evaluated along the flown trajectory. The plot shows\n"
       "each component's efficiency, the gas-turbine throttle (used/available power), and the\n"
       "propeller pitch. (Requires the GT artifact and pandas for the propeller surrogate.)"),
    code("pp.plot_component_timeseries(aircraft, n_engines=2); plt.show()"),
])

# 3. Hydrogen fuel cell ----------------------------------------------------------
write("03_hydrogen_fuel_cell.ipynb", [
    md("# Hydrogen fuel-cell aircraft\n\n"
       "A pure fuel-cell electric powertrain with a cryogenic LH2 tank — no battery, no gas\n"
       "turbine. We also re-fly the mission with the tank thermodynamics tracked, to see the\n"
       "tank pressure / mass / venting evolve. (Requires CoolProp for the tank.)"),
    code(HEADER + "from common import hydrogen_config"),
    md("## Build the design specification\n\n"
       "`tank=True` attaches a cryogenic LH2 tank. Try changing the design cell voltage."),
    code("config = hydrogen_config(v_cell_design=0.5, tank=True)\n"
         "print('configuration :', config.configuration)\n"
         "print('Ef (H2 LHV)   :', config.energy.Ef/1e6, 'MJ/kg')"),
    md("## Size the aircraft and read the results"),
    code("aircraft = pg.build_aircraft()\n"
         "aircraft.configure(config)\n"
         "r = aircraft.results()\n"
         "fc = aircraft.fuelcell\n"
         "print(f'take-off weight : {r.WTO:8.1f} kg')\n"
         "print(f'usable H2       : {aircraft.weight.WH2_Fuel:8.1f} kg')\n"
         "print(f'fuel-cell mass  : {r.WPT:8.1f} kg  ({fc.N_cells} cells)')\n"
         "print(f'tank empty mass : {aircraft.weight.WTank:8.1f} kg')"),
    md("## Plot the design outcomes"),
    code(PLOTS),
    md("## Tank thermodynamics over the mission\n\n"
       "Switch on tank tracking and re-fly the mission, then plot the tank state."),
    code("aircraft.mission.track_tank = True\n"
         "aircraft.mission.EvaluateMission(aircraft.weight.WTO)\n"
         "pp.plot_tank_state(aircraft); plt.show()"),
])

# 4. Fuel cell + battery ---------------------------------------------------------
write("04_fuel_cell_battery.ipynb", [
    md("# Fuel cell + battery hybrid\n\n"
       "Hybridizing the hydrogen fuel cell with a battery: the battery supplies a fraction\n"
       "`phi` of the propulsive power, the fuel cell the rest."),
    code(HEADER + "from common import fuelcell_battery_config"),
    md("## Build the design specification\n\n"
       "`cruise_phi` is the battery share during cruise (0 reproduces the pure-hydrogen design)."),
    code("config = fuelcell_battery_config(cruise_phi=0.10)\n"
         "print('configuration :', config.configuration)"),
    md("## Size the aircraft and read the results"),
    code("aircraft = pg.build_aircraft()\n"
         "aircraft.configure(config)\n"
         "r = aircraft.results()\n"
         "print(f'take-off weight : {r.WTO:8.1f} kg')\n"
         "print(f'usable H2       : {aircraft.weight.WH2_Fuel:8.1f} kg')\n"
         "print(f'battery mass    : {r.WBat:8.1f} kg')\n"
         "print(f'fuel-cell mass  : {r.WPT:8.1f} kg')"),
    md("## Plot every outcome"),
    code(PLOTS),
])

print("done")
