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
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        aircraft.configure(config)
    sizing_warnings = [str(w.message) for w in caught if "undersized" in str(w.message)]
    return aircraft, sizing_warnings


def gas_turbine():
    print("=== Class-II gas turbine (response surface) ===")
    # 1. Class-I pre-pass for a tentative nominal power = DesignPW * WTO.
    pre, _ = _design(traditional_config())
    p_nominal = pre.DesignPW * pre.weight.WTO
    print(f"pre-pass: WTO = {pre.weight.WTO:.0f} kg, DesignPW = {pre.DesignPW:.1f} W/kg")
    print(f"tentative GT nominal power = DesignPW * WTO = {p_nominal/1e3:.0f} kW")

    # 2. Class-II GT design at the fixed nominal power.
    cfg = traditional_config()
    cfg.energy.eta_gas_turbine_model = 'ResponseSurface'
    cfg.energy.gt_design_power = p_nominal
    aircraft, _ = _design(cfg)
    rep = aircraft.powertrain.report_class_ii_sizing()['gas turbine']
    print(f"design: WTO = {aircraft.weight.WTO:.0f} kg, mission fuel = {aircraft.weight.Wf:.1f} kg")
    print(f"GT sizing: nominal {rep['nominal']/1e3:.0f} kW, peak absorbed "
          f"{rep['actual']/1e3:.0f} kW  ->  {rep['status']} (ratio {rep['ratio']:.2f})")

    # 3. What an undersized choice looks like (half the nominal power).
    cfg.energy.gt_design_power = 0.5 * p_nominal
    _, warns = _design(cfg)
    print(f"undersized (half nominal): {warns[0] if warns else 'no warning'}")


def electric_motor():
    print("\n=== Class-II electric motor (d-q model) ===")
    pre, _ = _design(hybrid_config(battery_class='I'))
    p_nominal = pre.DesignPW * pre.weight.WTO
    print(f"tentative EM nominal power = DesignPW * WTO = {p_nominal/1e3:.0f} kW")

    cfg = hybrid_config(battery_class='I')
    cfg.energy.eta_electric_motor_model = 'Smart'
    cfg.energy.em_design_power = p_nominal
    cfg.energy.em_design_voltage = 800.0
    cfg.energy.em_design_rpm = 11000.0
    aircraft, _ = _design(cfg)
    rep = aircraft.powertrain.report_class_ii_sizing()['electric motor']
    print(f"design: WTO = {aircraft.weight.WTO:.0f} kg")
    print(f"EM sizing: nominal {rep['nominal']/1e3:.0f} kW, peak absorbed "
          f"{rep['actual']/1e3:.0f} kW  ->  {rep['status']} (ratio {rep['ratio']:.2f})")
    print("(the tentative DesignPW*WTO is generous for the motor, which only carries the "
          "battery share — the 'oversized' flag says to reduce its nominal power.)")


if __name__ == "__main__":
    gas_turbine()
    electric_motor()
