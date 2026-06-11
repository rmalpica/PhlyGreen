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
    # Mass fraction (Beta) index in the ODE state vector: [Ef, Beta] (2 states) ->
    # index 1; [Ef, EBat, Beta] (Class-I hybrid) and [Ef, EBat, Beta, it, T] (Class-II
    # hybrid) -> index 2. (For the 5-state case y[-1] is the temperature, not Beta.)
    nstates = sols[0].y.shape[0]
    beta_idx = 1 if nstates == 2 else 2
    beta = np.concatenate([s.y[beta_idx] for s in sols])

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

    # Battery energy / SOC / temperature time-series exist as ODE states for the Hybrid and the
    # Class-II fuel-cell+battery configurations (the battery energy is the 2nd state). The Class-I
    # fuel-cell+battery integrates no battery state ([E_h2, Beta]), so it has none.
    if config in ("Hybrid", "FuelCellBattery") and sols[0].y.shape[0] >= 3:
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


def power_timeseries(aircraft):
    """Mission power flow: propulsive, gas-turbine and electric-motor power vs time.

    Returns equal-length arrays ``time`` [s], ``propulsive_power`` [W] (total shaft power the
    propellers must deliver), ``gt_power`` [W] (gas-turbine shaft power) and ``em_power`` [W]
    (electric-motor / battery power). These come straight from the powertrain power-ratio solve
    (``Powertrain.Traditional`` / ``Powertrain.Hybrid``) at every mission time point, so they
    are correct for both Class-I (constant) and Class-II efficiencies and need no surrogates.

    All powers are **totals for the whole aircraft** (summed over the engines). For a fuel-only
    aircraft ``em_power`` is zero; for configurations without a gas turbine
    (Hydrogen / FuelCellBattery) ``gt_power``/``em_power`` are returned as ``NaN``.
    """
    ts = mission_timeseries(aircraft)
    t, alt, vel = ts["time"], ts["altitude"], ts["velocity"]
    pe, beta = ts["power_excess"], ts["mass_fraction"]
    phi = ts.get("phi", np.zeros_like(t))

    perf, pt = aircraft.performance, aircraft.powertrain
    WTO, WS, DISA = aircraft.weight.WTO, aircraft.DesignWTOoS, aircraft.mission.DISA

    PP = np.array([WTO * perf.PoWTO(WS, beta[i], pe[i], 1, alt[i], DISA, vel[i], 'TAS')
                   for i in range(len(t))])
    config = getattr(aircraft, "Configuration", None)
    if config == "Hybrid":
        PR = np.array([pt.Hybrid(float(phi[i]), alt[i], vel[i], PP[i]) for i in range(len(t))])
        gt_power = PR[:, 1] * PP     # gas-turbine shaft power
        em_power = PR[:, 5] * PP     # battery / electric-motor power
    elif config == "Traditional":
        PR = np.array([pt.Traditional(alt[i], vel[i], PP[i]) for i in range(len(t))])
        gt_power = PR[:, 1] * PP     # all propulsion is thermal
        em_power = np.zeros_like(PP)
    else:                            # Hydrogen / FuelCellBattery: no gas turbine
        gt_power = np.full_like(PP, np.nan)
        em_power = np.full_like(PP, np.nan)

    result = {"time": t, "propulsive_power": PP, "gt_power": gt_power, "em_power": em_power}

    # Fuel-cell / battery / tank outputs for the hydrogen architectures: the battery supplies a
    # share ``phi`` of the propulsive power and the fuel cell the rest; the tank empties as the
    # cumulative hydrogen chemical energy is drawn.
    if config in ("Hydrogen", "FuelCellBattery"):
        result["fc_power"] = (1.0 - phi) * PP        # fuel-cell propulsive share [W]
        result["battery_power"] = phi * PP           # battery propulsive share [W]
        ef = getattr(aircraft.mission, "ef", None)   # H2 lower heating value [J/kg]
        WH2 = getattr(aircraft.weight, "WH2_Fuel", None)
        if ef and WH2:
            result["h2_remaining"] = np.clip(WH2 - ts["fuel_energy"] / ef, 0.0, None)  # [kg]

    return result


