"""Regenerate every figure and every computed number of the fuel-cell manual.

Run from the repository's ``trunk/`` directory with the PhlyGreen environment:

    cd trunk
    conda run -n phlygreen python ../manuals/fuel-cell/scripts/make_figures.py          # all
    conda run -n phlygreen python ../manuals/fuel-cell/scripts/make_figures.py cell     # one group

Groups (each writes PDFs to ``manuals/fuel-cell/figures/`` and merges its numbers into
``manuals/fuel-cell/figures/manual_numbers.json``):

    cell      cell-level physics, no design needed (seconds)
    reference reference hydrogen design: load sweeps, mission history, power limit (~1 min)
    sweep     design-voltage sweep, 0.40-0.65 V (~2 min)
    eol       end-of-life sizing versus beginning-of-life sizing (~30 s)
    fcb       take-off-sized FC + battery design of example 30: duty and degraded flights (~2 min)
    assist    take-off assist sweep of example 23 on two fields (~4 min)
    weather   ambient humidity, hot day (ISA+20) and humidifier on the reference (~2 min)

Configurations: ``examples/common.py:hydrogen_config()`` (the reference hydrogen design,
Class-I TMS, gravimetric-index tank) and ``examples/30_off_design_mission.py:fc_battery_design``.
"""

import copy
import importlib.util
import json
import os
import sys
import warnings

import numpy as np
from scipy.optimize import brentq

HERE = os.path.dirname(os.path.abspath(__file__))
MANUAL = os.path.dirname(HERE)
FIGS = os.path.join(MANUAL, "figures")
REPO = os.path.dirname(os.path.dirname(MANUAL))
TRUNK = os.path.join(REPO, "trunk")
EXAMPLES = os.path.join(TRUNK, "examples")
sys.path.insert(0, EXAMPLES)
os.makedirs(FIGS, exist_ok=True)

import matplotlib                                                    # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt                                      # noqa: E402

import PhlyGreen as pg                                               # noqa: E402
from PhlyGreen.Systems.FuelCell import FC_Database                   # noqa: E402
from common import hydrogen_config, fuelcell_battery_config          # noqa: E402

warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
warnings.filterwarnings("ignore", message=".*matrix subclass.*")

# --------------------------------------------------------------------------- style
# Fixed categorical order (blue, orange, aqua, yellow, magenta, green); line style and
# marker double the colour so every figure reads in grey-scale print.
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
LS = ["-", "--", "-.", ":", (0, (5, 1, 1, 1)), (0, (1, 1))]
MK = ["o", "s", "^", "D", "v", "P"]
INK, MUTED = "#222222", "#777777"
plt.rcParams.update({
    "font.family": "serif", "font.size": 8.5, "axes.labelsize": 8.5, "axes.titlesize": 9,
    "legend.fontsize": 7.5, "xtick.labelsize": 8, "ytick.labelsize": 8,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "xtick.color": MUTED,
    "ytick.color": MUTED, "axes.grid": True, "grid.color": "#e3e3e3", "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "lines.linewidth": 1.6,
    "lines.markersize": 4.5, "legend.frameon": False, "savefig.bbox": "tight",
    "pdf.fonttype": 42, "mathtext.fontset": "cm",
})
FULL, HALF = 6.3, 3.1                                  # figure widths [in]

NUMBERS_FILE = os.path.join(FIGS, "manual_numbers.json")


def save(fig, name):
    path = os.path.join(FIGS, name)
    fig.savefig(path)
    plt.close(fig)
    print("  wrote", os.path.relpath(path, REPO))


def store(group, data):
    """Merge ``data`` into the numbers file under ``group``."""
    allnum = {}
    if os.path.exists(NUMBERS_FILE):
        with open(NUMBERS_FILE) as f:
            allnum = json.load(f)
    allnum[group] = data
    with open(NUMBERS_FILE, "w") as f:
        json.dump(allnum, f, indent=1, default=float)


def quiet(fn, *args, **kwargs):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return fn(*args, **kwargs)


def design(cfg):
    a = pg.build_aircraft()
    quiet(a.configure, cfg)
    return a


def ready_fuelcell(model="PEMFC_GoodPerformance"):
    """A fuel cell whose inputs are read (SetInput) but which is not sized."""
    a = pg.build_aircraft()
    cfg = hydrogen_config()
    cfg.energy.fc_model = model
    quiet(a.configure, cfg, design=False)
    return a.fuelcell


