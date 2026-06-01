"""Generic post-processing and plotting helpers for a designed aircraft.

After ``aircraft.configure(config)`` (or ``pg.run_design``), these functions extract the
mission time histories and produce the common plots — the flight profile, the energy
time-series, the constraint diagram, the mass breakdown, and the LH2 tank state — for any
configuration (Traditional / Hybrid / Hydrogen / FuelCellBattery). Plot helpers accept an
optional matplotlib ``ax`` and return it, so they compose into dashboards/notebooks.

matplotlib is imported lazily; only :func:`mission_timeseries` works without it.
"""

import numpy as np


def mission_timeseries(aircraft):
    """Extract mission time histories into a dict of equal-length numpy arrays.

    Keys always present: ``time`` [s], ``altitude`` [m], ``velocity`` [m/s] (TAS),
    ``power_excess`` [m/s], ``mass_fraction`` (Beta), ``fuel_energy`` [J] (cumulative;
    hydrogen chemical energy for the Hydrogen/FuelCellBattery configurations). Present for
    hybrids: ``battery_energy`` [J] and (approximate) ``soc``. Present for hybrids: ``phi``.
    """
    mission = aircraft.mission
    profile = mission.profile
    sols = mission.integral_solution
    if not sols:
        raise ValueError("No mission solution found — design the aircraft first.")

    time = np.concatenate([s.t for s in sols])
    y_fuel = np.concatenate([s.y[0] for s in sols])
    beta = np.concatenate([s.y[-1] for s in sols])

    out = {
        "time": time,
        "altitude": np.array([float(profile.Altitude(t)) for t in time]),
        "velocity": np.array([float(profile.Velocity(t)) for t in time]),
        "power_excess": np.array([float(profile.PowerExcess(t)) for t in time]),
        "mass_fraction": beta,
        "fuel_energy": y_fuel,
    }

    config = getattr(aircraft, "Configuration", None)
    if config in ("Hybrid", "FuelCellBattery"):
        out["phi"] = np.array([float(profile.SuppliedPowerRatio(t)) for t in time])

    # Battery energy time-series exists as an ODE state only for the Hybrid configuration.
    if config == "Hybrid" and sols[0].y.shape[0] >= 3:
        out["battery_energy"] = np.concatenate([s.y[1] for s in sols])
        pack_energy = getattr(aircraft.battery, "pack_energy", None)
        if pack_energy:
            out["soc"] = np.clip(1.0 - out["battery_energy"] / pack_energy, 0.0, 1.0)

    return out


def plot_mission_profile(aircraft, axes=None):
    """Plot altitude, true airspeed and (for hybrids) phi versus time."""
    import matplotlib.pyplot as plt
    ts = mission_timeseries(aircraft)
    t_min = ts["time"] / 60.0
    has_phi = "phi" in ts
    n = 3 if has_phi else 2
    if axes is None:
        _, axes = plt.subplots(n, 1, sharex=True, figsize=(8, 2.4 * n))
    axes[0].plot(t_min, ts["altitude"], color="tab:blue")
    axes[0].set_ylabel("altitude [m]")
    axes[1].plot(t_min, ts["velocity"], color="tab:orange")
    axes[1].set_ylabel("TAS [m/s]")
    if has_phi:
        axes[2].plot(t_min, ts["phi"], color="tab:green")
        axes[2].set_ylabel("phi [-]")
    axes[-1].set_xlabel("time [min]")
    for ax in axes:
        ax.grid(alpha=0.3)
    return axes


def plot_energy_timeseries(aircraft, ax=None):
    """Plot cumulative fuel (and battery) energy, and SOC if available, versus time."""
    import matplotlib.pyplot as plt
    ts = mission_timeseries(aircraft)
    t_min = ts["time"] / 60.0
    if ax is None:
        _, ax = plt.subplots(figsize=(8, 4))
    ax.plot(t_min, ts["fuel_energy"] / 1e6, color="tab:red", label="fuel / H2 energy")
    if "battery_energy" in ts:
        ax.plot(t_min, ts["battery_energy"] / 1e6, color="tab:blue", label="battery energy")
    ax.set_xlabel("time [min]"); ax.set_ylabel("cumulative energy [MJ]")
    ax.grid(alpha=0.3)
    if "soc" in ts:
        ax2 = ax.twinx()
        ax2.plot(t_min, ts["soc"], color="tab:green", ls="--", label="SOC")
        ax2.set_ylabel("state of charge [-]")
    ax.legend(loc="upper left")
    return ax