def class_ii_components(aircraft):
    """Return the set of powertrain components that used a **Class-II** (operating-point
    dependent) efficiency model in this design.

    Determined by inspecting the powertrain's per-component efficiency models: a
    :class:`~PhlyGreen.Systems.Powertrain.efficiency.ConstantEfficiency` is Class-I, anything
    else is Class-II. An externally-set ``em_model`` / ``fc_model`` also counts as Class-II.
    Used to decide *automatically* which component time series are meaningful for a given
    design (so a constant-efficiency design pulls in no surrogate columns).
    """
    from .Systems.Powertrain.efficiency import ConstantEfficiency
    pt = getattr(aircraft, "powertrain", None)
    found = set()
    if pt is None:
        return found
    for name, model in (getattr(pt, "efficiency", None) or {}).items():
        if not isinstance(model, ConstantEfficiency):
            found.add(name)
    if getattr(pt, "em_model", None) is not None:
        found.add("electric_motor")
    if getattr(pt, "fc_model", None) is not None:
        found.add("fuel_cell")
    return found


def component_timeseries(aircraft, components=None, n_engines=None, gt_design_hp=None,
                         em_design=None, propeller_rpm=1200.0):
    """Evaluate the Class-II propulsion models along the flown mission.

    Walks the converged mission timeline and computes the power flow
    (``propulsive_power``/``gt_power``/``em_power`` [W], also available cheaply via
    :func:`power_timeseries`) plus, for each requested component, its Class-II model outputs:
    gas-turbine efficiency & throttle, electric-motor efficiency & throttle (+ rpm), and
    propeller efficiency & pitch.

    ``components`` selects which Class-II models to evaluate — a subset of
    ``{'gas_turbine', 'electric_motor', 'propeller'}``. ``None`` (default) evaluates all three
    (forced exploration). Only the requested components load their surrogate, so e.g. the
    propeller RBF is *not* loaded unless the propeller is requested.

    By default the GT/EM nominal powers and the engine count are taken from the *designed*
    aircraft (``powertrain.gt_design_power``/``em_design_power``/``n_engines``); pass overrides
    to explore other sizes. A component is skipped silently if its model/data is unavailable.
    """
    import PhlyGreen.Utilities.Units as Units
    import PhlyGreen.Utilities.Speed as Speed

    requested = ({'gas_turbine', 'electric_motor', 'propeller'}
                 if components is None else set(components))

    ts = mission_timeseries(aircraft)
    t, alt, vel = ts["time"], ts["altitude"], ts["velocity"]
    pe, beta = ts["power_excess"], ts["mass_fraction"]
    phi = ts.get("phi", np.zeros_like(t))

    perf, pt = aircraft.performance, aircraft.powertrain
    WTO, WS, DISA = aircraft.weight.WTO, aircraft.DesignWTOoS, aircraft.mission.DISA
    if n_engines is None:
        n_engines = getattr(pt, "n_engines", 1) or 1

    # Propulsive power and its thermal(Pgt)/electric(Pbat) split. Use the hybrid graph for a
    # Hybrid configuration, else the traditional (gas-turbine-only) chain so the function also
    # works for a Class-II gas turbine on a conventional aircraft (no battery).
    PP = np.array([WTO * perf.PoWTO(WS, beta[i], pe[i], 1, alt[i], DISA, vel[i], 'TAS')
                   for i in range(len(t))])
    if getattr(aircraft, "Configuration", None) == "Hybrid":
        PR = np.array([pt.Hybrid(float(phi[i]), alt[i], vel[i], PP[i]) for i in range(len(t))])
        p_thermal = PR[:, 1] * PP    # gas-turbine shaft power
        p_electric = PR[:, 5] * PP   # battery (electric) power
    else:
        PR = np.array([pt.Traditional(alt[i], vel[i], PP[i]) for i in range(len(t))])
        p_thermal = PR[:, 1] * PP    # gas-turbine shaft power (all propulsion is thermal)
        p_electric = np.zeros_like(PP)

    out = {"time": t, "propulsive_power": PP, "gt_power": p_thermal, "em_power": p_electric}

    # --- Gas turbine (Class-II response surface) ---
    if 'gas_turbine' in requested:
        try:
            from .Systems.Powertrain.gas_turbine_surrogate import GasTurbineResponseSurface
            if gt_design_hp is None:
                if getattr(pt, "gt_design_power", None):
                    gt_design_hp = Units.wTohp(pt.gt_design_power) / n_engines
                else:
                    rating = getattr(pt, "engineRating", None) or float(np.max(p_thermal)) or 1.0
                    gt_design_hp = 1.5 * Units.wTohp(rating) / n_engines
            gt = GasTurbineResponseSurface()
            eta_gt, gt_throttle = [], []
            for i in range(len(t)):
                a = Speed.soundspeed(alt[i], 0.0)
                mach = vel[i] / a if a > 0 else 0.0
                req_hp = Units.wTohp(p_thermal[i]) / n_engines
                e, _, pmax, _ = gt.predict(gt_design_hp, Units.mToft(alt[i]), mach, req_hp)
                eta_gt.append(e)
                # GT throttle = required / available power (1.0 means power-limited here).
                gt_throttle.append(min(req_hp / pmax, 1.0) if pmax > 0 else 0.0)
            out["eta_gas_turbine"] = np.array(eta_gt)
            out["gt_throttle"] = np.array(gt_throttle)
        except Exception:
            pass

    # --- Electric motor (Class-II d-q model) ---
    if 'electric_motor' in requested:
        try:
            from .Systems.Powertrain.efficiency import OperatingPoint, MotorEfficiencyModel
            if em_design is None:
                if getattr(pt, "em_design_power", None):
                    em_kw = (pt.em_design_power / n_engines) / 1000.0
                else:
                    em_kw = max(float(np.max(p_electric)) / n_engines / 1000.0, 1.0)
                em_design = (em_kw, 800.0, 11000.0)
            em = MotorEfficiencyModel(*em_design, n_engines=n_engines)
            em_nominal_total = em_design[0] * 1000.0 * n_engines   # [W]
            eta_em, em_throttle = [], []
            for i in range(len(t)):
                # EM throttle = electric demand / nominal; efficiency only when loaded.
                em_throttle.append(p_electric[i] / em_nominal_total if em_nominal_total > 0 else 0.0)
                if p_electric[i] > 1.0:
                    eta_em.append(em.eta(OperatingPoint(power=p_electric[i], rpm=em_design[2])))
                else:
                    eta_em.append(np.nan)
            out["eta_electric_motor"] = np.array(eta_em)
            out["em_throttle"] = np.array(em_throttle)
            out["rpm"] = np.full_like(t, em_design[2])
        except Exception:
            pass

    # --- Propeller (Class-II RBF surrogate) ---
    if 'propeller' in requested:
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