def load_example30():
    spec = importlib.util.spec_from_file_location(
        "ex30", os.path.join(EXAMPLES, "30_off_design_mission.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# =========================================================================== cell level
def group_cell():
    print("[cell] database models")
    F = 96485.33
    out = {}
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(FULL, 2.6))
    for k, name in enumerate(FC_Database):
        fc = ready_fuelcell(name)
        P = fc.Target_Press
        ii = np.linspace(1e-3, 0.999 * fc.j_lim, 600)
        vv = np.array([fc.PolarizationCurve(x, P) for x in ii])
        pp = ii * vv
        V = lambda i: fc.PolarizationCurve(i, P)
        c_h = fc.c_h_ref * P / 1e5
        out[name] = {
            "j_star": fc.sigma_t * fc.b_tafel / fc.l_t,
            "D_star": fc.sigma_t * fc.b_tafel / (4 * F * fc.c_ref),
            "eps": float(np.sqrt(fc.sigma_t * fc.b_tafel / (2 * fc.i_star * fc.l_t ** 2))),
            "D_tilde": fc.D_ccl / (fc.sigma_t * fc.b_tafel / (4 * F * fc.c_ref)),
            "c_h_tilde": c_h / fc.c_ref,
            "j_lim_star": 4 * F * fc.D_b * c_h / fc.l_b,
            "V_at_1e-4": V(1e-4),
            "i_at_0p7": brentq(lambda i: V(i) - 0.7, 1e-4, 5.0),
            "i_at_0p5": brentq(lambda i: V(i) - 0.5, 1e-4, 5.0),
            "p_max": float(pp.max()), "i_pmax": float(ii[pp.argmax()]),
            "V_pmax": float(vv[pp.argmax()]),
            "x_vapour": fc.product_water_vapour_fraction(),
        }
        lab = name.replace("_", r"\_")
        ax1.plot(ii, vv, color=C[k], ls=LS[k], label=lab)
        ax2.plot(ii, pp, color=C[k], ls=LS[k], label=lab)
        ax2.plot(out[name]["i_pmax"], out[name]["p_max"], MK[k], color=C[k], ms=4)
    ax1.set_xlabel(r"current density $j$ [A cm$^{-2}$]")
    ax1.set_ylabel(r"cell voltage $V_\mathrm{cell}$ [V]")
    ax1.set_ylim(0, 1.15)
    ax2.set_xlabel(r"current density $j$ [A cm$^{-2}$]")
    ax2.set_ylabel(r"power density $jV_\mathrm{cell}$ [W cm$^{-2}$]")
    ax1.legend(loc="lower left")
    ax1.set_title("(a) polarization curve", loc="left")
    ax2.set_title("(b) power density (marker: maximum)", loc="left")
    fig.tight_layout()
    save(fig, "fig_polarization.pdf")

    # --- loss breakdown of the reference model
    print("[cell] loss breakdown")
    fc = ready_fuelcell()
    P = fc.Target_Press
    ii = np.linspace(1e-3, 0.999 * fc.j_lim, 600)
    ohm = fc.R_ohm * ii
    conc = -fc.B_conc * np.log(1 - ii / fc.j_lim)
    vv = np.array([fc.PolarizationCurve(x, P) for x in ii])
    eta0 = fc.Voc - ohm - conc - vv           # the Kulikovsky term, by difference (V > 1e-3)
    fig, ax = plt.subplots(figsize=(HALF + 0.4, 2.5))
    ax.plot(ii, eta0, color=C[0], ls=LS[0], label=r"$\eta_0$ (CCL activation + transport)")
    ax.plot(ii, ohm, color=C[1], ls=LS[1], label=r"$R_\Omega j$ (ohmic)")
    ax.plot(ii, conc, color=C[2], ls=LS[2], label=r"$V_\mathrm{conc}$ (empirical)")
    ax.set_xlabel(r"current density $j$ [A cm$^{-2}$]")
    ax.set_ylabel("voltage loss [V]")
    ax.legend(loc="upper left")
    fig.tight_layout()
    save(fig, "fig_losses.pdf")
    j_mark = [0.1, 0.5, 1.0, 1.147, 1.5]
    out["loss_breakdown_GoodPerformance"] = {
        str(j): {"eta0": float(np.interp(j, ii, eta0)), "ohm": fc.R_ohm * j,
                 "conc": float(-fc.B_conc * np.log(1 - j / fc.j_lim)),
                 "V": fc.PolarizationCurve(j, P)} for j in j_mark}

    # --- state of health
    print("[cell] degraded curves")
    states = [("BOL", {}), (r"$\Delta V$ = 25 mV", {"voltage_loss": 0.025}),
              (r"$\Delta V$ = 50 mV", {"voltage_loss": 0.05}),
              (r"$k_R$ = 1.5", {"ohmic_resistance_factor": 1.5}),
              (r"$k_i$ = 0.5", {"exchange_current_factor": 0.5})]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(FULL, 2.6))
    soh = {}
    for k, (lab, st) in enumerate(states):
        fc.set_state_of_health(**st)
        vv = np.array([fc.PolarizationCurve(x, P) for x in ii])
        ax1.plot(ii, vv, color=C[k], ls=LS[k], label=lab)
        ax2.plot(ii, ii * vv, color=C[k], ls=LS[k], label=lab)
        V = lambda i: fc.PolarizationCurve(i, P)
        soh[lab] = {"i_at_0p5": brentq(lambda i: V(i) - 0.5, 1e-4, 5.0),
                    "V_at_0p3": V(0.3), "V_at_1p0": V(1.0),
                    "p_max": float((ii * vv).max())}
    fc.set_state_of_health()
    ax1.axhline(0.5, color=MUTED, lw=0.8, ls=":")
    ax1.set_xlabel(r"current density $j$ [A cm$^{-2}$]")
    ax1.set_ylabel(r"cell voltage $V_\mathrm{cell}$ [V]")
    ax1.set_ylim(0, 1.1)
    ax2.set_xlabel(r"current density $j$ [A cm$^{-2}$]")
    ax2.set_ylabel(r"power density [W cm$^{-2}$]")
    ax1.legend(loc="lower left")
    ax1.set_title("(a) polarization curve", loc="left")
    ax2.set_title("(b) power density", loc="left")
    fig.tight_layout()
    save(fig, "fig_degradation_curves.pdf")
    out["state_of_health"] = soh

    # --- product-water vapour fraction
    print("[cell] vapour fraction")
    rh = np.linspace(0, 1, 201)
    fig, ax = plt.subplots(figsize=(HALF + 0.4, 2.5))
    xv = {}
    for k, (Pbar, lam) in enumerate([(1.2, 2.0), (1.5, 2.0), (2.0, 2.0), (1.5, 1.5)]):
        fc.Target_Press, fc.stoich = Pbar * 1e5, lam
        vals = []
        for r in rh:
            fc.inlet_rh = r
            vals.append(fc.product_water_vapour_fraction())
        ax.plot(rh, vals, color=C[k], ls=LS[k],
                label=rf"$P$ = {Pbar:.1f} bar, $\lambda$ = {lam:.1f}")
        xv[f"{Pbar}bar_lambda{lam}"] = {str(r): float(np.interp(r, rh, vals))
                                         for r in (0.5, 0.6, 0.7, 0.8, 0.9)}
    fc.Target_Press, fc.stoich, fc.inlet_rh = P, 2.0, 0.0
    ax.set_xlabel(r"cathode inlet relative humidity $\phi_\mathrm{in}$ [-]")
    ax.set_ylabel(r"vapour fraction $x_v$ [-]")
    ax.legend(loc="lower left")
    fig.tight_layout()
    save(fig, "fig_vapour_fraction.pdf")
    out["x_vapour_vs_rh"] = xv
    out["p_sat_80C"] = fc.water_saturation_pressure(353.15)
    out["V_tn_HHV"] = fc.DELTA_H_REACT / (2 * F)
    out["V_tn_LHV"] = fc.DELTA_H_REACT_LHV / (2 * F)
    store("cell", out)


