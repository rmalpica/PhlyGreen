"""Example 18 — Serial range-extender vs parallel hybrid, with the Class-II gas turbine.

A *serial* hybrid decouples the gas turbine from the propeller: the turbine spins a generator
and an electric motor drives the propeller. Flown as a **range extender**, the turbine runs at a
constant (full-throttle) shaft power for the whole mission while the **battery buffers** the
mismatch with propulsive demand — discharging when demand is high (climb, take-off) and
*recharging* from the turbine surplus when demand is low (cruise, descent). This is the new
``SerialRangeExtenderConfiguration`` mission mode (triggered by a ``gt_rated_power`` input on a
Serial hybrid).

The point of interest is the **Class-II, operating-point-dependent gas-turbine efficiency**
(`eta_gas_turbine_model='ResponseSurface'`): a turbine is most efficient near full load and loses
efficiency at part load. A *parallel* turbine is tied to the propeller and follows the (varying)
demand; a *serial* range-extender turbine stays at its chosen rated load. So the serial layout
*should* keep the turbine more efficient — the question this example answers honestly is whether
that gain is worth the price.

It is **not free**: the serial chain pays two extra electrical conversions (generator + motor,
~10% together) and carries a battery + a turbine sized for the rated power. We compare the two on
the same mission, **at a charge-sustaining battery** (net battery energy ≈ 0, so the fuel
comparison is fair and not secretly burning stored ground energy).

Result (baseline ATR-like mission, high-altitude cruise): the serial turbine does run a little
more efficiently, but **not nearly enough** to pay back the conversion + mass penalties — it burns
more fuel. The serial advantage only appears when the parallel turbine would otherwise run at deep
part load; the altitude lapse keeps an efficient cruise turbine well loaded, so it does not here.

Run it:
    cd trunk && python examples/18_serial_range_extender_gt.py
"""

import numpy as np

import PhlyGreen as pg
from common import hybrid_config, savefig, OUTPUT_DIR

from PhlyGreen.Systems.Powertrain.gas_turbine_surrogate import (
    GasTurbineResponseSurface, _isa_pressure_ratio)
import PhlyGreen.Utilities.Units as Units

# A turbine nominal/rated power [W]. The parallel turbine is sized for the installed (peak) power;
# the serial range-extender turbine is set to GT_RATED and run at full throttle the whole mission.
GT_DESIGN_PARALLEL = 3.2e6     # parallel installed gas-turbine power [W]
GT_RATED_SERIAL = 3.0e6        # serial range-extender constant turbine power [W] (~charge-sustaining)


def parallel_turboprop():
    """A conventional parallel layout flown as a pure turboprop (no battery assist): the gas
    turbine alone drives the propeller and follows the propulsive demand."""
    cfg = hybrid_config(battery_class='I', hybrid_type='Parallel')
    for s in cfg.mission_stages.segments:                  # phi = 0 everywhere -> turbine-only
        s.phi, s.phi_start, s.phi_end = 0.0, 0.0, 0.0
    cfg.energy.eta_gas_turbine_model = 'ResponseSurface'
    cfg.energy.gt_design_power = GT_DESIGN_PARALLEL
    a = pg.build_aircraft()
    a.configure(cfg)
    return a


def serial_range_extender():
    """A serial range-extender: constant-power turbine + recharging battery buffer."""
    cfg = hybrid_config(battery_class='I', hybrid_type='Serial')
    cfg.energy.eta_gas_turbine_model = 'ResponseSurface'
    cfg.energy.gt_design_power = GT_RATED_SERIAL           # turbine sized for its rated power
    cfg.energy.gt_rated_power = GT_RATED_SERIAL            # ...and run at it (full throttle)
    cfg.energy.battery_charge_efficiency = 0.96            # in-flight recharge efficiency
    a = pg.build_aircraft()
    a.configure(cfg)
    return a


def _mission_trajectory(m):
    """Time and mass-fraction (Beta) over the whole mission, from the per-segment solutions
    (``m.Beta`` holds only the last segment, so reconstruct the full arrays here)."""
    t = np.concatenate([s.t for s in m.integral_solution])
    beta = np.concatenate([s.y[-1] for s in m.integral_solution])   # Beta is the last ODE state
    return t, beta


def _mission_gt_efficiency(aircraft, serial):
    """Mission-average gas-turbine efficiency actually seen by a sized design."""
    m, pt = aircraft.mission, aircraft.powertrain
    t_all, beta_all = _mission_trajectory(m)
    etas = []
    for t, beta in zip(t_all, beta_all):
        alt, vel = m.profile.Altitude(t), m.profile.Velocity(t)
        P_prop = aircraft.weight.WTO * aircraft.performance.PoWTO(
            aircraft.DesignWTOoS, beta, m.profile.PowerExcess(t), 1, alt, m.DISA, vel, 'TAS')
        if serial:                                          # turbine at full throttle, lapsed
            P_gt = min(GT_RATED_SERIAL, GT_RATED_SERIAL * _isa_pressure_ratio(Units.mToft(alt)))
        else:                                               # parallel turbine follows the demand
            P_gt = P_prop
        etas.append(pt.eta('gas_turbine', alt, vel, P_gt))
    return float(np.mean(etas))