def timeseries_table(aircraft, include_components="auto"):
    """Collect *every* time-evolving mission variable into one aligned table (debug).

    Returns ``(header, columns)`` where ``header`` is a list of column names and ``columns``
    is a list of equal-length numpy arrays (one per name), all sampled at the solver time
    points of the converged mission. It gathers:

    * the raw ODE states (``state_0`` … ``state_n`` — fuel/battery energy, Beta, and, for the
      Class-II battery, charge throughput and temperature) straight from
      ``mission.integral_solution`` — nothing is lost or smoothed;
    * the derived mission quantities from :func:`mission_timeseries` (altitude, velocity,
      power excess, SOC, phi, …);
    * the power flow from :func:`power_timeseries` (``propulsive_power``, ``gt_power``,
      ``em_power`` [W]);
    * the Class-II component quantities from :func:`component_timeseries`
      (gas-turbine / electric-motor / propeller efficiencies, throttles, pitch).

    ``include_components`` controls the last group:

    * ``"auto"`` (default) — include only the components that *actually used* a Class-II model
      in this design (detected with :func:`class_ii_components`); a fully constant-efficiency
      design therefore pulls in no surrogate columns and loads no surrogate.
    * ``True`` — force all three component models (loads every surrogate).
    * ``False`` — omit the component columns entirely.

    ``time`` is always the first column; the remaining columns are sorted by name.
    """
    data = dict(mission_timeseries(aircraft))

    # Raw ODE states, segment by segment, so the dump is the integrator's own output.
    sols = aircraft.mission.integral_solution
    if sols:
        nstates = sols[0].y.shape[0]
        for i in range(nstates):
            data.setdefault(f"state_{i}", np.concatenate([s.y[i] for s in sols]))

    n = len(data["time"])

    # Power flow (propulsive / gas-turbine / electric-motor power) — cheap and always available
    # for Traditional/Hybrid, no surrogates needed.
    try:
        for k, v in power_timeseries(aircraft).items():
            if k == "time":
                continue
            arr = np.asarray(v)
            if arr.ndim == 1 and arr.shape[0] == n:
                data.setdefault(k, arr)
    except Exception:
        pass

    # Class-II component columns. In "auto" mode include only the components that the design
    # actually used as Class-II (so no surrogate is loaded for a constant-efficiency design).
    propulsion = {"gas_turbine", "electric_motor", "propeller"}
    if include_components == "auto":
        wanted = class_ii_components(aircraft) & propulsion
        components = wanted if wanted else None   # None signals "nothing to do" below
        do_components = bool(wanted)
    elif include_components:
        components = None                          # forced: all three
        do_components = True
    else:
        components = None
        do_components = False

    if do_components:
        try:
            cs = component_timeseries(aircraft, components=components)
            for k, v in cs.items():
                if k == "time":
                    continue
                arr = np.asarray(v)
                if arr.ndim == 1 and arr.shape[0] == n:
                    data.setdefault(k, arr)
        except Exception:
            # Optional Class-II models unavailable — derived/raw columns are still written.
            pass

    cols = [(k, np.asarray(v, dtype=float)) for k, v in data.items()
            if np.ndim(v) == 1 and len(v) == n]
    cols.sort(key=lambda kv: (kv[0] != "time", kv[0]))
    header = [k for k, _ in cols]
    columns = [v for _, v in cols]
    return header, columns