# =========================================================================== reference
def operating_point(fc, alt, vel, P_prop):
    fc.reset_adequacy()
    pr = fc.ComputePRatio(alt, vel, P_prop)
    return {"PRatio": float(pr[0]), "i": fc.i_op_last, "V": fc.v_cell_last,
            "eta_fcs": fc.eta_fcs_last, "Q": fc.Q_thermal, "mdot_h2": fc.mdot_h2,
            "P_gross": fc.P_gross_last, "P_comp_net": fc.P_comp_net_last,
            "P_turb": fc.P_turb_last, "x_v": fc.x_vapour,
            "load_ratio": fc._worst_load_ratio, "limited": fc._power_limited}


def mission_history(a, dt=5.0, t_end=None):
    """Re-evaluate the fuel-cell operating point on a uniform time grid along the flown
    mission (Beta interpolated from mission.integral_solution). Works on a copy."""
    a = copy.deepcopy(a)
    m, fc, prof = a.mission, a.fuelcell, a.mission.profile
    t_s = np.concatenate([s.t for s in m.integral_solution])
    b_s = np.concatenate([s.y[-1] if a.Configuration == "Hydrogen" else s.y[1]
                          for s in m.integral_solution])
    t_end = prof.MissionTime2 if t_end is None else t_end
    t = np.arange(0.0, t_end, dt)
    rows = []
    for tk in t:
        beta = float(np.interp(tk, t_s, b_s))
        alt, vel = float(prof.Altitude(tk)), float(prof.Velocity(tk))
        PP = m.WTO * a.performance.PoWTO(a.DesignWTOoS, beta, prof.PowerExcess(tk), 1,
                                         alt, m.DISA, vel, "TAS")
        PP = max(PP, 0.0)
        phi = float(prof.SuppliedPowerRatio(tk)) if a.Configuration == "FuelCellBattery" else 0.0
        P_fc = (1 - phi) * PP
        op = operating_point(fc, alt, vel, P_fc)
        eta_m = fc.EtaGB * fc.EtaEM * fc.EtaPM * fc.EtaProp
        P_elec = P_fc / eta_m + fc.P_aux_tms
        rows.append(dict(t=tk, alt=alt, vel=vel, PP=PP, P_fc=P_fc, P_elec=P_elec, **op))
    return {k: np.array([r[k] for r in rows]) for k in rows[0]}


