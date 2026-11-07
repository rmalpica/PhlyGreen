"""Class-II hybrid design (common.hybrid_config('II')) and everything computed on it.

fig_mission_class_ii.pdf : time histories of the sized pack along the mission.
fig_pnumber_search.pdf   : P-number search history inside the take-off-weight loop.
fig_aged_flight.pdf      : the BOL-sized pack flown at a degraded state of health.
fig_ground_charge.pdf    : post-design ground fast-charge / cycle-life analysis.
data/class_ii.json       : the numbers quoted in the manual.
"""

import contextlib
import copy
import io
import time
import warnings

import numpy as np

from _setup import C, SEQ, GREY, TEXTWIDTH, plt, save, dump, label_panel

import PhlyGreen as pg
import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed
from common import hybrid_config

COLS = ["t", "SOC", "Voc", "Vout", "i", "T", "Tamb", "alt", "mdot"]


def design_recorded():
    """Design hybrid_config('II') recording the WTO of every weight-loop call."""
    a = pg.build_aircraft()
    wto_calls = []
    orig = a.mission.EvaluateMission

    def recorder(WTO):
        wto_calls.append(float(WTO))
        return orig(WTO)

    a.mission.EvaluateMission = recorder
    t0 = time.time()
    buf = io.StringIO()
    with warnings.catch_warnings(), contextlib.redirect_stdout(buf):
        warnings.simplefilter("ignore")
        a.configure(hybrid_config("II"))
    elapsed = time.time() - t0
    a.mission.EvaluateMission = orig
    n_rtol_warnings = buf.getvalue().count("rtol may be too loose")
    return a, wto_calls, elapsed, n_rtol_warnings


def phi_of(a, t):
    return np.array([float(a.mission.profile.SuppliedPowerRatio(x)) for x in t])


def pack_heat(a):
    """Pack heat generation [W] at every integration point (no ceiling filter)."""
    m, b = a.mission, a.battery
    t = np.concatenate([s.t for s in m.integral_solution])
    beta = np.concatenate([s.y[2] for s in m.integral_solution])
    it = np.concatenate([s.y[3] for s in m.integral_solution])
    T = np.concatenate([s.y[4] for s in m.integral_solution])
    q = np.zeros_like(t)
    for k in range(len(t)):
        alt, vel = m.profile.Altitude(t[k]), m.profile.Velocity(t[k])
        PP = a.weight.WTO * a.performance.PoWTO(a.DesignWTOoS, beta[k], m.profile.PowerExcess(t[k]),
                                                1, alt, m.DISA, vel, "TAS")
        phi = float(m.profile.SuppliedPowerRatio(t[k]))
        PR = a.powertrain.Hybrid(phi, alt, vel, PP)
        try:
            b.T, b.phi, b.it = T[k], phi, it[k] / 3600
            b.i = b.Power_2_current(PP * PR[5])
            Mach = Speed.TAS2Mach(vel, alt, DISA=m.DISA)
            _, qc = b.heatLoss(ISA.atmosphere.T0std(alt, Mach), ISA.atmosphere.RHO0std(alt, Mach, m.DISA))
            q[k] = qc * b.cells_total
        except Exception:
            q[k] = np.nan
    return t, q, T


def fly_aged(sized, capacity_fraction, resistance_factor, range_nm=None, P=None):
    """Fly the frozen BOL pack at a state of health; the design take-off mass is used when
    ``range_nm`` is None, otherwise the off-design mass is closed as in
    examples/30_off_design_mission.py:fly_off_design. Returns (aircraft, result, code, WTO)."""
    a = copy.deepcopy(sized)
    a.battery.set_state_of_health(capacity_fraction, resistance_factor)
    if P is not None:
        a.battery.Configure(P)
    a.mission.size_battery_pack = False
    w = sized.weight
    if range_nm is not None:
        a.MissionInput["Range Mission"] = range_nm
        a.mission.InitializeProfile()
    oew = w.WTO - w.Wf - w.final_reserve - w.WPayload - w.WCrew
    wto, code, out = w.WTO, None, None
    with contextlib.redirect_stdout(io.StringIO()), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for _ in range(20 if range_nm is not None else 1):
            out = a.mission.EvaluateMission(wto)
            if out[0] == 0:
                code = out[1]
                break
            wto_new = oew + w.WPayload + w.WCrew + out[0] / a.mission.ef + w.final_reserve
            if abs(wto_new - wto) < 1.0:
                wto = wto_new
                break
            wto = wto_new
    return a, out, code, wto


