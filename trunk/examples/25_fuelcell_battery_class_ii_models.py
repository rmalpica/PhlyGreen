"""Example 25 — Fuel-cell + battery with Class-II battery, electric motor and propeller.

The fuel-cell + battery hybrid can be sized with the *physics* Class-II component models, not just
the simple Class-I constants:

* **battery** — the cell-level electro-thermal model (P-number sized; the mission integrates the
  pack charge and temperature and enforces the SOC / voltage / current limits);
* **electric motor** — the d-q ("Smart") motor model, so the motor efficiency varies with the
  operating point;
* **propeller** — the analytic Hamilton-Standard model, so the propeller efficiency varies with
  airspeed / altitude / power.

The battery here is used for **peak power** — it covers part of the take-off and climb power and
nothing in cruise — so the fuel cell is sized for the (lower) cruise power and the take-off weight
comes down.

This script sizes such a design and plots the relevant time series: the flight profile, the
fuel-cell / battery power split, the battery state of charge and temperature, and the electric-motor
and propeller efficiencies along the mission.

Run it:
    cd trunk && python examples/25_fuelcell_battery_class_ii_models.py
"""

import warnings

import PhlyGreen as pg
import PhlyGreen.Utilities.Units as Units
from PhlyGreen.config import CellConfig
from common import fuelcell_battery_config, print_results, savefig


TAKEOFF_CLIMB_PHI = 0.30  # battery covers part of the take-off/climb power peak; cruise on H2 alone
RANGE_NM = 500            # a short regional hop (a longer range snowballs with a realistic battery)


def _base_config():
    """Fuel-cell + battery with a Class-II battery, hybridised for **peak power**.

    The battery supplies a share (``TAKEOFF_CLIMB_PHI``) of the take-off and climb power and
    *nothing* in cruise, so the fuel cell is sized for the lower cruise power (a smaller, lighter
    stack) and the battery only needs energy for the short high-power phases — both push the
    take-off weight down relative to hybridising the (long) cruise.
    """
    cfg = fuelcell_battery_config(cruise_phi=0.0)
    cfg.mission.range_mission = RANGE_NM
    for s in cfg.mission_stages.segments:
        if s.name == 'Takeoff':
            s.phi, s.phi_start, s.phi_end = TAKEOFF_CLIMB_PHI, None, None
        elif s.segment_type == 'ConstantRateClimb':
            s.phi, s.phi_start, s.phi_end = None, TAKEOFF_CLIMB_PHI, TAKEOFF_CLIMB_PHI
        elif s.segment_type == 'ConstantMachCruise':
            s.phi, s.phi_start, s.phi_end = None, 0.0, 0.0
    cfg.cell = CellConfig(cell_class='II', model='Finger-Cell-Thermal',
                          specific_power=8000, specific_energy=250, minimum_soc=0.2,
                          pack_voltage=800, initial_temperature=25, max_operative_temperature=50)
    return cfg


def _config(em_design_power):
    """Add the Class-II electric motor (d-q) and propeller (Hamilton) to the base config.

    ``em_design_power`` must cover the peak propulsive power (take-off / climb), otherwise the
    d-q motor model reports the motor as overloaded — so we size it from a pre-pass below.
    """
    cfg = _base_config()
    cfg.energy.eta_electric_motor_model = 'Smart'
    cfg.energy.em_design_power = float(em_design_power)
    cfg.energy.em_design_voltage = 800.0
    cfg.energy.em_design_rpm = 11000.0
    cfg.energy.eta_propulsive_model = 'Hamilton'
    return cfg


# The Hamilton-Standard propeller needs a full geometry definition.
PROPELLER_INPUT = {
    'Propeller Diameter': Units.ftTom(13), 'RPM': 13820 / 13, 'N_ENGINES': 2.,
    'N_BLADES': 6, 'ACTIVITY_FACTOR': 167, 'INTEGRATED_LIFT_COEFFICIENT': 0.5,
}


def _design():
    # Pre-pass: size the design with the simple (constant) component models to get a tentative
    # nominal motor power = DesignPW * WTO, then size the motor generously (1.5x) so it stays
    # within range over the whole mission for the (heavier) Class-II design.
    pre = pg.build_aircraft()
    pre.PropellerInput = PROPELLER_INPUT
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        pre.configure(_base_config())
    em_design_power = 1.5 * pre.DesignPW * pre.weight.WTO
    print(f"pre-pass: WTO {pre.weight.WTO:.0f} kg, DesignPW {pre.DesignPW:.0f} W/kg "
          f"-> motor nominal {em_design_power/1e6:.1f} MW")

    aircraft = pg.build_aircraft()
    aircraft.PropellerInput = PROPELLER_INPUT
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        aircraft.configure(_config(em_design_power))
    return aircraft