def group_reference():
    print("[reference] designing hydrogen_config() ...")
    a = design(hydrogen_config())
    fc, m, w = a.fuelcell, a.mission, a.weight
    eta_down = fc.EtaEM * fc.EtaPM * fc.EtaGB * fc.EtaProp
    i_ref = brentq(lambda i: fc.PolarizationCurve(i, fc.Target_Press, bol=True) - 0.7, 1e-4, 5)
    area = fc.N_cells * fc.A_cell_reale
    M_stack = area * 0.7 * i_ref / fc.Stack_PD
    P_elec_prop = fc.P_fc_rated - fc.P_aux_tms
    sp_motor = a.powertrain.SPowerPT[1]
    sp_pmad = a.powertrain.pmad_specific_power()
    out = {
        "WTO": w.WTO, "WPT": w.WPT, "WH2": w.WH2_Fuel, "WTank": w.WTank,
        "WHEX": w.WHeat_Exchanger, "WStructure": w.WStructure, "reserve": w.final_reserve,
        "payload": w.WPayload, "crew": w.WCrew,
        "N_cells": fc.N_cells, "A_cell_cm2": fc.A_cell_reale, "A_total_m2": area / 1e4,
        "P_fc_rated": fc.P_fc_rated, "i_design": fc.i_max_density, "V_design": fc.V_cell_design,
        "i_ref_0p7": i_ref, "kg_per_m2": 1e4 * 0.7 * i_ref / fc.Stack_PD,
        "M_stack": M_stack, "M_BoP": M_stack * fc.BoP_Mass_Ratio,
        "M_EM": P_elec_prop * fc.EtaPM / sp_motor, "M_PM": fc.P_fc_rated / sp_pmad,
        "sp_motor": sp_motor, "sp_pmad": sp_pmad, "eta_downstream": eta_down,
        "TO_PP": m.TO_PP, "Max_PEng": m.Max_PEng, "Q_TO": m.TO_FC_Thermal_Pwr,
        "Q_max_mission": m.Max_FC_Thermal_Pwr, "Q_max_alt": m.Max_FC_Thermal_Pwr_alt,
        "E_ground": m.E_ground, "beta0": m.beta0, "E_total": float(m.Ef[-1]),
        "DesignPW": a.DesignPW, "DesignWTOoS": a.DesignWTOoS,
        "report": {k: (v if not isinstance(v, (np.bool_,)) else bool(v))
                   for k, v in fc.report_sizing().items()},
        "x_vapour": fc.x_vapour, "MissionTime": m.profile.MissionTime,
        "MissionTime2": m.profile.MissionTime2,
    }
    # ground segments
    alt_to, v_to = m._ground_condition()
    P_TOfield = m._takeoff_power(w.WTO)
    out["P_takeoff_field"] = P_TOfield
    out["P_oei"] = m._oei_climb_power(w.WTO)
    out["taxi"] = operating_point(copy.deepcopy(fc), alt_to, v_to, m.taxi_power_fraction * P_TOfield)
    out["takeoff_op"] = operating_point(copy.deepcopy(fc), alt_to, v_to, m.TO_PP)

    # --- efficiency and heat versus load at several altitudes
    print("[reference] load sweeps")
    f = copy.deepcopy(fc)
    alts = [0.0, 3000.0, 6000.0, 8000.0]
    vel = 120.0
    P_max_prop = fc.P_fc_rated * eta_down
    loads = np.linspace(0.02, 1.15, 120)
    sweep = {}
    for alt in alts:
        rows = [operating_point(f, alt, vel, x * P_max_prop) for x in loads]
        sweep[alt] = {k: np.array([r[k] for r in rows]) for k in rows[0]}
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(FULL, 2.6))
    for k, alt in enumerate(alts):
        s = sweep[alt]
        ok = ~s["limited"]
        lab = f"{alt/1000:.0f} km"
        ax1.plot(loads[ok], s["eta_fcs"][ok], color=C[k], ls=LS[k], label=lab)
        ax2.plot(loads[ok], s["P_comp_net"][ok] / s["P_gross"][ok], color=C[k], ls=LS[k], label=lab)
    ax1.set_xlabel(r"net electrical load $P_\mathrm{el}/P_\mathrm{fc,rated}$ [-]")
    ax1.set_ylabel(r"net system efficiency $\eta_\mathrm{FCS}$ (HHV) [-]")
    ax2.set_xlabel(r"net electrical load $P_\mathrm{el}/P_\mathrm{fc,rated}$ [-]")
    ax2.set_ylabel(r"$P_\mathrm{comp,net}/P_\mathrm{gross}$ [-]")
    ax1.legend(title="altitude", loc="lower center")
    ax1.set_title("(a) efficiency", loc="left")
    ax2.set_title("(b) net air-system power", loc="left")
    fig.tight_layout()
    save(fig, "fig_efficiency_load.pdf")
    eff = {}
    for alt in alts:
        s = sweep[alt]
        ok = ~s["limited"]
        lim_load = float(loads[ok][-1]) if ok.any() else None
        eff[str(int(alt))] = {
            "eta_at_load": {str(l): float(np.interp(l, loads[ok], s["eta_fcs"][ok]))
                            for l in (0.05, 0.1, 0.3, 0.5, 0.8, 1.0) if l <= lim_load},
            "eta_max": float(s["eta_fcs"][ok].max()),
            "load_eta_max": float(loads[ok][np.argmax(s["eta_fcs"][ok])]),
            "comp_frac_at_load1": float(np.interp(min(1.0, lim_load), loads[ok],
                                                  (s["P_comp_net"] / s["P_gross"])[ok])),
            "last_feasible_load": lim_load,
        }
    out["efficiency_vs_load"] = eff

    # heat per unit net electric power
    fig, ax = plt.subplots(figsize=(HALF + 0.4, 2.5))
    heat = {}
    for k, (alt, xv) in enumerate([(0.0, 1.0), (8000.0, 1.0), (0.0, 0.0), (8000.0, 0.0)]):
        g = copy.deepcopy(fc)
        g.x_vapour_spec = xv              # fixed product-water phase (overrides 'auto')
        rows = [operating_point(g, alt, vel, x * P_max_prop) for x in loads]
        Q = np.array([r["Q"] for r in rows])
        lim = np.array([r["limited"] for r in rows])
        Pel = loads * P_max_prop / eta_down
        ax.plot(loads[~lim], (Q / Pel)[~lim], color=C[k], ls=LS[k],
                label=rf"{alt/1000:.0f} km, $x_v$ = {xv:.0f}")
        heat[f"{int(alt)}m_xv{xv:.0f}"] = {str(l): float(np.interp(l, loads[~lim], (Q / Pel)[~lim]))
                                          for l in (0.1, 0.5, 0.8, 1.0)}
    ax.set_xlabel(r"net electrical load $P_\mathrm{el}/P_\mathrm{fc,rated}$ [-]")
    ax.set_ylabel(r"$\dot Q_\mathrm{cool}/P_\mathrm{el}$ [-]")
    ax.legend(loc="upper left")
    fig.tight_layout()
    save(fig, "fig_heat_load.pdf")
    out["heat_per_power"] = heat

    # --- power-limited branch continuity
    print("[reference] power-limited branch")
    g = copy.deepcopy(fc)
    alt, vel = 0.0, 70.0
    g.reset_adequacy()
    g.ComputePRatio(alt, vel, 2.0e7)
    P_lim = 2.0e7 / g._worst_load_ratio
    ratios = np.linspace(0.5, 1.4, 181)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(FULL, 2.5))
    pl = {"P_lim_prop_SL": P_lim}
    for k, (lab, st) in enumerate([("BOL", {}), (r"$\Delta V$ = 50 mV", {"voltage_loss": 0.05})]):
        g.set_state_of_health(**st)
        rows = [operating_point(g, alt, vel, r * P_lim) for r in ratios]
        mh = np.array([r["mdot_h2"] for r in rows]) * 1e3
        Q = np.array([r["Q"] for r in rows]) / 1e6
        lim = np.array([r["limited"] for r in rows])
        for ax, y in ((ax1, mh), (ax2, Q)):
            ax.plot(ratios[~lim], y[~lim], color=C[k], ls="-", label=f"{lab}, feasible")
            ax.plot(ratios[lim], y[lim], color=C[k], ls="--", label=f"{lab}, power-limited")
        first_lim = float(ratios[lim][0]) if lim.any() else None
        pl[lab] = {"first_limited_ratio": first_lim,
                   "mdot_at_1p2": float(np.interp(1.2, ratios, mh)),
                   "Q_at_1p2": float(np.interp(1.2, ratios, Q))}
    g.set_state_of_health()
    for ax in (ax1, ax2):
        ax.axvline(1.0, color=MUTED, lw=0.8, ls=":")
        ax.set_xlabel(r"demand / BOL deliverable power [-]")
    ax1.set_ylabel(r"hydrogen flow $\dot m_\mathrm{H_2}$ [g s$^{-1}$]")
    ax2.set_ylabel(r"coolant heat $\dot Q_\mathrm{cool}$ [MW]")
    ax1.legend(loc="upper left")
    ax1.set_title("(a) hydrogen", loc="left")
    ax2.set_title("(b) heat", loc="left")
    fig.tight_layout()
    save(fig, "fig_power_limited.pdf")
    out["power_limited"] = pl

    # --- mission history
    print("[reference] mission history")
    h = mission_history(a, dt=5.0)
    tm = h["t"] / 60.0
    fig, axes = plt.subplots(3, 2, figsize=(FULL, 5.6), sharex=True)
    ax = axes.ravel()
    ax[0].plot(tm, h["alt"] / 1e3, color=C[0]); ax[0].set_ylabel("altitude [km]")
    ax[1].plot(tm, h["P_elec"] / 1e6, color=C[0], label="net electrical")
    ax[1].plot(tm, h["P_gross"] / 1e6, color=C[1], ls="--", label="gross stack")
    ax[1].set_ylabel("fuel-cell power [MW]"); ax[1].legend(loc="upper right")
    ax[2].plot(tm, h["i"], color=C[0]); ax[2].set_ylabel(r"$j$ [A cm$^{-2}$]")
    ax[2].axhline(fc.i_max_density, color=MUTED, lw=0.8, ls=":")
    ax[3].plot(tm, h["V"], color=C[0]); ax[3].set_ylabel(r"$V_\mathrm{cell}$ [V]")
    ax[3].axhline(fc.V_cell_design, color=MUTED, lw=0.8, ls=":")
    ax[4].plot(tm, h["Q"] / 1e6, color=C[0]); ax[4].set_ylabel(r"$\dot Q_\mathrm{cool}$ [MW]")
    ax[5].plot(tm, h["eta_fcs"], color=C[0]); ax[5].set_ylabel(r"$\eta_\mathrm{FCS}$ (HHV) [-]")
    ax[5].set_ylim(0, 0.6)
    for x in ax:
        x.axvline(m.profile.MissionTime / 60, color=MUTED, lw=0.8, ls="-.")
    ax[4].set_xlabel("time [min]"); ax[5].set_xlabel("time [min]")
    fig.tight_layout()
    save(fig, "fig_mission_history.pdf")
    nominal = h["t"] <= m.profile.MissionTime
    climb_end = None
    for seg in m.profile._segments:
        if seg.phase == "Mission" and seg.name == "Cruise":
            cruise = (h["t"] >= seg.start_time) & (h["t"] < seg.end_time)
    out["history"] = {
        "i_max": float(h["i"].max()), "V_min": float(h["V"].min()),
        "Q_max": float(h["Q"].max()), "load_max": float(h["load_ratio"].max()),
        "cruise_i_range": [float(h["i"][cruise].min()), float(h["i"][cruise].max())],
        "cruise_V_range": [float(h["V"][cruise].min()), float(h["V"][cruise].max())],
        "cruise_eta_range": [float(h["eta_fcs"][cruise].min()), float(h["eta_fcs"][cruise].max())],
        "cruise_P_elec_range": [float(h["P_elec"][cruise].min()), float(h["P_elec"][cruise].max())],
        "n_points": int(len(h["t"])), "n_PP_zero": int((h["PP"] <= 0).sum()),
        "time_PP_zero_min": float((h["PP"] <= 0).sum() * 5.0 / 60),
        "mdot_h2_at_PP_zero_gps": (float(h["mdot_h2"][h["PP"] <= 0].mean() * 1e3)
                                   if (h["PP"] <= 0).any() else None),
        "x_v_range": [float(h["x_v"].min()), float(h["x_v"].max())],
    }
    store("reference", out)
    return a


