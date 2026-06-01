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
    if config == "Hybrid":
        nstates = sols[0].y.shape[0]
        out["battery_energy"] = np.concatenate([s.y[1] for s in sols])
        b = aircraft.battery
        if nstates >= 5:
            # Class II: SOC is charge-based (state y[3] = charge throughput [A·s]); the
            # energy ratio is NOT a valid SOC. Also expose the battery temperature (y[4]).
            it_As = np.concatenate([s.y[3] for s in sols])
            q_pack_Ah = getattr(b, "cell_capacity", None)
            p_number = getattr(b, "P_number", None)
            if q_pack_Ah and p_number:
                out["soc"] = np.clip(1.0 - (it_As / 3600.0) / (q_pack_Ah * p_number), 0.0, 1.0)
            out["battery_temperature"] = np.concatenate([s.y[4] for s in sols])
        else:
            # Class I: energy-based SOC against the installed battery energy.
            ebat = getattr(b, "Ebat", None)            # [J/kg]
            wbat = getattr(aircraft.weight, "WBat", None)
            if ebat and wbat:
                out["soc"] = np.clip(1.0 - out["battery_energy"] / (ebat * wbat), 0.0, 1.0)

    return out


def component_timeseries(aircraft, n_engines=None, gt_design_hp=None, em_design=None,
                         propeller_rpm=1200.0):
    """Evaluate the Class-II propulsion models along the flown mission.

    Walks the converged mission timeline and, at each instant, computes the propulsive power
    and its thermal/electric split (via the powertrain graph), then evaluates the gas-turbine
    response surface, the d-q electric-motor model and the propeller RBF surrogate. Returns
    per-time arrays: component efficiencies, gas-turbine throttle (used/available power),
    propeller pitch, motor rpm, and the thermal/electric shaft powers.

    By default the GT/EM nominal powers and the engine count are taken from the *designed*
    aircraft (``powertrain.gt_design_power``/``em_design_power``/``n_engines``), so the
    throttle is the real result for the sized engines; pass overrides to explore other sizes.

    Requires the optional GT artifact and (for the propeller) pandas; propeller fields are
    omitted if unavailable.
    """
    from .Systems.Powertrain.efficiency import OperatingPoint, MotorEfficiencyModel
    from .Systems.Powertrain.gas_turbine_surrogate import GasTurbineResponseSurface
    import PhlyGreen.Utilities.Units as Units
    import PhlyGreen.Utilities.Speed as Speed

    ts = mission_timeseries(aircraft)
    t, alt, vel = ts["time"], ts["altitude"], ts["velocity"]
    pe, beta = ts["power_excess"], ts["mass_fraction"]
    phi = ts.get("phi", np.zeros_like(t))

    perf, pt = aircraft.performance, aircraft.powertrain
    WTO, WS, DISA = aircraft.weight.WTO, aircraft.DesignWTOoS, aircraft.mission.DISA
    if n_engines is None:
        n_engines = getattr(pt, "n_engines", 1) or 1

    # Propulsive power and its thermal(Pgt)/electric(Pbat) split (parallel-hybrid graph).
    PP = np.array([WTO * perf.PoWTO(WS, beta[i], pe[i], 1, alt[i], DISA, vel[i], 'TAS')
                   for i in range(len(t))])
    PR = np.array([pt.Hybrid(float(phi[i]), alt[i], vel[i], PP[i]) for i in range(len(t))])
    p_thermal = PR[:, 1] * PP    # gas-turbine shaft power
    p_electric = PR[:, 5] * PP   # battery (electric) power

    # Nominal powers: use the designed Class-II values if available, else a sensible default.
    if gt_design_hp is None:
        if getattr(pt, "gt_design_power", None):
            gt_design_hp = Units.wTohp(pt.gt_design_power) / n_engines
        else:
            rating = getattr(pt, "engineRating", None) or float(np.max(p_thermal)) or 1.0
            gt_design_hp = 1.5 * Units.wTohp(rating) / n_engines
    if em_design is None:
        if getattr(pt, "em_design_power", None):
            em_kw = (pt.em_design_power / n_engines) / 1000.0
        else:
            em_kw = max(float(np.max(p_electric)) / n_engines / 1000.0, 1.0)
        em_design = (em_kw, 800.0, 11000.0)

    gt = GasTurbineResponseSurface()
    em = MotorEfficiencyModel(*em_design, n_engines=n_engines)

    eta_gt, throttle, eta_em = [], [], []
    for i in range(len(t)):
        a = Speed.soundspeed(alt[i], 0.0)
        mach = vel[i] / a if a > 0 else 0.0
        req_hp = Units.wTohp(p_thermal[i]) / n_engines
        e, _, pmax, _ = gt.predict(gt_design_hp, Units.mToft(alt[i]), mach, req_hp)
        eta_gt.append(e)
        throttle.append(min(req_hp / pmax, 1.0) if pmax > 0 else 0.0)
        # Electric-motor efficiency only meaningful when the motor is loaded.
        if p_electric[i] > 1.0:
            eta_em.append(em.eta(OperatingPoint(power=p_electric[i], rpm=em_design[2])))
        else:
            eta_em.append(np.nan)

    out = {
        "time": t, "p_thermal": p_thermal, "p_electric": p_electric,
        "eta_gas_turbine": np.array(eta_gt), "gt_throttle": np.array(throttle),
        "eta_electric_motor": np.array(eta_em), "rpm": np.full_like(t, em_design[2]),
    }

    try:
        import os
        from .Systems.Powertrain import propeller_surrogate as _prbf
        csv = os.path.join(os.path.dirname(_prbf.__file__), "data", "propeller_data_rbf.csv")
        prop = _prbf.PropellerSurrogate(csv)
        eta_pp, pitch = [], []
        for i in range(len(t)):
            pk = (PP[i] / n_engines) / 1000.0
            pit = prop.solve_pitch(pk, alt[i], vel[i], propeller_rpm)
            eta_pp.append(prop.get_efficiency(pk, alt[i], vel[i], pit, propeller_rpm))
            pitch.append(pit)
        out["eta_propeller"] = np.array(eta_pp)
        out["propeller_pitch"] = np.array(pitch)
    except Exception:
        pass
    return out