def write_timeseries(aircraft, path, include_components="auto"):
    """Dump every time-evolving mission variable to a CSV file (debug helper).

    Writes one row per solver time point and one column per variable returned by
    :func:`timeseries_table` (raw ODE states + derived mission quantities + the power flow +
    Class-II component quantities). ``include_components`` defaults to ``"auto"``: only the
    components that actually used a Class-II model in this design are added (so a
    constant-efficiency design loads no surrogates). Pass ``True`` to force all component
    models or ``False`` to omit them. Returns the path written.
    """
    header, columns = timeseries_table(aircraft, include_components=include_components)
    matrix = np.column_stack(columns) if columns else np.empty((0, 0))
    np.savetxt(path, matrix, delimiter=",", header=",".join(header), comments="")
    return path


def plot_power_timeseries(aircraft, ax=None):
    """Plot the mission power flow vs time (totals, kW).

    Thermal architectures (Traditional / Hybrid) show propulsive, gas-turbine and electric-motor
    power; the hydrogen architectures (Hydrogen / FuelCellBattery) show propulsive, fuel-cell and
    battery power, with the hydrogen remaining in the tank on a second axis.
    """
    import matplotlib.pyplot as plt
    ps = power_timeseries(aircraft)
    t = ps["time"] / 60.0
    if ax is None:
        _, ax = plt.subplots(figsize=(8, 4.5))
    config = getattr(aircraft, "Configuration", None)

    if config in ("Hydrogen", "FuelCellBattery"):
        ax.plot(t, ps["propulsive_power"] / 1e3, color="tab:green", label="propulsive")
        ax.plot(t, ps["fc_power"] / 1e3, color="tab:red", label="fuel cell")
        if np.any(np.nan_to_num(ps.get("battery_power")) != 0):
            ax.plot(t, ps["battery_power"] / 1e3, color="tab:blue", label="battery")
        ax.set_xlabel("time [min]"); ax.set_ylabel("power [kW] (total)"); ax.grid(alpha=0.3)
        if "h2_remaining" in ps:
            ax2 = ax.twinx()
            ax2.plot(t, ps["h2_remaining"], color="tab:purple", ls="--", label="H2 in tank")
            ax2.set_ylabel("H2 in tank [kg]")
            h1, l1 = ax.get_legend_handles_labels()
            h2, l2 = ax2.get_legend_handles_labels()
            ax.legend(h1 + h2, l1 + l2, fontsize=12)
        else:
            ax.legend()
        return ax

    ax.plot(t, ps["propulsive_power"] / 1e3, color="tab:green", label="propulsive")
    ax.plot(t, ps["gt_power"] / 1e3, color="tab:red", label="gas turbine")
    if np.any(np.nan_to_num(ps["em_power"]) != 0):
        ax.plot(t, ps["em_power"] / 1e3, color="tab:blue", label="electric motor")
    ax.set_xlabel("time [min]"); ax.set_ylabel("power [kW] (total)")
    ax.grid(alpha=0.3); ax.legend()
    return ax