# =========================================================================== sweep
def group_sweep():
    print("[sweep] design-voltage sweep")
    volts = [0.40, 0.45, 0.50, 0.55, 0.60, 0.65]
    rows = []
    for v in volts:
        try:
            a = design(hydrogen_config(v_cell_design=v))
        except Exception as exc:
            print(f"  V={v}: did not close ({type(exc).__name__})")
            rows.append({"V": v, "closed": False})
            continue
        fc, w, m = a.fuelcell, a.weight, a.mission
        i_ref = brentq(lambda i: fc.PolarizationCurve(i, fc.Target_Press, bol=True) - 0.7, 1e-4, 5)
        area = fc.N_cells * fc.A_cell_reale
        rows.append({"V": v, "closed": True, "WTO": w.WTO, "WPT": w.WPT,
                     "M_stack": area * 0.7 * i_ref / fc.Stack_PD, "WH2": w.WH2_Fuel,
                     "WHEX": w.WHeat_Exchanger, "WTank": w.WTank, "N_cells": fc.N_cells,
                     "i_design": fc.i_max_density, "A_total_m2": area / 1e4,
                     "P_fc_rated": fc.P_fc_rated, "worst_load": fc._worst_load_ratio,
                     "Q_peak": max(m.Max_FC_Thermal_Pwr, m.TO_FC_Thermal_Pwr)})
        print(f"  V={v:.2f}: WTO {w.WTO:,.0f} kg")
    ok = [r for r in rows if r["closed"]]
    v = [r["V"] for r in ok]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(FULL, 2.6))
    ax1.plot(v, [r["WTO"] / 1e3 for r in ok], "o-", color=C[0])
    ax1.set_ylabel(r"take-off mass $W_\mathrm{TO}$ [t]")
    ax1.set_title("(a) take-off mass", loc="left")
    for k, (key, lab) in enumerate([("WPT", "fuel-cell system (stack + BoP + drive)"),
                                    ("M_stack", "stack only"), ("WH2", r"H$_2$ load"),
                                    ("WHEX", "TMS (Class I)")]):
        ax2.plot(v, [r[key] for r in ok], ls=LS[k], marker=MK[k], color=C[k], label=lab)
    ax2.set_ylabel("mass [kg]")
    ax2.set_title("(b) component masses", loc="left")
    ax2.legend(loc="upper left")
    for ax in (ax1, ax2):
        ax.set_xlabel(r"design cell voltage $V_\mathrm{cell,des}$ [V]")
    fig.tight_layout()
    save(fig, "fig_voltage_sweep.pdf")
    store("sweep", rows)


