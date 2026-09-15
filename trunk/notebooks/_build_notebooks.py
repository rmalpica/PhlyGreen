"""Generate the workflow notebooks (run from trunk/: python notebooks/_build_notebooks.py).

Builds five narrative notebooks that each: build a typed config, show how to change inputs,
design the aircraft, print results, and plot every outcome (constraint diagram, mission
profile, energy time-series, mass breakdown; the fuel-cell ones also plot the tank state).
The notebooks are written un-executed; execute them with:

    jupyter nbconvert --to notebook --execute --inplace notebooks/*.ipynb

The committed .ipynb carry their executed outputs, so regenerating ALL of them discards those
outputs until they are executed again. Pass a substring to rebuild only what you are working on:

    python notebooks/_build_notebooks.py 05        # only 05_A320_turbofan.ipynb
"""

import os
import sys

import nbformat as nbf

HERE = os.path.dirname(os.path.abspath(__file__))

# Optional name filter, so rebuilding one notebook does not wipe the others' stored outputs.
_ONLY = sys.argv[1] if len(sys.argv) > 1 else None


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
    if _ONLY is not None and _ONLY not in name:
        return
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


# 5. A320 turbofan ---------------------------------------------------------------
write("05_A320_turbofan.ipynb", [
    md("# A320 — turbofan jet, and what changes versus the regional turboprop\n\n"
       "Every other notebook here sizes a **propeller** aircraft, where the installed rating is\n"
       "shaft power. This one sizes an **A320-200 class turbofan**, which is rated on **thrust** —\n"
       "and that single difference propagates into the constraint diagram, the engine model, the\n"
       "drag polar and the weight loop.\n\n"
       "The notebook doubles as a validation: the design is compared against sourced Airbus and\n"
       "EASA reference data (`validation/a320_reference.md`)."),
    code(HEADER + "import numpy as np\nfrom common import turbofan_config, traditional_config"),

    md("## 1. Why a jet is a different sizing problem\n\n"
       "`Performance.PoWTO` returns\n\n"
       "$$P/W = g\\left[\\frac{q V C_D}{W/S} + \\beta P_s\\right] = \\frac{D V + W\\,\\mathrm{ROC}}{m}$$\n\n"
       "which is **thrust power** — there is no propulsive efficiency in it. So the requirement\n"
       "physics is already propulsion-agnostic and $T/W = (P/W)/(gV)$ *exactly*. Nothing about the\n"
       "aerodynamics changes for a jet.\n\n"
       "What changes is the **rating the requirements are compared against**. That switch lives in\n"
       "one method, `Powertrain.SizingDenominator`: it divides by the power lapse for a\n"
       "propeller aircraft, and by $g\\,V\\,\\lambda_T(h,M)$ for a turbofan.\n\n"
       "This is more than a change of units. `FindDesignPoint` minimises the *largest* requirement\n"
       "over wing loading, and each requirement is evaluated at its own speed — so the\n"
       "minimum-installed-**power** point and the minimum-installed-**thrust** point are different\n"
       "points, and can be set by different constraints."),
    code("config = turbofan_config()\n"
         "print('configuration    :', config.configuration)\n"
         "print('structural model :', config.aircraft_type, '(Class-'+config.weight_class+')')\n"
         "print('drag polar       :', config.aerodynamics.analytic_polar['type'])\n"
         "print('engine model     :', config.energy.eta_gas_turbine_model)\n"
         "print()\n"
         "print('design mission: {:.0f} nm, {:.0f} kg payload, {:.0f} nm alternate, {:.0f} min hold'\n"
         "      .format(config.mission.range_mission, config.mission.payload_weight,\n"
         "              config.mission.range_diversion, config.mission.time_loiter))"),

    md("## 2. The engine: one overall-efficiency node\n\n"
       "The turboprop chain is `fuel → gas turbine → gearbox → propeller`. A turbofan has no\n"
       "gearbox and no propeller, so the powertrain graph collapses to a **single node** carrying\n"
       "the overall efficiency\n\n"
       "$$\\eta_o = \\frac{F V}{\\dot m_f\\,\\mathrm{LHV}}$$\n\n"
       "This is not a simplification: because the graph normalises on propulsive power,\n"
       "$P_f/P_p = 1/\\eta_o$ is **exactly a TSFC closure**, since\n"
       "$\\mathrm{TSFC} = V/(\\eta_o\\,\\mathrm{LHV})$. The two carry the same information, so fuel\n"
       "burn, range and CO₂ all come out of the existing machinery unchanged.\n\n"
       "$\\eta_o$, TSFC and the thrust lapse all come from one pyCycle high-bypass turbofan sweep."),
    code("from PhlyGreen.Systems.Powertrain.turbofan_surrogate import TurbofanResponseSurface\n"
         "s = TurbofanResponseSurface()\n"
         "LHV, F00 = 43.0e6, config.energy.turbofan_design_thrust\n"
         "print(f'map: {s.tag}')\n"
         "print(f\"{'condition':<30}{'eta_o':>8}{'TSFC':>16}{'lapse':>8}\")\n"
         "for label, alt, M, pc in [('take-off    SL     M 0.25', 0., 0.25, 1.00),\n"
         "                          ('climb       10 kft M 0.55', 10000., 0.55, 0.90),\n"
         "                          ('cruise      33 kft M 0.78', 33000., 0.78, 0.75),\n"
         "                          ('cruise      35 kft M 0.78', 35000., 0.78, 0.85)]:\n"
         "    lap = s.thrust_lapse(alt, M)\n"
         "    eta, tsfc, _, _ = s.predict(F00, alt, M, pc*F00*lap)\n"
         "    print(f'{label:<30}{eta:>8.3f}{tsfc*3600*9.80665:>11.3f} lb/lbf/h{lap:>8.3f}')\n"
         "print()\n"
         "print('A turboprop cruises at eta_o ~ 0.25-0.30 and much lower speed; the turbofan buys\\n'\n"
         "      'its efficiency back through flight speed, not through propeller efficiency.')"),

    md("## 3. The drag polar: wave drag the turboprop never sees\n\n"
       "An ATR42 cruises at M 0.4, far below drag divergence, so a plain quadratic polar is fine.\n"
       "A jet cruises near it, so the `compressible` polar adds a Korn drag-divergence Mach number\n"
       "and Lock's fourth-power wave drag:\n\n"
       "$$M_{dd} = \\frac{\\kappa}{\\cos\\Lambda} - \\frac{t/c}{\\cos^2\\Lambda} - \\frac{C_L}{10\\cos^3\\Lambda},"
       "\\qquad C_{D,wave} = 20\\,(M-M_{crit})^4$$\n\n"
       "The plain quadratic polar has **no wave drag at all**, and the legacy `Cd0` bump is flat\n"
       "below M 0.8 and then steps *down* — neither can size a transonic aircraft."),
    code("aero = pg.build_aircraft()\n"
         "aero.configure(config, design=False)\n"
         "a = aero.aerodynamics\n"
         "M = np.linspace(0.5, 0.88, 60)\n"
         "cl = 0.5\n"
         "fig, ax = plt.subplots(figsize=(7,4))\n"
         "ax.plot(M, 1e4*np.asarray(a.Cd_wave(cl, M)), label='wave drag (compressible polar)')\n"
         "ax.axvline(float(a.MachCrit(cl)), ls=':',  color='tab:grey', label='$M_{crit}$')\n"
         "ax.axvline(float(a.MachDD(cl)),   ls='--', color='tab:red',  label='$M_{dd}$')\n"
         "ax.axvline(0.78, ls='-.', color='tab:green', label='design cruise M 0.78')\n"
         "ax.set_xlabel('Mach'); ax.set_ylabel('$C_{D,wave}$ [counts]')\n"
         "ax.set_title(f'Transonic drag rise at $C_L$={cl} (sweep {a.sweep:.0f}$^\\\\circ$, t/c {a.tc})')\n"
         "ax.grid(alpha=0.3); ax.legend(); plt.show()"),

    md("## 3b. What the engine model actually looks like\n\n"
       "Before flying it, it is worth seeing the response surface itself. Four views, each\n"
       "showing something a constant-efficiency turboprop chain cannot represent:\n\n"
       "* **$\\eta_o$ against thrust fraction** — efficiency falls away at part throttle, and the\n"
       "  whole curve shifts up with altitude because the cycle runs cooler and the flight speed\n"
       "  is higher.\n"
       "* **TSFC against Mach** — it *rises* with speed even though $\\eta_o$ improves, because\n"
       "  $\\mathrm{TSFC} = V/(\\eta_o\\,\\mathrm{LHV})$ and $V$ grows faster than $\\eta_o$ does.\n"
       "* **Thrust lapse** — this is the Mach dependence a turboshaft power lapse has no way to\n"
       "  express, and it is fitted from the deck rather than assumed.\n"
       "* **Air flow** — total through the inlet, and the core flow the combustor actually sees;\n"
       "  the gap between them is the bypass stream.\n"
       "* **Bypass ratio** — in this deck BPR is an off-design *balance* variable, solved against\n"
       "  the bypass-nozzle throat area rather than held at its design value. That is why total\n"
       "  inlet flow has to be read from the cycle directly: it is **not** the core flow times a\n"
       "  fixed $(1+BPR)$. A turboprop has no analogue of any of this."),
    code("from PhlyGreen.Systems.Powertrain.turbofan_surrogate import TurbofanResponseSurface\n"
         "s = TurbofanResponseSurface()\n"
         "F00 = config.energy.turbofan_design_thrust\n"
         "IMP = 3600 * 9.80665     # kg/(N s) -> lb/(lbf h)\n"
         "fig, ax = plt.subplots(2, 3, figsize=(15, 7.5))\n"
         "\n"
         "pcs = np.linspace(0.32, 1.0, 25)\n"
         "for alt in (0., 10000., 20000., 30000., 35000.):\n"
         "    M = 0.78 if alt >= 20000 else 0.45\n"
         "    lap = s.thrust_lapse(alt, M)\n"
         "    eta = [s.predict(F00, alt, M, pc*F00*lap)[0] for pc in pcs]\n"
         "    ax[0,0].plot(pcs, eta, label=f'{alt/1000:.0f} kft, M {M:.2f}')\n"
         "ax[0,0].set_xlabel('thrust fraction $F/F_{avail}$'); ax[0,0].set_ylabel(r'$\\eta_o$ [-]')\n"
         "ax[0,0].set_title('overall efficiency vs throttle'); ax[0,0].legend(fontsize=8)\n"
         "\n"
         "machs = np.linspace(0.25, 0.85, 25)\n"
         "for alt in (0., 10000., 20000., 30000., 35000.):\n"
         "    y = []\n"
         "    for M in machs:\n"
         "        lap = s.thrust_lapse(alt, M)\n"
         "        y.append(s.predict(F00, alt, M, 0.85*F00*lap)[1]*IMP)\n"
         "    ax[0,1].plot(machs, y, label=f'{alt/1000:.0f} kft')\n"
         "ax[0,1].set_xlabel('Mach'); ax[0,1].set_ylabel('TSFC [lb/(lbf h)]')\n"
         "ax[0,1].set_title('TSFC at 85 % thrust'); ax[0,1].legend(fontsize=8)\n"
         "\n"
         "alts = np.linspace(0., 35000., 40)\n"
         "for M in (0.25, 0.45, 0.60, 0.78):\n"
         "    ax[1,0].plot(alts/1000, [s.thrust_lapse(a, M) for a in alts], label=f'M {M:.2f}')\n"
         "ax[1,0].set_xlabel('altitude [kft]'); ax[1,0].set_ylabel(r'$F_{max}/F_{00}$ [-]')\n"
         "ax[1,0].set_title('thrust lapse (fitted, not assumed)'); ax[1,0].legend(fontsize=8)\n"
         "\n"
         "for M, c in ((0.25,'tab:blue'), (0.78,'tab:red')):\n"
         "    ax[0,2].plot(alts/1000, [s.inlet_air_flow(F00, a, M, 0.85) for a in alts],\n"
         "                 color=c, label=f'inlet, M {M:.2f}')\n"
         "    ax[0,2].plot(alts/1000, [s.core_air_flow(F00, a, M, 0.85) for a in alts],\n"
         "                 color=c, ls='--', label=f'core, M {M:.2f}')\n"
         "ax[0,2].set_xlabel('altitude [kft]'); ax[0,2].set_ylabel('air flow [kg/s]')\n"
         "ax[0,2].set_title('air flow, 85 % thrust'); ax[0,2].legend(fontsize=7)\n"
         "\n"
         "for M in (0.25, 0.45, 0.60, 0.78):\n"
         "    ax[1,1].plot(alts/1000, [s.bypass_ratio(a, M, 0.85) for a in alts], label=f'M {M:.2f}')\n"
         "ax[1,1].set_xlabel('altitude [kft]'); ax[1,1].set_ylabel('BPR [-]')\n"
         "ax[1,1].set_title('bypass ratio vs altitude (balance variable)'); ax[1,1].legend(fontsize=8)\n"
         "\n"
         "for alt in (0., 10000., 20000., 35000.):\n"
         "    Mb = 0.78 if alt >= 20000 else 0.45\n"
         "    ax[1,2].plot(pcs, [s.bypass_ratio(alt, Mb, pc) for pc in pcs],\n"
         "                 label=f'{alt/1000:.0f} kft, M {Mb:.2f}')\n"
         "ax[1,2].set_xlabel('thrust fraction'); ax[1,2].set_ylabel('BPR [-]')\n"
         "ax[1,2].set_title('bypass ratio vs throttle'); ax[1,2].legend(fontsize=8)\n"
         "for a in ax.ravel(): a.grid(alpha=0.3)\n"
         "fig.tight_layout(); plt.show()\n"
         "print('Total inlet flow and core (post-bypass-split, post-bleed) flow are both taken')\n"
         "print('from the pyCycle deck, scaled from the reference engine by installed thrust.')\n"
         "print('They are NOT related by a fixed (1+BPR): bypass ratio is an off-design balance')\n"
         "print('variable here, solved against the bypass-nozzle throat area, so it moves across')\n"
         "print('the flight envelope -- see the BPR panel in section 3b.')"),

    md("## 4. Size it\n\n"
       "The constraint diagram is now drawn in **T/W** rather than P/W — `plot_constraint_diagram`\n"
       "switches the axis automatically for a `Turbofan`."),
    code("aircraft = pg.build_aircraft()\n"
         "aircraft.configure(config)\n"
         "r = aircraft.results()\n"
         "print(f'take-off weight : {r.WTO:9.0f} kg')\n"
         "print(f'empty weight    : {r.empty_weight:9.0f} kg')\n"
         "print(f'block fuel      : {aircraft.weight.Wf + aircraft.weight.final_reserve:9.0f} kg')\n"
         "print(f'wing area       : {aircraft.WingSurface:9.1f} m^2')\n"
         "print(f'design T/W      : {r.DesignTW:9.4f} [-]')\n"
         "print(f'design W/S      : {aircraft.DesignWTOoS/9.81:9.1f} kg/m^2')\n"
         "print(f'SLS thrust      : {r.engineRating/1000:9.1f} kN  ({r.engineRating_units})')\n"
         "print(f'mean TSFC       : {r.mean_TSFC*3600*9.80665:9.3f} lb/(lbf h)')"),
    code(PLOTS),

    md("## 4b. The engine along the mission\n\n"
       "`postprocess.turbofan_timeseries` recovers the engine-level history from the converged\n"
       "design — the thrust from the same `PoWTO` the mission integrated, the fuel flow from the\n"
       "same `PRatio[0]` that closed the weight loop. These are the design, not a re-modelling of\n"
       "it, and the integrated fuel below reproduces the weight loop's own answer to ~0.01 %.\n\n"
       "Watch the step at top of climb: thrust drops by a factor of four between the climb and the\n"
       "cruise, while TSFC *rises* — the engine is far more efficient per unit of thrust up there,\n"
       "but each newton is bought at a higher speed."),
    code("ts = pp.turbofan_timeseries(aircraft)\n"
         "tmin = ts['time'] / 60.0\n"
         "fig, ax = plt.subplots(3, 2, figsize=(11, 10), sharex=True)\n"
         "ax[0,0].plot(tmin, ts['altitude']/1000, color='tab:grey')\n"
         "ax[0,0].set_ylabel('altitude [km]'); ax[0,0].set_title('mission profile')\n"
         "ax[0,1].plot(tmin, ts['thrust']/1e3, label='required')\n"
         "ax[0,1].plot(tmin, ts['thrust_available']/1e3, ls='--', label='available')\n"
         "ax[0,1].set_ylabel('thrust [kN]'); ax[0,1].set_title('thrust'); ax[0,1].legend(fontsize=8)\n"
         "ax[1,0].plot(tmin, ts['fuel_flow'], color='tab:red')\n"
         "ax[1,0].set_ylabel('fuel flow [kg/s]'); ax[1,0].set_title('fuel mass flow')\n"
         "ax[1,1].plot(tmin, ts['tsfc']*3600*9.80665, color='tab:purple')\n"
         "ax[1,1].set_ylabel('TSFC [lb/(lbf h)]'); ax[1,1].set_title('TSFC')\n"
         "if 'inlet_air_flow' in ts:\n"
         "    ax[2,0].plot(tmin, ts['inlet_air_flow'], color='tab:green', label='total (inlet)')\n"
         "if 'core_air_flow' in ts:\n"
         "    ax[2,0].plot(tmin, ts['core_air_flow'], ls='--', color='tab:olive',\n"
         "                 label='core (station 3)')\n"
         "ax[2,0].legend(fontsize=8)\n"
         "ax[2,0].set_ylabel('air flow [kg/s]'); ax[2,0].set_title('ingested air')\n"
         "ax[2,0].set_xlabel('time [min]')\n"
         "for k, c in (('EINOX','tab:red'), ('EICO','tab:blue'), ('EIUHC','tab:orange')):\n"
         "    if k in ts: ax[2,1].plot(tmin, ts[k], color=c, label=k)\n"
         "ax[2,1].set_yscale('log'); ax[2,1].set_ylabel('EI [g/kg fuel]')\n"
         "ax[2,1].set_title('emission indices'); ax[2,1].set_xlabel('time [min]')\n"
         "ax[2,1].legend(fontsize=8)\n"
         "for a in ax.ravel(): a.grid(alpha=0.3)\n"
         "fig.tight_layout(); plt.show()"),
    code("import numpy as np\n"
         "print(f\"mission duration      : {ts['time'][-1]/3600:8.2f} h\")\n"
         "print(f\"fuel, integrated here : {np.trapezoid(ts['fuel_flow'], ts['time']):8.0f} kg\")\n"
         "print(f\"fuel, weight loop     : {aircraft.weight.Wf:8.0f} kg   <- same number, two routes\")\n"
         "print()\n"
         "for k in ('NOX', 'CO', 'UHC'):\n"
         "    if k + '_kg' in ts:\n"
         "        print(f'{k:<4} emitted          : {ts[k+chr(95)+chr(107)+chr(103)][-1]:8.1f} kg')"),

    md("## 5. What sizes the engine\n\n"
       "A thrust-rated engine has three candidate sizing cases, and they are compared *after*\n"
       "being referred back to sea level through the thrust lapse — available thrust falls with\n"
       "both altitude and Mach, so the point that stresses the engine hardest is the one with the\n"
       "largest $F/\\lambda_T$, not the largest raw thrust.\n\n"
       "For a transport that is usually **top of climb**, which is the classic result. The\n"
       "turboprop equivalent is `report_class_ii_sizing()` in notebook 02."),
    code("rep = aircraft.powertrain.report_turbofan_sizing(warn=False)\n"
         "for k, v in sorted(rep['cases'].items(), key=lambda kv: -kv[1]):\n"
         "    mark = '  <-- sizing' if k == rep['sizing_case'] else ''\n"
         "    print(f'{k:<22}{v/1000:8.1f} kN SLS{mark}')\n"
         "print()\n"
         "print(f\"nominal thrust the map was read against: {rep['nominal']/1000:.1f} kN\")\n"
         "print(f\"ratio required/nominal                : {rep['nominal_ratio']:.3f}\")"),

    md("## 6. Validation against the real A320\n\n"
       "Reference data is sourced and cited in `validation/a320_reference.md`: MTOW, MZFW and the\n"
       "engine thrust rating are **certification** data (Airbus ACAP, EASA TCDS); wing area and OEW\n"
       "are secondary-source values and labelled as such.\n\n"
       "Two design points are worth comparing. The default one minimises **installed thrust**. But\n"
       "a narrow-body is sized by its **approach speed**: within the landing-field cap on wing\n"
       "loading, a smaller wing is lighter and has less drag, so take-off weight keeps falling\n"
       "right up to the wall. Minimum installed thrust is not minimum take-off weight."),
    code("import importlib.util, os\n"
         "_v = os.path.join('validation', 'a320_reference.py')\n"
         "if not os.path.exists(_v): _v = os.path.join('..', 'validation', 'a320_reference.py')\n"
         "spec = importlib.util.spec_from_file_location('a320ref', _v)\n"
         "a320 = importlib.util.module_from_spec(spec); spec.loader.exec_module(a320)\n"
         "wall = a320.landing_limited_wing_loading()\n"
         "print(f'landing-field wing-loading wall: {wall:.1f} kg/m^2')\n"
         "a320.compare(aircraft, 'A) default - minimum installed thrust')\n"
         "ac_land = a320._design(wall)\n"
         "a320.compare(ac_land, f'B) landing-limited (W/S = {wall:.1f} kg/m^2)')"),
    md("The wing-loading sweep below is the *evidence* for that claim rather than an assertion of\n"
       "it: take-off weight falls monotonically with wing loading until the landing wall stops it."),
    code("wall, sweep = a320.wing_loading_sweep()\n"
         "ws = [p[0] for p in sweep]; mt = [p[1] for p in sweep]\n"
         "fig, ax = plt.subplots(figsize=(7,4))\n"
         "ax.plot(ws, mt, 'o-', label='PhlyGreen')\n"
         "ax.axvline(wall, color='tab:red', ls='--', label='landing wall')\n"
         "ax.axvline(aircraft.DesignWTOoS/9.81, color='tab:blue', ls=':', label='min installed thrust')\n"
         "ax.axhline(73500, color='k', ls='-.', lw=1, label='A320 MTOW')\n"
         "ax.set_xlabel('wing loading [kg/m$^2$]'); ax.set_ylabel('MTOW [kg]')\n"
         "ax.grid(alpha=0.3); ax.legend(fontsize=9); plt.show()"),

    md("## 6b. Payload-range\n\n"
       "The payload-range diagram is the clearest single picture of what an airliner can do, and\n"
       "it needs something PhlyGreen does not normally do: an **off-design** calculation. The\n"
       "sizing loop always re-sizes the aircraft, so here the empty weight and the wing are held\n"
       "at the values the design converged on and only the fuel and take-off weight are solved\n"
       "for. Every point below is therefore the *same* aircraft flown differently.\n\n"
       "The curve has two legs:\n\n"
       "* a **flat leg** at the design payload. Out to the design range the aircraft is not\n"
       "  weight-limited — it simply carries less fuel for a shorter trip — so payload is\n"
       "  constant and range is free.\n"
       "* a **descending leg** beyond it. Take-off weight is now pinned at MTOW, so every extra\n"
       "  kilogram of fuel has to be paid for with a kilogram of payload.\n\n"
       "The corner between the two **is** the design mission, and that is the check: the aircraft\n"
       "was sized to carry 14 250 kg over 3000 nm, so 3000 nm is exactly where it runs out of\n"
       "take-off weight. Using the aircraft's own converged MTOW rather than the reference value\n"
       "is what makes that come out right.\n\n"
       "A real aircraft has a third limit — full tanks — which PhlyGreen does not model for\n"
       "kerosene. The A320's usable capacity is marked below for scale.\n\n"
       "*(This cell runs a few hundred mission integrations and takes a couple of minutes.)*"),
    code("oew_sized = ac_land.results().empty_weight\n"
         "mtow_own = ac_land.weight.WTO          # the aircraft's OWN converged take-off weight\n"
         "design_payload = config.mission.payload_weight\n"
         "pts, corner = a320.payload_range(oew_sized, mtow_own, wall, design_payload)\n"
         "print(f'OEW {oew_sized:8.0f} kg    MTOW {mtow_own:8.0f} kg')\n"
         "print(f'corner of the diagram : {corner[0]:6.0f} nm at {corner[1]:6.0f} kg')\n"
         "print(f'design mission        : {config.mission.range_mission:6.0f} nm at "
         "{design_payload:6.0f} kg\\n')\n"
         "for R, P in pts:\n"
         "    print(f'   {R:7.0f} nm   {P:8.0f} kg')"),
    code("max_fuel = 24209 * 0.785   # ACAP usable volume [l] x Jet-A density [kg/l]\n"
         "R = [p[0] for p in pts]; P = [p[1] for p in pts]\n"
         "fig, ax = plt.subplots(figsize=(7.5, 4.6))\n"
         "ax.plot(R, P, 'o-', color='tab:blue', label='PhlyGreen (off-design, MTOW limited)')\n"
         "ax.plot([corner[0]], [corner[1]], '*', ms=18, color='tab:green', zorder=5,\n"
         "        label=f'design mission ({design_payload:.0f} kg, "
         "{config.mission.range_mission:.0f} nm)')\n"
         "ax.axhline(design_payload, color='tab:grey', ls=':', lw=1)\n"
         "# where full tanks would cap it: the payload that leaves exactly max_fuel at MTOW\n"
         "pl_fuel_lim = mtow_own - oew_sized - max_fuel\n"
         "ax.axhline(pl_fuel_lim, color='tab:red', ls='--', lw=1,\n"
         "           label=f'full tanks ({max_fuel:.0f} kg usable, A320)')\n"
         "ax.annotate('constant payload:\\nnot weight limited', xy=(corner[0]*0.45, design_payload),\n"
         "            xytext=(corner[0]*0.30, design_payload*0.62), fontsize=8,\n"
         "            arrowprops=dict(arrowstyle='->', lw=0.8))\n"
         "ax.annotate('payload traded for fuel\\nat MTOW, ~1:1', xy=(R[-2], P[-2]),\n"
         "            xytext=(R[-2]*0.72, P[-2]*2.4), fontsize=8,\n"
         "            arrowprops=dict(arrowstyle='->', lw=0.8))\n"
         "ax.set_xlabel('range [nm]'); ax.set_ylabel('payload [kg]')\n"
         "ax.set_title('A320 payload-range (this design, flown off-design)')\n"
         "ax.set_ylim(0, design_payload*1.25); ax.set_xlim(0, max(R)*1.05)\n"
         "ax.grid(alpha=0.3); ax.legend(fontsize=8, loc='lower left'); plt.show()\n"
         "print('The corner sits on the design mission because the aircraft was sized for it.')\n"
         "print('Below the red line the real A320 would be out of tank volume; PhlyGreen has no')\n"
         "print('kerosene tank model, so the descending leg continues on weight alone.')"),

    md("### Empty weight, and two stated limits\n\n"
       "The Class-I empty-weight model used here is `'NarrowBody'`, a regression fitted to six\n"
       "in-service narrow-body transports (A319/A320/A321, B737-700/-800/-900ER), each reproduced\n"
       "within 2 %:\n\n"
       "$$W_e/W_0 = 4.2747\\,W_0^{-0.1844}$$\n\n"
       "It is a fit to a **population of aircraft**, not a calibration to this design's answer, so\n"
       "MTOW, wing area and installed thrust remain independent checks. Being an *empty*-weight\n"
       "fraction it already contains the installed engines, so the powertrain mass is not added on\n"
       "top of it (`avoid_powertrain_double_count`). The textbook Raymer jet fraction, by contrast,\n"
       "gives 0.495 at 78 t against ~0.546 for an A320-200 and is not used here.\n\n"
       "Two limits worth stating:\n\n"
       "* **FLOPS Class-II is rejected for turbofans** — its component set has no engine or pylon\n"
       "  mass and always adds a propeller. The component-scaler calibration used for turboprop\n"
       "  validations is not available here, and no mass breakdown below Class-I is claimed.\n"
       "* The engine map is validated to **35 000 ft**; queries above it are clipped, which is\n"
       "  *optimistic on available thrust*. The mission cruises at FL330 with the ceiling\n"
       "  requirement at FL350, both inside the box."),

    md("## 7. Emissions: a jet burns differently\n\n"
       "The emission *index* depends on the combustor operating point, so it is engine-size\n"
       "independent but **not** engine-class independent. A turbofan runs a hotter, richer\n"
       "combustor than a turboprop (FAR 0.015–0.029 against 0.009–0.017), and the table below\n"
       "shows the consequence: at high thrust the turbofan index is the larger of the two, while\n"
       "at low load the turboprop's is higher. Read the absolute values with care — the turboprop\n"
       "map is certification-*anchored* (its level is asserted from ICAO), whereas the turbofan\n"
       "map is unanchored and predicts its own level to about 26 % rms at the ICAO LTO points.\n\n"
       "PhlyGreen therefore ships two emission-index maps and picks by configuration — the\n"
       "turboprop one is keyed on a shaft-power fraction, the turbofan one on a **thrust** fraction."),
    code("from PhlyGreen.Systems.Powertrain.emissions_surrogate import (\n"
         "    EmissionSurrogate, default_model_path)\n"
         "tf = EmissionSurrogate(default_model_path('Turbofan'))\n"
         "tp = EmissionSurrogate(default_model_path('Traditional'))\n"
         "print(f\"{'thrust/power fraction':<24}{'turbofan EINOx':>16}{'turboprop EINOx':>18}\")\n"
         "for pc in (0.30, 0.55, 0.85, 1.00):\n"
         "    a = tf.predict_op(0.0, 0.25, pc)['EINOX']\n"
         "    b = tp.predict_op(0.0, 0.25, pc)['EINOX']\n"
         "    print(f'{pc:<24.2f}{a:>16.2f}{b:>18.2f}')"),
    md("Integrated over the mission, with the CO₂/H₂O/soot indices unchanged:"),
    code("from PhlyGreen.config import ClimateImpactConfig\n"
         "cfg2 = turbofan_config()\n"
         "cfg2.climate_impact = ClimateImpactConfig(H=100, N=1.6e7, Y=30,\n"
         "                                          einox_model='Surrogate',\n"
         "                                          wtw_co2=8.30e-3, grid_co2=9.36e-2)\n"
         "jet = pg.build_aircraft(); jet.configure(cfg2)\n"
         "jet.MissionType = 'Continue'   # the EI surrogate integrates the continuous mission\n"
         "jet.climateimpact.calculate_mission_emissions()\n"
         "e = jet.climateimpact.mission_emissions\n"
         "for k in ('co2', 'nox', 'co', 'uhc'):\n"
         "    if k in e: print(f'{k.upper():<5}{e[k]:10.1f} kg per mission')"),

    md("## 8. Summary — what actually differs from the regional turboprop\n\n"
       "| | ATR42 turboprop | A320 turbofan |\n"
       "|---|---|---|\n"
       "| installed rating | shaft power [W] | **thrust [N]** |\n"
       "| constraint diagram | P/W vs W/S | **T/W vs W/S** |\n"
       "| lapse | $(\\rho/\\rho_0)^{0.75}$, altitude only | **fitted $\\lambda_T(h, M)$**, Mach too |\n"
       "| powertrain graph | GT × gearbox × propeller | **one $\\eta_o$ node** (= a TSFC closure) |\n"
       "| drag polar | quadratic, no wave drag | **Korn/Lock compressible** |\n"
       "| engine mass | peak shaft power / (W/kg) | **SLS thrust / (g · T/W)** |\n"
       "| sizing case | take-off or climb peak power | **top of climb**, thrust referred to SLS |\n"
       "| EI map | PW127, shaft-power fraction | **CFM56-class, thrust fraction** |\n"
       "| weight class | Class-I or FLOPS Class-II | **Class-I only** (FLOPS has no engine mass) |\n\n"
       "What does *not* change is the aerodynamic core: `PoWTO` was always thrust power, which is\n"
       "why the same mission integrator, weight loop and climate model serve both aircraft."),
])

print("done")