def plot_component_timeseries(aircraft, **kwargs):
    """Plot the Class-II component time series from :func:`component_timeseries`.

    By default (no ``components`` kwarg) all three component models are forced, so this works
    as an explicit "show me the component behaviour" request; only the curves actually present
    are drawn.
    """
    import matplotlib.pyplot as plt
    cs = component_timeseries(aircraft, **kwargs)
    t = cs["time"] / 60.0
    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(8, 9))
    for key, label in (("eta_gas_turbine", "gas turbine"),
                       ("eta_electric_motor", "electric motor"),
                       ("eta_propeller", "propeller")):
        if key in cs:
            axes[0].plot(t, cs[key], label=label)
    axes[0].set_ylabel("efficiency [-]"); axes[0].legend(fontsize=12)
    if "gt_throttle" in cs:
        axes[1].plot(t, cs["gt_throttle"], color="tab:red", label="gas turbine")
    if "em_throttle" in cs:
        axes[1].plot(t, cs["em_throttle"], color="tab:blue", label="electric motor")
    axes[1].set_ylabel("throttle [-]"); axes[1].set_ylim(0, 1.05); axes[1].legend(fontsize=12)
    if "propeller_pitch" in cs:
        axes[2].plot(t, cs["propeller_pitch"], color="tab:purple")
        axes[2].set_ylabel("propeller pitch [deg]")
    elif "rpm" in cs:
        axes[2].plot(t, cs["rpm"], color="tab:gray"); axes[2].set_ylabel("motor rpm")
    axes[-1].set_xlabel("time [min]")
    for ax in axes:
        ax.grid(alpha=0.3)
    return axes


def _flown_mask(aircraft, n):
    """Boolean mask over the concatenated time array that drops the loiter/hold (a reserve
    calculation, not an actually flown trajectory). All points at or after the loiter's start time
    are dropped, which also removes the segment-boundary point whose altitude the piecewise profile
    evaluates at the loiter level. Falls back to all-True if segment phases are unavailable."""
    m = getattr(aircraft, "mission", None)
    prof = getattr(m, "profile", None)
    sols = getattr(m, "integral_solution", None)
    segs = getattr(prof, "_segments", None)
    if not sols or segs is None or len(segs) != len(sols):
        return np.ones(n, dtype=bool)
    loiter_starts = [float(s.t[0]) for s, seg in zip(sols, segs)
                     if getattr(seg, "phase", "") == "Loiter"]
    if not loiter_starts:
        return np.ones(n, dtype=bool)
    time = np.concatenate([s.t for s in sols])
    mask = time < min(loiter_starts)
    return mask if mask.shape[0] == n else np.ones(n, dtype=bool)


def plot_mission_profile(aircraft, axes=None, include_loiter=False):
    """Plot altitude, true airspeed and (for hybrids) phi versus time.

    By default the final loiter/hold is excluded (``include_loiter=False``): it is flown only to
    size the fuel reserve, not as part of the actual mission trajectory."""
    import matplotlib.pyplot as plt
    ts = mission_timeseries(aircraft)
    mask = np.ones(len(ts["time"]), dtype=bool) if include_loiter else _flown_mask(aircraft, len(ts["time"]))
    ts = {k: (v[mask] if hasattr(v, "shape") and v.shape[:1] == mask.shape else v) for k, v in ts.items()}
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
    """Plot the constraint diagram (power loading P/m_TO vs wing loading m_TO/S_wing) with the
    design point. The wing-loading axis is in mass terms [kg/m^2]: the stored W/S is a weight
    loading [N/m^2], so it is divided by g for display. The power-loading axis is already a
    specific power [W/kg], i.e. P/m_TO, and is only relabelled."""
    import matplotlib.pyplot as plt
    G = 9.80665                                   # N/m^2 (weight loading) -> kg/m^2 (mass loading)
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
            ax.plot(np.asarray(c.WTOoS) / G, y, label=label)
    if getattr(c, "PWLanding", None) is not None and getattr(c, "WTOoSLanding", None) is not None:
        ax.plot(np.asarray(c.WTOoSLanding) / G, c.PWLanding, label="Landing")
    design_pw = None
    try:
        design_pw = aircraft.DesignPW
        ax.plot(aircraft.DesignWTOoS / G, design_pw, "o", ms=10,
                mfc="red", mec="black", label="design point", zorder=5)
    except Exception:
        pass
    ax.set_xlabel(r"wing loading $m_{TO}/S_{wing}$ [kg/m$^2$]")
    ax.set_ylabel(r"power loading $P/m_{TO}$ [W/kg]")
    # Limit the y-range so the design point sits roughly mid-axis (P/W curves can shoot up
    # towards the W/S extremes and otherwise squash the design region).
    if design_pw is not None and design_pw > 0:
        ax.set_ylim(0, 2.0 * design_pw)
    else:
        ax.set_ylim(bottom=0)
    ax.grid(alpha=0.3); ax.legend(fontsize=12)
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
        ax.text(i, v, f"{v:.0f}", ha="center", va="bottom", fontsize=12)
    ax.grid(axis="y", alpha=0.3)
    return ax