# =========================================================================== EOL
def group_eol():
    print("[eol] end-of-life sizing")
    out = {}
    for lab, dv in (("BOL", 0.0), ("EOL_50mV", 0.05)):
        cfg = hydrogen_config()
        cfg.energy.fc_voltage_loss = dv
        a = design(cfg)
        fc, w, m = a.fuelcell, a.weight, a.mission
        out[lab] = {"WTO": w.WTO, "WPT": w.WPT, "WH2": w.WH2_Fuel, "WHEX": w.WHeat_Exchanger,
                    "i_design": fc.i_max_density,
                    "A_total_m2": fc.N_cells * fc.A_cell_reale / 1e4,
                    "Q_peak": max(m.Max_FC_Thermal_Pwr, m.TO_FC_Thermal_Pwr)}
        print(f"  {lab}: WTO {w.WTO:,.0f} kg")
    store("eol", out)


# =========================================================================== FC + battery
def group_fcb():
    print("[fcb] example-30 take-off-sized FC + battery design")
    ex30 = load_example30()
    a = quiet(ex30.fc_battery_design)
    fc, w, m = a.fuelcell, a.weight, a.mission
    out = {"WTO": w.WTO, "WPT": w.WPT, "WBat": w.WBat, "WH2": w.WH2_Fuel,
           "WHEX": w.WHeat_Exchanger, "P_fc_rated": fc.P_fc_rated,
           "i_design": fc.i_max_density, "TO_PP": m.TO_PP, "TO_PBat": m.TO_PBat,
           "Max_PEng": m.Max_PEng, "MissionTime": m.profile.MissionTime}

    # duty: nominal mission (diversion excluded) on a 2 s grid, plus taxi-out / taxi-in
    h = mission_history(a, dt=2.0, t_end=m.profile.MissionTime)
    alt_to, v_to = m._ground_condition()
    P_to = m._takeoff_power(w.WTO)
    phi_taxi = m._taxi_phi()
    taxi = operating_point(copy.deepcopy(fc), alt_to, v_to,
                           (1 - phi_taxi) * m.taxi_power_fraction * P_to)
    takeoff = operating_point(copy.deepcopy(fc), alt_to, v_to,
                              (1 - m._takeoff_phi()) * m.takeoff_power_fraction * P_to)
    t_taxi = (m.taxi_out_time + m.taxi_in_time) * 60.0
    t_to = m.takeoff_time * 60.0
    rel = h["i"] / fc.i_max_density
    dt = 2.0
    edges = np.linspace(0, 1.0, 21)
    flight_h, _ = np.histogram(np.clip(rel, 0, 0.9999), bins=edges)
    flight_min = flight_h * dt / 60
    ground_min = np.zeros_like(flight_min)
    ground_min[min(int(taxi["i"] / fc.i_max_density * 20), 19)] += t_taxi / 60
    ground_min[min(int(takeoff["i"] / fc.i_max_density * 20), 19)] += t_to / 60
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(FULL, 2.6))
    centers = 0.5 * (edges[1:] + edges[:-1])
    width = (edges[1] - edges[0]) * 0.92
    ax1.bar(centers, flight_min, width=width, color=C[0], label="flight (nominal mission)")
    ax1.bar(centers, ground_min, width=width, bottom=flight_min, color=C[1],
            label="taxi and take-off run")
    ax1.set_xlabel(r"$j/j_\mathrm{des}$ [-]")
    ax1.set_ylabel("time [min]")
    ax1.legend(loc="upper right")
    ax1.set_title("(a) time at current density", loc="left")
    tm = h["t"] / 60
    ax2.plot(tm, h["V"], color=C[0])
    ax2.axhline(fc.V_cell_design, color=MUTED, lw=0.8, ls=":")
    ax2.set_xlabel("time [min]")
    ax2.set_ylabel(r"$V_\mathrm{cell}$ [V]")
    ax2.set_title("(b) cell voltage in flight", loc="left")
    fig.tight_layout()
    save(fig, "fig_duty_histogram.pdf")
    T_flight = h["t"][-1] + dt
    out["duty"] = {
        "flight_min": T_flight / 60, "taxi_min": t_taxi / 60, "takeoff_min": t_to / 60,
        "taxi_rel_i": taxi["i"] / fc.i_max_density, "taxi_V": taxi["V"],
        "takeoff_rel_i": takeoff["i"] / fc.i_max_density, "takeoff_V": takeoff["V"],
        "frac_flight_5_30pct": float(((rel >= 0.05) & (rel < 0.30)).sum() * dt / T_flight),
        "V_range_5_30pct": [float(h["V"][(rel >= 0.05) & (rel < 0.30)].min()),
                            float(h["V"][(rel >= 0.05) & (rel < 0.30)].max())],
        "min_above_0p80V": float((h["V"] > 0.80).sum() * dt / 60),
        "frac_flight_above_80pct": float((rel >= 0.8).sum() * dt / T_flight),
        "max_rel_i_flight": float(rel.max()),
        "flight_hist_min": flight_min.tolist(), "edges": edges.tolist(),
    }

    # same duty over the whole profile (mission + diversion), as quoted in the user guide
    hw = mission_history(a, dt=2.0)
    relw = hw["i"] / fc.i_max_density
    Tw = len(hw["t"]) * 2.0
    out["duty_whole_profile"] = {
        "flight_min": Tw / 60, "min_above_0p80V": float((hw["V"] > 0.80).sum() * 2.0 / 60),
        "frac_5_30pct": float(((relw >= 0.05) & (relw < 0.30)).sum() * 2.0 / Tw)}

    # degraded flights at the design range
    print("[fcb] degraded flights")
    rng = a.MissionInput["Range Mission"]
    states = [("BOL", {}), ("dV=25mV", {"fc_voltage_loss": 0.025}),
              ("dV=50mV", {"fc_voltage_loss": 0.05}),
              ("kR=1.5", {"fc_ohmic_resistance_factor": 1.5}),
              ("ki=0.5", {"fc_exchange_current_factor": 0.5})]
    deg = {}
    for lab, st in states:
        r = quiet(ex30.fly_off_design, a, rng, state_of_health=st)
        b = copy.deepcopy(a)
        ex30._set_state_of_health(b, st)
        b.fuelcell.reset_adequacy()
        quiet(b.mission.EvaluateMission, r.WTO)
        deg[lab] = {"trip_fuel": r.trip_fuel, "WTO": r.WTO, "fuel_load": r.fuel_load,
                    "violations": r.violations,
                    "Q_peak": ex30._fc_design_heat(b.mission),
                    "worst_load": b.fuelcell._worst_load_ratio}
        print(f"  {lab}: trip H2 {r.trip_fuel:.1f} kg, {r.violations}")
    out["degraded"] = deg
    out["Q_design"] = ex30._fc_design_heat(m)
    out["design_fuel_load"] = w.Wf
    store("fcb", out)