def plot_component_timeseries(aircraft, **kwargs):
    """Plot the Class-II component time series from :func:`component_timeseries`."""
    import matplotlib.pyplot as plt
    cs = component_timeseries(aircraft, **kwargs)
    t = cs["time"] / 60.0
    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(8, 9))
    axes[0].plot(t, cs["eta_gas_turbine"], label="gas turbine")
    axes[0].plot(t, cs["eta_electric_motor"], label="electric motor")
    if "eta_propeller" in cs:
        axes[0].plot(t, cs["eta_propeller"], label="propeller")
    axes[0].set_ylabel("efficiency [-]"); axes[0].legend(fontsize=8)
    axes[1].plot(t, cs["gt_throttle"], color="tab:red")
    axes[1].set_ylabel("GT throttle [-]")
    if "propeller_pitch" in cs:
        axes[2].plot(t, cs["propeller_pitch"], color="tab:purple")
        axes[2].set_ylabel("propeller pitch [deg]")
    else:
        axes[2].plot(t, cs["rpm"], color="tab:gray"); axes[2].set_ylabel("motor rpm")
    axes[-1].set_xlabel("time [min]")
    for ax in axes:
        ax.grid(alpha=0.3)
    return axes


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
    design_pw = None
    try:
        design_pw = aircraft.DesignPW
        ax.plot(aircraft.DesignWTOoS, design_pw, "o", ms=10,
                mfc="red", mec="black", label="design point", zorder=5)
    except Exception:
        pass
    ax.set_xlabel(r"$W_{TO}/S$ [N/m$^2$]"); ax.set_ylabel(r"$P/W_{TO}$ [W/kg]")
    # Limit the y-range so the design point sits roughly mid-axis (P/W curves can shoot up
    # towards the W/S extremes and otherwise squash the design region).
    if design_pw is not None and design_pw > 0:
        ax.set_ylim(0, 2.0 * design_pw)
    else:
        ax.set_ylim(bottom=0)
    ax.grid(alpha=0.3); ax.legend(fontsize=8)
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
