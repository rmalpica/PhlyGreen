"""Example 16 — Sizing the Class-II gas turbine and electric motor.

The Class-II gas-turbine and electric-motor models are response surfaces / physics models
that work as a *percentage of a fixed nominal (design) power*. That nominal power must be
chosen **before** the mission — an engine cannot resize itself at every instant. So the
workflow is:

1. get a tentative nominal power. A good first guess is ``DesignPW * WTO`` (design
   power-to-weight times take-off weight), which we obtain from a quick Class-I pre-pass;
2. fix that nominal power and run the Class-II design;
3. after sizing, compare the *peak absorbed* power to the nominal — if the component is
   undersized (peak demand exceeds nominal) a warning is raised; if it is much larger than
   needed, the report flags it as oversized so you can shrink it.

Run it:
    cd trunk && python examples/16_class_ii_propulsion_sizing.py
"""

import warnings

import PhlyGreen as pg
from common import traditional_config, hybrid_config


def _design(config):
    aircraft = pg.build_aircraft()
    aircraft.PropellerInput = {'Number of Engines': 2}   # an ATR has two engines
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")   # we read the sizing report explicitly instead
        aircraft.configure(config)
    return aircraft


def gas_turbine():
    print("=== Class-II gas turbine (response surface) ===")
    # 1. Class-I pre-pass for a tentative nominal power = DesignPW * WTO.
    pre = _design(traditional_config())
    p_nominal = pre.DesignPW * pre.weight.WTO
    print(f"pre-pass: WTO = {pre.weight.WTO:.0f} kg, DesignPW = {pre.DesignPW:.1f} W/kg")
    print(f"tentative GT nominal = DesignPW * WTO = {p_nominal/1e3:.0f} kW")

    # 2. Design with the tentative nominal; the altitude-aware check may flag power-limiting.
    cfg = traditional_config()
    cfg.energy.eta_gas_turbine_model = 'ResponseSurface'
    cfg.energy.gt_design_power = p_nominal
    rep = _design(cfg).powertrain.report_class_ii_sizing()['gas turbine']
    print(f"tentative design: worst load ratio {rep['worst_load_ratio']:.2f}, "
          f"power-limited = {rep['power_limited']}  ->  {rep['status']}")
    print(f"  (available power lapses with altitude; need >= {rep['min_nominal']/1e3:.0f} kW)")

    # 3. Re-size the gas turbine so it is no longer power-limited at altitude.
    cfg.energy.gt_design_power = 1.05 * rep['min_nominal']
    aircraft = _design(cfg)
    rep2 = aircraft.powertrain.report_class_ii_sizing()['gas turbine']
    print(f"re-sized: nominal {rep2['nominal']/1e3:.0f} kW, worst load ratio "
          f"{rep2['worst_load_ratio']:.2f}  ->  {rep2['status']}")
    print(f"  WTO = {aircraft.weight.WTO:.0f} kg, mission fuel = {aircraft.weight.Wf:.1f} kg")


def electric_motor():
    print("\n=== Class-II electric motor (d-q model) ===")
    pre = _design(hybrid_config(battery_class='I'))
    p_nominal = pre.DesignPW * pre.weight.WTO
    print(f"tentative EM nominal = DesignPW * WTO = {p_nominal/1e3:.0f} kW")

    cfg = hybrid_config(battery_class='I')
    cfg.energy.eta_electric_motor_model = 'Smart'
    cfg.energy.em_design_power = p_nominal
    cfg.energy.em_design_voltage = 800.0
    cfg.energy.em_design_rpm = 11000.0
    rep = _design(cfg).powertrain.report_class_ii_sizing()['electric motor']
    print(f"EM sizing: nominal {rep['nominal']/1e3:.0f} kW, peak {rep['peak_demand']/1e3:.0f} kW "
          f"-> {rep['status']} (load ratio {rep['worst_load_ratio']:.2f})")
    print("(the tentative DesignPW*WTO is generous for the motor, which only carries the "
          "battery share — the 'oversized' flag says you can reduce its nominal power.)")


if __name__ == "__main__":
    gas_turbine()
    electric_motor()