def plot_constraint_diagram(aircraft, ax=None):
    """Plot the constraint diagram (P/W vs W/S) with the design point."""
    import matplotlib.pyplot as plt
    c = aircraft.constraint
    if ax is None:
        _, ax = plt.subplots(figsize=(7, 5))
    curves = [
        ("Cruise", "PWCruise"), ("Take Off", "PWTakeOff"), ("AEO Climb", "PWAEOClimb"),
        ("OEI Climb", "PWOEIClimb"), ("Turn", "PWTurn"), ("Ceiling", "PWCeiling"),
        ("Acceleration", "PWAcceleration"),
    ]
    for label, attr in curves:
        y = getattr(c, attr, None)
        if y is not None:
            ax.plot(c.WTOoS, y, label=label)
    if getattr(c, "PWLanding", None) is not None and getattr(c, "WTOoSLanding", None) is not None:
        ax.plot(c.WTOoSLanding, c.PWLanding, label="Landing")
    try:
        ax.plot(aircraft.DesignWTOoS, aircraft.DesignPW, "o", ms=10,
                mfc="red", mec="black", label="design point", zorder=5)
    except Exception:
        pass
    ax.set_xlabel(r"$W_{TO}/S$ [N/m$^2$]"); ax.set_ylabel(r"$P/W_{TO}$ [W/kg]")
    ax.set_ylim(bottom=0); ax.grid(alpha=0.3); ax.legend(fontsize=8)
    return ax


def mass_breakdown(aircraft):
    """Return an ordered ``{component: mass_kg}`` dict (omitting absent/zero items)."""
    w = aircraft.weight
    items = [
        ("structure", getattr(w, "WStructure", None)),
        ("powertrain", getattr(w, "WPT", None)),
        ("battery", getattr(w, "WBat", None)),
        ("fuel / H2", getattr(w, "Wf", None)),
        ("H2 tank", getattr(w, "WTank", None)),
        ("cooling", getattr(w, "WHeat_Exchanger", None)),
        ("payload", getattr(w, "WPayload", None)),
        ("crew", getattr(w, "WCrew", None)),
        ("reserve", getattr(w, "final_reserve", None)),
    ]
    return {name: float(v) for name, v in items if v not in (None, 0, 0.0)}


def plot_mass_breakdown(aircraft, ax=None):
    """Bar chart of the take-off mass breakdown."""
    import matplotlib.pyplot as plt
    masses = mass_breakdown(aircraft)
    if ax is None:
        _, ax = plt.subplots(figsize=(8, 4))
    ax.bar(list(masses.keys()), list(masses.values()), color="slategray")
    ax.set_ylabel("mass [kg]")
    ax.tick_params(axis="x", rotation=30)
    for i, v in enumerate(masses.values()):
        ax.text(i, v, f"{v:.0f}", ha="center", va="bottom", fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    return ax


def plot_tank_state(aircraft, axes=None):
    """Plot LH2 tank pressure, stored mass and vent flow vs time.

    Requires the tank thermodynamics to have been tracked, i.e. set
    ``aircraft.mission.track_tank = True`` and re-run ``EvaluateMission`` first.
    """
    import matplotlib.pyplot as plt
    tank = getattr(aircraft, "tank", None)
    if tank is None or not getattr(tank, "history", None) or not tank.history["t"]:
        raise ValueError("No tank history — set mission.track_tank=True and re-run EvaluateMission.")
    h = tank.history
    t_min = np.array(h["t"]) / 60.0
    if axes is None:
        _, axes = plt.subplots(3, 1, sharex=True, figsize=(8, 8))
    axes[0].plot(t_min, h["P"], color="tab:blue"); axes[0].set_ylabel("pressure [bar]")
    axes[1].plot(t_min, h["m_tot"], color="tab:green"); axes[1].set_ylabel("stored H2 [kg]")
    axes[2].plot(t_min, h["Vent"], color="tab:red"); axes[2].set_ylabel("vent flow [kg/s]")
    axes[-1].set_xlabel("time [min]")
    for ax in axes:
        ax.grid(alpha=0.3)
    return axes
