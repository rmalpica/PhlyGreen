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
    md("## Designing with the Class-II propulsion models\n\n"
       "Now we *size the aircraft using the Class-II propulsion models* — the gas-turbine\n"
       "response surface and the d-q electric motor. These work as a percentage of a **fixed\n"
       "nominal power** that must be set before the mission (an engine cannot resize itself\n"
       "instant by instant). A good first guess is `DesignPW * WTO` from a quick Class-I\n"
       "pre-pass. We set **two engines** (an ATR has two) so each gas turbine sits in the\n"
       "well-trained part of the response surface. (A simple Class-I battery keeps it fast.)"),
    code("import warnings\n"
         "def design_class_ii(p_gt, p_em, n_engines=2):\n"
         "    cfg = hybrid_config(battery_class='I')\n"
         "    for seg in cfg.mission_stages.segments:\n"
         "        if seg.name == 'Cruise':\n"
         "            seg.phi_end = 0.5\n"
         "    cfg.energy.eta_gas_turbine_model = 'ResponseSurface'\n"
         "    cfg.energy.gt_design_power = p_gt\n"
         "    cfg.energy.eta_electric_motor_model = 'Smart'\n"
         "    cfg.energy.em_design_power = p_em\n"
         "    cfg.energy.em_design_voltage = 800.0\n"
         "    cfg.energy.em_design_rpm = 11000.0\n"
         "    aircraft = pg.build_aircraft()\n"
         "    aircraft.PropellerInput = {'Number of Engines': n_engines}\n"
         "    with warnings.catch_warnings():\n"
         "        warnings.simplefilter('ignore')   # we read the sizing report explicitly below\n"
         "        aircraft.configure(cfg)\n"
         "    return aircraft\n\n"
         "# 1. Class-I pre-pass -> tentative nominal power = DesignPW * WTO\n"
         "pre = pg.build_aircraft(); pre.configure(hybrid_config(battery_class='I'))\n"
         "P_nominal = pre.DesignPW * pre.weight.WTO\n"
         "print(f'tentative nominal power = DesignPW * WTO = {P_nominal/1e3:.0f} kW')"),
    md("## Is the gas turbine adequately sized? (altitude-aware check)\n\n"
       "The available shaft power lapses with altitude. The check below walks the mission and\n"
       "compares the **required** power to the power **available** from the response surface at\n"
       "each point — so a turbine whose peak demand is below its nominal can still be\n"
       "*power-limited* in the climb (unable to sustain flight)."),
    code("aircraft = design_class_ii(P_nominal, P_nominal)\n"
         "gt = aircraft.powertrain.report_class_ii_sizing()['gas turbine']\n"
         "print(f\"GT nominal      : {gt['nominal']/1e3:8.0f} kW\")\n"
         "print(f\"worst load ratio: {gt['worst_load_ratio']:8.2f}  (>1 means power-limited)\")\n"
         "print(f\"power-limited?  : {gt['power_limited']}\")\n"
         "print(f\"min nominal to avoid power-limiting: {gt['min_nominal']/1e3:.0f} kW\")"),
    md("The tentative gas turbine is **power-limited at altitude** — it cannot deliver the\n"
       "climb power, so the design is infeasible. Re-size it to the recommended nominal (with a\n"
       "small margin) and design again:"),
    code("aircraft = design_class_ii(1.05 * gt['min_nominal'], P_nominal)\n"
         "rep = aircraft.powertrain.report_class_ii_sizing()\n"
         "g, m = rep['gas turbine'], rep['electric motor']\n"
         "print(f\"GT : nominal {g['nominal']/1e3:7.0f} kW, worst load ratio {g['worst_load_ratio']:.2f} -> {g['status']}\")\n"
         "print(f\"EM : nominal {m['nominal']/1e3:7.0f} kW, peak {m['peak_demand']/1e3:7.0f} kW -> {m['status']}\")\n"
         "print(f\"take-off weight : {aircraft.results().WTO:.0f} kg\")"),
    md("## Class-II propulsion time series\n\n"
       "With the gas turbine adequately sized, the **throttle is now realistic and varying** —\n"
       "high on climb, lower in cruise where the battery offloads the turbine — and never\n"
       "pinned at 100%. The **electric-motor throttle is low** (the motor only carries the\n"
       "battery share). The plot also shows each component's efficiency and the propeller\n"
       "pitch."),
    code("pp.plot_component_timeseries(aircraft); plt.show()"),
    md("## Why is the Class-II take-off weight lower than Class-I?\n\n"
       "Not a paradox — it is an input-assumption difference. The Class-I model used a\n"
       "*constant* gas-turbine efficiency (here 0.22, deliberately conservative), while the\n"
       "Class-II response surface returns a higher, operating-point-dependent efficiency\n"
       "(~0.30-0.40 at the cruise load). Higher efficiency burns less fuel, so the aircraft is\n"
       "lighter. For a like-for-like comparison, set the constant Class-I efficiency to the\n"
       "value the response surface predicts at cruise."),
    code("import numpy as np\n"
         "ts = pp.component_timeseries(aircraft)\n"
         "print(f\"Class-II GT efficiency in cruise ~ {np.nanmedian(ts['eta_gas_turbine']):.3f}\")\n"
         "print(f\"Class-I  GT efficiency (constant)  = 0.220\")"),
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