def main():
    par = parallel_turboprop()
    ser = serial_range_extender()

    eta_par = _mission_gt_efficiency(par, serial=False)
    eta_ser = _mission_gt_efficiency(ser, serial=True)
    net_batt_kWh = ser.mission.EBat[-1] / 3.6e6 / 1000.0    # net energy drawn from the battery

    print("Serial range-extender vs parallel turboprop (Class-II gas turbine, same mission)")
    print(f"  {'quantity':28s} {'Parallel':>10s} {'Serial RE':>10s}")
    print(f"  {'Take-off weight [kg]':28s} {par.weight.WTO:10.0f} {ser.weight.WTO:10.0f}")
    print(f"  {'Mission fuel [kg]':28s} {par.weight.Wf:10.0f} {ser.weight.Wf:10.0f}")
    print(f"  {'Battery mass [kg]':28s} {0.0:10.0f} {ser.weight.WBat:10.0f}")
    print(f"  {'Mean gas-turbine eta [-]':28s} {eta_par:10.3f} {eta_ser:10.3f}")
    print(f"  {'Net battery energy [kWh]':28s} {0.0:10.1f} {net_batt_kWh:10.2f}  (~0 => charge-sustaining)")
    verdict = "less" if ser.weight.Wf < par.weight.Wf else "MORE"
    print(f"\n  The serial range-extender keeps the turbine a little more efficient "
          f"({eta_ser:.3f} vs {eta_par:.3f}),")
    print(f"  but burns {verdict} fuel ({ser.weight.Wf:.0f} vs {par.weight.Wf:.0f} kg): the "
          f"generator+motor conversions and the")
    print(f"  battery/turbine mass outweigh the small efficiency gain on this efficient-cruise mission.")

    print("\nFigures:")
    _plot_gt_map(par, ser, "18_gt_partload.png")
    _plot_serial_power(ser, "18_serial_power_split.png")

    # Try it: lower the cruise altitude in common._mission_stages() (e.g. 8000 -> 2000 m). At low
    # altitude the turbine's available power is high, so the *parallel* turbine cruises at low part
    # load (inefficient) — and the serial range-extender's advantage grows. The crossover is the
    # whole lesson: serial hybridization pays off only when the thermal engine would otherwise run
    # badly part-loaded.


def _plot_gt_map(par, ser, name):
    """The Class-II turbine efficiency vs load fraction, with where each design's turbine sits."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    s = GasTurbineResponseSurface()
    design_hp = Units.wTohp(GT_RATED_SERIAL)
    fracs = np.linspace(0.1, 1.0, 19)
    # efficiency vs fraction-of-available-power at a representative cruise altitude (8000 m)
    alt_ft, delta = Units.mToft(8000.0), _isa_pressure_ratio(Units.mToft(8000.0))
    eta = [s.predict(design_hp, alt_ft, 0.4, f * design_hp * delta)[0] for f in fracs]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(fracs * 100, eta, "-o", ms=3, label="turbine efficiency map (8000 m)")
    ax.axvspan(40, 75, color="orange", alpha=0.12, label="typical parallel cruise (part load)")
    ax.axvline(100, color="green", ls="--", lw=1, label="serial range-extender (full load)")
    ax.set_xlabel("turbine load [% of available power]")
    ax.set_ylabel("thermal efficiency [-]")
    ax.set_title("Class-II gas-turbine efficiency vs load\n(serial keeps it near full load; parallel runs part-loaded)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    savefig(fig, name)
    plt.close(fig)


def _plot_serial_power(aircraft, name):
    """Mission power split of the serial range-extender: constant turbine, battery buffering."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    m = aircraft.mission
    t, beta = _mission_trajectory(m)
    alt = np.array([m.profile.Altitude(tt) for tt in t])
    P_prop = np.array([aircraft.weight.WTO * aircraft.performance.PoWTO(
        aircraft.DesignWTOoS, b, m.profile.PowerExcess(tt), 1, m.profile.Altitude(tt),
        m.DISA, m.profile.Velocity(tt), 'TAS') for tt, b in zip(t, beta)])
    P_gt = np.array([min(GT_RATED_SERIAL, GT_RATED_SERIAL * _isa_pressure_ratio(Units.mToft(a)))
                     for a in alt])
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.5, 6), sharex=True)
    ax1.plot(t / 60, P_prop / 1e6, label="propulsive demand")
    ax1.plot(t / 60, P_gt / 1e6, label="gas turbine (full throttle, lapsed)")
    ax1.fill_between(t / 60, P_gt / 1e6, P_prop / 1e6, where=P_prop > P_gt, alpha=0.2,
                     color="red", label="battery discharges")
    ax1.fill_between(t / 60, P_gt / 1e6, P_prop / 1e6, where=P_prop <= P_gt, alpha=0.2,
                     color="green", label="battery recharges (surplus)")
    ax1.set_ylabel("power [MW]")
    ax1.set_title("Serial range-extender: turbine at full power, battery buffers the rest")
    ax1.legend(fontsize=8, loc="upper right")
    ax1.grid(alpha=0.3)
    ax2.plot(t / 60, alt, color="gray")
    ax2.set_ylabel("altitude [m]")
    ax2.set_xlabel("time [min]")
    ax2.grid(alpha=0.3)
    fig.tight_layout()
    savefig(fig, name)
    plt.close(fig)


if __name__ == "__main__":
    main()