def main():
    a, wto_calls, elapsed, n_warn = design_recorded()
    m, b, w = a.mission, a.battery, a.weight
    pv = np.array(m.plottingVars)
    H = {c: pv[:, k] for k, c in enumerate(COLS)}
    t_h, q_h, T_h = pack_heat(a)
    ceiling = 273.15 + m.T_battery_limit
    at_ceiling = T_h >= ceiling - 0.5
    phi = phi_of(a, H["t"])
    on = phi > 0
    out = {
        "elapsed_s": elapsed, "rtol_warnings": n_warn,
        "WTO": w.WTO, "WBat": w.WBat, "Wf": w.Wf, "WHEX": w.WHeat_Exchanger, "WPT": w.WPT,
        "WMotor": a.powertrain.WMotor, "WPMAD": a.powertrain.WPMAD,
        "E_bat_kWh": w.TotalEnergies[1] / 3.6e6, "Max_PBat_W": m.Max_PBat,
        "Max_Bat_Thermal_Pwr_W": m.Max_Bat_Thermal_Pwr, "S": b.S_number, "P": b.P_number,
        "cells": b.cells_total, "pack_energy_Wh": b.pack_energy, "pack_power_max_W": b.pack_power_max,
        "pack_nominal_V": b.S_number * b.Vnom, "pack_Vmax": b.S_number * b.cell_Vmax,
        "SOC_end": float(H["SOC"][-1]), "SOC_min_hist": float(H["SOC"].min()),
        "T_max_C": float(H["T"].max() - 273.15), "T_end_C": float(H["T"][-1] - 273.15),
        "i_max_pack_A": float(H["i"].max()), "i_max_cell_A": float(H["i"].max() / b.P_number),
        "cell_max_current_A": float(b.cell_max_current),
        "Vout_min_pack": float(H["Vout"][on].min()), "Vcell_min": float(H["Vout"][on].min() / b.S_number),
        "q_pack_peak_all_W": float(np.nanmax(q_h)),
        "q_pack_peak_at_ceiling_W": float(np.nanmax(np.where(at_ceiling, q_h, np.nan))) if at_ceiling.any() else 0.0,
        "t_reach_ceiling_min": float(t_h[np.argmax(at_ceiling)] / 60) if at_ceiling.any() else None,
        "mission_time_min": float(H["t"][-1] / 60),
        "T_min_before_cruise_C": float(H["T"][H["t"] <= m.profile.Breaks[5]].min() - 273.15),
        "T_cruise_start_C": float(np.interp(m.profile.Breaks[5], H["t"], H["T"]) - 273.15),
        "cruise_start_min": float(m.profile.Breaks[5] / 60), "cruise_end_min": float(m.profile.Breaks[6] / 60),
        "wto_calls": wto_calls, "Past_P_n": m.Past_P_n,
        "n_P_evaluations": int(sum(len(x) for x in m.Past_P_n)),
        "hex_specific_power": a.EnergyInput.get("HEX Specific Power Battery", 1500.0),
    }

    # ---------------- figure: mission histories ----------------
    tm = H["t"] / 60
    fig, axes = plt.subplots(3, 2, figsize=(TEXTWIDTH, 5.6), sharex=True)
    ax = axes[0, 0]
    ax.plot(tm, H["alt"] / 1000, color=C[0])
    ax.set_ylabel("altitude [km]")
    label_panel(ax, "a")
    ax = axes[0, 1]
    ax.plot(tm, phi, color=C[0])
    ax.set_ylabel(r"supplied power ratio $\varphi$ [-]")
    label_panel(ax, "b")
    ax = axes[1, 0]
    ax.plot(tm, H["SOC"], color=C[0])
    ax.axhline(b.SOC_min, color=GREY, lw=0.8, ls=":")
    ax.text(tm[0], b.SOC_min + 0.02, "SOC$_{min}$", color=GREY, fontsize=7)
    ax.set_ylabel("state of charge [-]")
    label_panel(ax, "c")
    ax = axes[1, 1]
    ax.plot(tm, H["Voc"] / b.S_number, color=C[0], label="open circuit")
    ax.plot(tm[on], H["Vout"][on] / b.S_number, ".", color=C[1], ms=1.5, label="terminal")
    ax.axhline(b.cell_Vmin, color=GREY, lw=0.8)
    ax.set_ylabel("cell voltage [V]")
    ax.legend(loc="lower left", markerscale=4)
    label_panel(ax, "d")
    ax = axes[2, 0]
    ax.plot(tm, H["i"] / b.P_number, color=C[0])
    ax.axhline(b.cell_max_current, color=GREY, lw=0.8, ls="--")
    ax.text(tm[0], b.cell_max_current * 0.93, "$I_{max}$", color=GREY, fontsize=7, va="top")
    ax.set_ylabel("cell current [A]")
    ax.set_xlabel("time [min]")
    label_panel(ax, "e")
    ax = axes[2, 1]
    ax.plot(tm, H["T"] - 273.15, color=C[0], label="cell")
    ax.plot(tm, H["Tamb"] - 273.15, color=C[2], ls="--", label="ambient")
    ax.axhline(m.T_battery_limit, color=GREY, lw=0.8, ls=":")
    ax.set_ylabel("temperature [°C]")
    ax.set_xlabel("time [min]")
    ax.legend(loc="lower left")
    label_panel(ax, "f")
    fig.tight_layout()
    save(fig, "fig_mission_class_ii.pdf")

    fig, ax = plt.subplots(figsize=(TEXTWIDTH * 0.6, 2.3))
    ax.plot(t_h / 60, q_h / 1e3, color=C[0], label="generated")
    ax.plot(t_h[at_ceiling] / 60, q_h[at_ceiling] / 1e3, ".", color=C[1], ms=2, label="rejected (at the ceiling)")
    ax.set_xlabel("time [min]")
    ax.set_ylabel("pack heat [kW]")
    ax.legend(loc="upper left", markerscale=4)
    save(fig, "fig_pack_heat.pdf")

    # ---------------- figure: P-number search ----------------
    fig, axes = plt.subplots(2, 1, figsize=(TEXTWIDTH, 3.6), sharex=True,
                             gridspec_kw={"height_ratios": [2, 1]})
    k0 = 0
    xs_c, ys_c = [], []
    for j, lst in enumerate(m.Past_P_n):
        opt = lst[-1]
        x = np.arange(k0, k0 + len(lst))
        feas = np.array([p >= opt for p in lst])
        axes[0].plot(x, lst, color=GREY, lw=0.6)
        axes[0].plot(x[feas], np.array(lst)[feas], "o", color=C[0], ms=4,
                     label="feasible" if j == 0 else None)
        axes[0].plot(x[~feas], np.array(lst)[~feas], "x", color=C[1], ms=5,
                     label="infeasible" if j == 0 else None)
        xs_c.append(x[-1]); ys_c.append(wto_calls[j] / 1000)
        if j:
            axes[0].axvline(k0 - 0.5, color="#d9d8d4", lw=0.6)
            axes[1].axvline(k0 - 0.5, color="#d9d8d4", lw=0.6)
        k0 += len(lst)
    axes[0].set_ylabel("parallel cells $P$ [-]")
    axes[0].legend(loc="upper right")
    axes[1].plot(xs_c, ys_c, "s-", color=C[2], ms=4)
    axes[1].set_ylabel("$W_{TO}$ probe [t]")
    axes[1].set_xlabel("mission evaluation index")
    label_panel(axes[0], "a")
    label_panel(axes[1], "b")
    fig.tight_layout()
    save(fig, "fig_pnumber_search.pdf")

    # ---------------- aged flight of the BOL pack ----------------
    # (1) design mission, at the design take-off mass: verdict of the frozen pack.
    def summary(ac, code):
        pvc = np.array(ac.mission.plottingVars)
        return {"code": code, "t_end_min": float(pvc[-1, 0] / 60), "SOC_last": float(pvc[-1, 1]),
                "SOC_min": float(pvc[:, 1].min())}
    verdicts = {}
    for c, r in [(1.0, 1.0), (0.99, 1.0), (0.98, 1.0), (0.97, 1.0), (1.0, 1.5), (1.0, 2.0), (1.0, 3.0)]:
        ac, _, code, _ = fly_aged(a, c, r)
        verdicts[f"c={c:g},r={r:g}"] = summary(ac, code)
    out["aged_design_range"] = verdicts
    # (2) the packs one and two strings smaller than the sized one
    pcheck = {}
    for P in [b.P_number - 2, b.P_number - 1]:
        ac, _, code, _ = fly_aged(a, 1.0, 1.0, P=int(P))
        pcheck[str(int(P))] = summary(ac, code)
    out["P_boundary_check"] = pcheck

    # (3) 500 nm off-design mission (design phi schedule): aged packs, histories.
    cases = [(1.0, 1.0), (0.8, 1.0), (1.0, 2.0), (0.7, 2.0)]
    grid = {}
    fig, axes = plt.subplots(1, 2, figsize=(TEXTWIDTH, 2.6), sharex=True)
    for k, (c, r) in enumerate(cases):
        ac, res, code, wto = fly_aged(a, c, r, range_nm=500.0)
        pvc = np.array(ac.mission.plottingVars)
        lab = f"$c$ = {c:g}, $r$ = {r:g}"
        tt = pvc[:, 0] / 60
        on_c = phi_of(ac, pvc[:, 0]) > 0
        axes[0].plot(tt, pvc[:, 1], color=C[k], label=lab)
        axes[1].plot(tt[on_c], pvc[on_c, 3] / b.S_number, ".", color=C[k], ms=1.2)
        grid[f"c={c:g},r={r:g}"] = {"code": code, "WTO": wto, "SOC_end": float(pvc[-1, 1]),
                                   "Vcell_min": float(pvc[on_c, 3].min() / b.S_number),
                                   "Vcell_first": float(pvc[on_c, 3][0] / b.S_number),
                                   "T_max_C": float(pvc[:, 5].max() - 273.15),
                                   "E_bat_kWh": float(res[1] / 3.6e6) if code is None else None,
                                   "Wf_trip_plus_div": float(res[0] / ac.mission.ef) if code is None else None}
    axes[0].axhline(b.SOC_min, color=GREY, lw=0.8, ls=":")
    axes[0].set_ylabel("state of charge [-]")
    axes[0].set_xlabel("time [min]")
    axes[0].legend(loc="lower left", fontsize=7)
    axes[1].set_ylabel("cell terminal voltage [V]")
    axes[1].set_xlabel("time [min]")
    label_panel(axes[0], "a")
    label_panel(axes[1], "b")
    fig.tight_layout()
    save(fig, "fig_aged_flight.pdf")
    out["aged_500nm"] = grid

    # ---------------- post-design ground charge and cycle life ----------------
    # The analysis reads the flown cycle from the mission: DoD, mean flight temperature and
    # the pack state after the taxi-in.
    rates = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    rows = []
    for cr in rates:
        r_ = b.thermal_degradation_analysis(charge_c_rate=cr, discharge_c_rate=3.0)
        rows.append(r_)
    out["ground_charge"] = {f"{cr:g}": r_ for cr, r_ in zip(rates, rows)}
    it_end, T_end = m.battery_end_state
    out["ground_charge_inputs"] = {"T_flight_K": rows[0]["T_flight"], "T_start_K": rows[0]["T_start"],
                                   "soc_start": rows[0]["soc_start"], "dod": rows[0]["dod"],
                                   "SOC_min_input": b.SOC_min, "T_end_taxi_in_K": float(T_end),
                                   "Cth": b.Cth, "area": b.cell_area_surface}
    fig, axes = plt.subplots(1, 3, figsize=(TEXTWIDTH, 2.3))
    axes[0].plot(rates, [x["T_final"] - 273.15 for x in rows], "o-", color=C[0])
    axes[0].set_ylabel("end-of-charge cell T [°C]")
    axes[1].plot(rates, [x["peak_cooling_w"] / 1e3 for x in rows], "o-", color=C[0],
                 label="charge heat")
    axes[1].plot(rates, [x["peak_pulldown_w"] / 1e3 for x in rows], "s--", color=C[1],
                 label="pull-down")
    axes[1].set_ylabel("peak cooling power [kW]")
    axes[1].legend(loc="upper left")
    axes[2].plot(rates, [x["n_cycles"] for x in rows], "o-", color=C[0])
    axes[2].set_ylabel("cycles to end of life [-]")
    for k, ax in enumerate(axes):
        ax.set_xlabel("charge C-rate [1/h]")
        label_panel(ax, "abc"[k])
    fig.tight_layout()
    save(fig, "fig_ground_charge.pdf")

    dump("class_ii.json", out)


if __name__ == "__main__":
    main()