# =========================================================================== take-off assist
def group_assist():
    print("[assist] take-off assist sweep (example 23 strategy 'takeoff')")
    phis = [0.00, 0.05, 0.10, 0.15, 0.20, 0.30]
    res = {}
    for field in (1107.0, 800.0):
        rows = []
        for phi in phis:
            cfg = fuelcell_battery_config(cruise_phi=0.0)
            cfg.constraints.phases["Take Off"]["sTO"] = field
            for seg in cfg.mission_stages.segments:
                if seg.name == "Takeoff":
                    seg.phi = phi
                elif seg.segment_type in ("ConstantRateClimb", "ConstantMachCruise"):
                    seg.phi_start = seg.phi_end = 0.0
            try:
                a = design(cfg)
            except Exception as exc:
                print(f"  field {field}, phi {phi}: failed ({type(exc).__name__})")
                rows.append(None)
                continue
            mm = a.mission
            rows.append({"phi": phi, "WTO": a.weight.WTO, "WPT": a.weight.WPT,
                         "WBat": a.weight.WBat, "WH2": a.weight.WH2_Fuel,
                         "P_TO_total": mm.TO_PP / (1.0 - phi),   # propulsive TO/OEI requirement
                         "TO_PP": mm.TO_PP, "TO_PBat_terminal": mm.TO_PBat,
                         "Max_PEng": mm.Max_PEng})
            print(f"  field {field:.0f} m, phi {phi:.2f}: WTO {a.weight.WTO:,.0f} kg")
        base = rows[0]
        res[str(int(field))] = {"rows": rows,
                                "phi_star": max(0.0, 1 - base["Max_PEng"] / base["P_TO_total"])}
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(FULL, 2.6))
    for k, field in enumerate(("1107", "800")):
        rows = [r for r in res[field]["rows"] if r]
        p = [r["phi"] for r in rows]
        ax1.plot(p, [r["WTO"] / 1e3 for r in rows], ls=LS[k], marker=MK[k], color=C[k],
                 label=f"{field} m field")
        ax2.plot(p, [r["WPT"] for r in rows], ls="-", marker=MK[k], color=C[k],
                 label=f"fuel-cell system, {field} m")
        ax2.plot(p, [r["WBat"] for r in rows], ls="--", marker=MK[k], color=C[k], mfc="white",
                 label=f"battery, {field} m")
        if res[field]["phi_star"] > 0:
            ax1.axvline(res[field]["phi_star"], color=C[k], lw=0.8, ls=":")
    ax1.set_xlabel(r"take-off battery share $\varphi_\mathrm{TO}$ [-]")
    ax1.set_ylabel(r"$W_\mathrm{TO}$ [t]")
    ax1.legend(loc="upper left")
    ax1.set_title(r"(a) take-off mass (dotted: $\varphi^*$)", loc="left")
    ax2.set_xlabel(r"take-off battery share $\varphi_\mathrm{TO}$ [-]")
    ax2.set_ylabel("mass [kg]")
    ax2.legend(loc="center right", fontsize=6.5)
    ax2.set_title("(b) fuel-cell system and battery", loc="left")
    fig.tight_layout()
    save(fig, "fig_takeoff_assist.pdf")
    store("assist", res)