def compute_tank_history(aircraft):
    """Advance the LH2 tank thermodynamic state along the converged mission, filling
    ``aircraft.tank.history``.

    Works for any hydrogen architecture (``Hydrogen`` and ``FuelCellBattery``): it walks the
    flown mission solution and drives the tank with the hydrogen mass flow recovered from the
    cumulative hydrogen chemical energy (ODE state ``y[0]``). Unlike setting
    ``mission.track_tank`` and re-flying, this is a cheap post-processing pass and needs no
    re-integration. Requires a physics LH2 tank (a ``TankConfig`` + CoolProp) and a flown mission.
    """
    tank = getattr(aircraft, "tank", None)
    m = getattr(aircraft, "mission", None)
    if tank is None or not hasattr(tank, "time_step"):
        raise ValueError("No physics LH2 tank — attach a TankConfig (needs CoolProp).")
    if m is None or not getattr(m, "integral_solution", None):
        raise ValueError("No mission solution — design the aircraft first.")
    tank.m_curr = tank.capacity_single        # start full
    tank.P_curr = tank.P_min
    tank.history = {'t': [], 'P': [], 'm_tot': [], 'Vent': [], 'Q_in': [],
                    'Alt': [], 'Q_heater': [], 'm_vent_cum': [], 'Consumption': []}
    tank.cum_vented_mass = 0.0
    for arr in m.integral_solution:
        for k in range(1, len(arr.t)):
            dt = arr.t[k] - arr.t[k - 1]
            dE = max(float(arr.y[0][k] - arr.y[0][k - 1]), 0.0)   # hydrogen chemical energy used
            m_dot = (dE / m.ef) / dt if dt > 0 else 0.0
            t_mid = 0.5 * (arr.t[k] + arr.t[k - 1])
            tank.time_step(dt, m_dot, float(m.profile.Altitude(t_mid)))
    return tank.history


def plot_tank_state(aircraft, axes=None):
    """Plot LH2 tank pressure, stored mass, vent flow and heater power vs time.

    The vent flow and heater power are the two active thermal-management actions: the tank vents
    hydrogen when it reaches the maximum pressure, and the heater adds power when it falls to the
    minimum pressure. Requires the tank thermodynamics to have been tracked: either set
    ``aircraft.mission.track_tank = True`` and re-run ``EvaluateMission``, or call
    :func:`compute_tank_history` (which works for the fuel-cell + battery configuration too).
    """
    import matplotlib.pyplot as plt
    tank = getattr(aircraft, "tank", None)
    if tank is None or not getattr(tank, "history", None) or not tank.history["t"]:
        raise ValueError("No tank history — set mission.track_tank=True and re-run EvaluateMission.")
    h = tank.history
    t_min = np.array(h["t"]) / 60.0
    if axes is None:
        _, axes = plt.subplots(4, 1, sharex=True, figsize=(8, 10))
    axes[0].plot(t_min, h["P"], color="tab:blue"); axes[0].set_ylabel("pressure [bar]")
    axes[1].plot(t_min, h["m_tot"], color="tab:green"); axes[1].set_ylabel("stored H2 [kg]")
    axes[2].plot(t_min, h["Vent"], color="tab:red"); axes[2].set_ylabel("vent flow [kg/s]")
    if len(axes) > 3:
        axes[3].plot(t_min, np.array(h["Q_heater"]) / 1e3, color="tab:orange")
        axes[3].set_ylabel("heater power [kW]")
    axes[-1].set_xlabel("time [min]")
    for ax in axes:
        ax.grid(alpha=0.3)
    return axes