def _timeseries(aircraft):
    """Walk the sized mission and return per-instant arrays for the plots."""
    import numpy as np
    import PhlyGreen.Utilities.Speed as Speed

    m, pt, b = aircraft.mission, aircraft.powertrain, aircraft.battery
    WTO, WS, DISA = aircraft.weight.WTO, aircraft.DesignWTOoS, m.DISA
    t = np.concatenate([s.t for s in m.integral_solution])
    beta = np.concatenate([s.y[2] for s in m.integral_solution])   # mass fraction
    it = np.concatenate([s.y[3] for s in m.integral_solution])     # spent charge [As]
    T = np.concatenate([s.y[4] for s in m.integral_solution])      # battery temperature [K]

    alt = np.array([float(m.profile.Altitude(x)) for x in t])
    vel = np.array([float(m.profile.Velocity(x)) for x in t])
    phi = np.array([float(m.profile.SuppliedPowerRatio(x)) for x in t])
    PP = np.array([WTO * aircraft.performance.PoWTO(WS, beta[i], m.profile.PowerExcess(t[i]), 1,
                                                    alt[i], DISA, vel[i], 'TAS')
                   for i in range(len(t))])
    p_fc, p_bat = (1.0 - phi) * PP, phi * PP
    soc = 1.0 - (it / 3600.0) / (b.cell_capacity * b.P_number)       # pack state of charge
    # The motor and propeller carry the *total* propulsive power (the fuel cell and battery feed a
    # common electric motor -> gearbox -> propeller), so read their efficiencies at PP.
    eta_em = np.array([pt.eta('electric_motor', alt[i], vel[i], max(PP[i], 1.0))
                       for i in range(len(t))])
    eta_prop = np.array([pt.Propeller.ComputePropEfficiency(alt[i], vel[i], max(PP[i], 1.0))
                         for i in range(len(t))])
    return dict(t=t / 60.0, alt=alt, vel=vel, p_fc=p_fc, p_bat=p_bat,
                soc=soc, Tc=T - 273.15, eta_em=eta_em, eta_prop=eta_prop)


def _plot(ts, name, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(2, 2, figsize=(13, 8))
    fig.suptitle(title, fontsize=13)

    a = ax[0, 0]
    a.plot(ts['t'], ts['alt'], color='tab:blue'); a.set_ylabel('altitude [m]', color='tab:blue')
    av = a.twinx(); av.plot(ts['t'], ts['vel'], color='tab:orange')
    av.set_ylabel('TAS [m/s]', color='tab:orange'); a.set_title('Flight profile'); a.grid(alpha=0.3)

    a = ax[0, 1]
    a.plot(ts['t'], ts['p_fc'] / 1e3, color='tab:red', label='fuel cell')
    a.plot(ts['t'], ts['p_bat'] / 1e3, color='tab:green', label='battery')
    a.set_ylabel('propulsive power [kW]'); a.set_title('Power split'); a.legend(); a.grid(alpha=0.3)

    a = ax[1, 0]
    a.plot(ts['t'], 100 * ts['soc'], color='tab:purple'); a.set_ylabel('battery SOC [%]', color='tab:purple')
    at = a.twinx(); at.plot(ts['t'], ts['Tc'], color='tab:brown')
    at.set_ylabel('battery T [°C]', color='tab:brown'); a.set_xlabel('time [min]')
    a.set_title('Battery state of charge & temperature'); a.grid(alpha=0.3)

    a = ax[1, 1]
    a.plot(ts['t'], 100 * ts['eta_em'], color='tab:blue', label='electric motor')
    a.plot(ts['t'], 100 * ts['eta_prop'], color='tab:green', label='propeller')
    a.set_ylabel('efficiency [%]'); a.set_xlabel('time [min]')
    a.set_title('Class-II component efficiencies'); a.legend(); a.grid(alpha=0.3)

    fig.tight_layout()
    print("Figures:")
    savefig(fig, name)
    plt.close(fig)


def main():
    print("=== Fuel-cell + battery with Class-II battery / motor / propeller ===")
    aircraft = _design()
    print_results(aircraft, "FC + battery (Class-II battery, Smart EM, Hamilton propeller)")
    try:
        ts = _timeseries(aircraft)
        _plot(ts, "25_fuelcell_battery_class_ii.png",
              "FC + battery — Class-II battery / motor / propeller")
    except Exception as exc:
        print(f"  (time-series plot skipped: {type(exc).__name__}: {exc})")


if __name__ == "__main__":
    main()