# =========================================================================== weather
def group_weather():
    """Ambient humidity, hot day and humidifier on common.hydrogen_config()."""
    print("[weather] humidity and hot-day study")
    cases = [("ISA, dry", 0.0, 0.0, 0.0), ("ISA, saturated", 0.0, 1.0, 0.0),
             ("ISA+20, dry", 20.0, 0.0, 0.0), ("ISA+20, saturated", 20.0, 1.0, 0.0),
             ("ISA, dry, humidifier RH 1", 0.0, 0.0, 1.0)]
    out = {}
    for lab, disa, rh_amb, rh_hum in cases:
        cfg = hydrogen_config()
        cfg.energy.fc_ambient_relative_humidity = rh_amb
        cfg.energy.fc_cathode_inlet_rh = rh_hum
        cfg.mission.disa = disa                    # mission ISA deviation; constraints stay at ISA
        a = pg.build_aircraft()
        quiet(a.configure, cfg)
        fc, w, m = a.fuelcell, a.weight, a.mission
        alt_to, _ = m._ground_condition()
        P_amb, T_amb = fc._get_env(alt_to)
        out[lab] = {"WTO": w.WTO, "WPT": w.WPT, "WH2": w.WH2_Fuel, "WHEX": w.WHeat_Exchanger,
                    "Q_TO": m.TO_FC_Thermal_Pwr, "Q_mission": m.Max_FC_Thermal_Pwr,
                    "inlet_rh_TO": fc.cathode_inlet_rh(P_amb, T_amb),
                    "x_v_TO": fc.vapour_fraction_at(P_amb, T_amb),
                    "P_fc_rated": fc.P_fc_rated, "DesignPW": a.DesignPW}
        print(f"  {lab}: WTO {w.WTO:,.0f} kg, inlet RH at TO {out[lab]['inlet_rh_TO']:.3f}, "
              f"x_v {out[lab]['x_v_TO']:.2f}")
    base = out["ISA, dry"]
    for lab, r in out.items():
        r["dWTO_pct"] = 100 * (r["WTO"] / base["WTO"] - 1)
        r["dWHEX_pct"] = 100 * (r["WHEX"] / base["WHEX"] - 1)
        r["dQ_TO_pct"] = 100 * (r["Q_TO"] / base["Q_TO"] - 1)
        r["dWH2_pct"] = 100 * (r["WH2"] / base["WH2"] - 1)

    # cathode inlet RH carried by saturated ambient air, against altitude
    fc = ready_fuelcell()
    fc.ambient_rh = 1.0
    alts = np.linspace(0, 9000, 91)
    fig, ax = plt.subplots(figsize=(HALF + 0.4, 2.5))
    prof = {}
    for k, disa in enumerate((0.0, 20.0)):
        rh = []
        for h in alts:
            from PhlyGreen.Utilities import Atmosphere as ISAmod
            P, T = ISAmod.atmosphere.Pstd(h), ISAmod.atmosphere.Tstd(h) + disa
            rh.append(fc.cathode_inlet_rh(P, T))
        ax.plot(alts / 1e3, rh, color=C[k], ls=LS[k], label=f"ISA{'+%d' % disa if disa else ''}")
        prof[str(int(disa))] = {"SL": rh[0], "8km": float(np.interp(8000, alts, rh))}
    ax.set_xlabel("altitude [km]")
    ax.set_ylabel(r"cathode inlet RH at $T_\mathrm{op}$ [-]")
    ax.legend(loc="upper right")
    fig.tight_layout()
    save(fig, "fig_humidity.pdf")
    out["inlet_rh_saturated_ambient"] = prof
    store("weather", out)


GROUPS = {"cell": group_cell, "reference": group_reference, "sweep": group_sweep,
          "eol": group_eol, "fcb": group_fcb, "assist": group_assist,
          "weather": group_weather}

if __name__ == "__main__":
    os.chdir(TRUNK)
    todo = sys.argv[1:] or list(GROUPS)
    for g in todo:
        GROUPS[g]()
