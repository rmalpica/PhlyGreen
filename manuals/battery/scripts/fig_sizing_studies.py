"""Design sweeps on the hybrid baselines of examples/common.py.

fig_class_i_sizing.pdf : Class-I battery mass candidates (energy, mission power, take-off power)
                         vs the cruise phi and vs the take-off phi.
fig_soh_sizing.pdf     : end-of-life sizing, battery mass vs capacity fraction and resistance factor.
fig_taxi_phi.pdf       : ground-segment energy split and design response vs taxi_phi.
data/sizing.json       : the numbers quoted in the manual (also serial / range-extender / FC+battery).
"""

import numpy as np

from _setup import C, GREY, TEXTWIDTH, plt, save, dump, label_panel, design

from common import hybrid_config, fuelcell_battery_config


def set_phi(cfg, cruise=None, takeoff=None):
    for s in cfg.mission_stages.segments:
        if s.name == "Cruise" and cruise is not None:
            s.phi, s.phi_start, s.phi_end = None, cruise, cruise
        if s.name == "Takeoff" and takeoff is not None:
            s.phi = takeoff
    return cfg


def class_i_candidates(a):
    """The three Class-I mass candidates of Weight.Hybrid at the converged design [kg]."""
    b, m, w = a.battery, a.mission, a.weight
    return {"energy": w.TotalEnergies[1] / (1 - b.SOC_min) / b.Ebat,
            "mission_power": m.Max_PBat / b.pbat, "takeoff_power": m.TO_PBat / b.pbat,
            "WBat": w.WBat, "WTO": w.WTO, "Wf": w.Wf, "E_bat_kWh": w.TotalEnergies[1] / 3.6e6,
            "Max_PBat": m.Max_PBat, "TO_PBat": m.TO_PBat, "Takeoff_PBat": m.Takeoff_PBat,
            "Taxi_PBat": m.Taxi_PBat, "EBat_ground_MJ": m.EBat_ground / 1e6,
            "WMotor": a.powertrain.WMotor, "WPMAD": a.powertrain.WPMAD, "idx": int(w.WBatidx),
            "Max_PMotor": float(m.Max_PMotor), "TO_PMotor": float(m.TO_PMotor),
            "Max_PBus": float(m.Max_PBus), "TO_PBus": float(m.TO_PBus),
            "engineRating": float(a.powertrain.engineRating)}


def summary(a):
    w, m, b = a.weight, a.mission, a.battery
    d = {"WTO": w.WTO, "WBat": w.WBat, "Wf": w.Wf, "E_bat_kWh": w.TotalEnergies[1] / 3.6e6,
         "Max_PBat": m.Max_PBat, "TO_PBat": m.TO_PBat, "WPT": w.WPT}
    if getattr(b, "BatteryClass", None) == "II":
        d.update({"P": b.P_number, "S": b.S_number, "WHEX": w.WHeat_Exchanger,
                  "it0_As": float(m.integral_solution[0].y[3][0]),
                  "T0_C": float(m.integral_solution[0].y[4][0] - 273.15)})
    return d


def main():
    out = {}

    # ---------------- Class-I mass candidates vs phi ----------------
    cruise = np.round(np.arange(0.0, 0.51, 0.05), 2)
    rows_c = []
    for p in cruise:
        rows_c.append(class_i_candidates(design(set_phi(hybrid_config("I"), cruise=p))))
    takeoff = np.round(np.arange(0.0, 0.41, 0.05), 2)
    rows_t = []
    for p in takeoff:
        rows_t.append(class_i_candidates(design(set_phi(hybrid_config("I"), cruise=0.0, takeoff=p))))
    out["cruise_phi_sweep"] = {f"{p:g}": r for p, r in zip(cruise, rows_c)}
    out["takeoff_phi_sweep"] = {f"{p:g}": r for p, r in zip(takeoff, rows_t)}

    fig, axes = plt.subplots(1, 2, figsize=(TEXTWIDTH, 2.7))
    for ax, xs, rows, xl, letter in ((axes[0], cruise, rows_c, r"cruise $\varphi$ (take-off $\varphi$ = 0)", "a"),
                                     (axes[1], takeoff, rows_t, r"take-off $\varphi$ (cruise $\varphi$ = 0)", "b")):
        ax.plot(xs, [r["energy"] for r in rows], "o-", color=C[0], label="energy")
        ax.plot(xs, [r["mission_power"] for r in rows], "s-", color=C[1], label="mission + ground power")
        ax.plot(xs, [r["takeoff_power"] for r in rows], "^-", color=C[2], label="take-off / OEI power")
        ax.plot(xs, [r["WBat"] for r in rows], "-", color=GREY, lw=3, alpha=0.35, label="$W_{bat}$ (max)")
        ax.set_xlabel(xl)
        ax.set_ylabel("battery mass candidate [kg]")
        label_panel(ax, letter)
    axes[0].legend(loc="upper left")
    fig.tight_layout()
    save(fig, "fig_class_i_sizing.pdf")

    # ---------------- end-of-life sizing ----------------
    soh = {"I_c": {}, "II_c": {}, "II_r": {}, "I_TO_r": {}}
    for c in [1.0, 0.9, 0.8, 0.7]:
        cfg = hybrid_config("I"); cfg.energy.battery_capacity_fraction = c
        soh["I_c"][f"{c:g}"] = summary(design(cfg))
    for c in [1.0, 0.9, 0.8]:
        cfg = hybrid_config("II"); cfg.energy.battery_capacity_fraction = c
        soh["II_c"][f"{c:g}"] = summary(design(cfg))
    soh["II_r"]["1"] = soh["II_c"]["1"]
    for r in [1.5, 2.0]:
        cfg = hybrid_config("II"); cfg.energy.battery_resistance_factor = r
        soh["II_r"][f"{r:g}"] = summary(design(cfg))
    for r in [1.0, 1.5, 2.0]:
        cfg = set_phi(hybrid_config("I"), cruise=0.0, takeoff=0.3)
        cfg.energy.battery_resistance_factor = r
        soh["I_TO_r"][f"{r:g}"] = summary(design(cfg))
    out["soh_sizing"] = soh

    fig, axes = plt.subplots(1, 2, figsize=(TEXTWIDTH, 2.6), sharey=True)
    for key, col, mk, lab in (("I_c", C[0], "o", "Class I, $\\varphi$ of hybrid_config"),
                              ("II_c", C[1], "s", "Class II, $\\varphi$ of hybrid_config")):
        xs = [float(k) for k in soh[key]]
        w0 = soh[key]["1"]["WBat"]
        axes[0].plot(xs, [v["WBat"] / w0 for v in soh[key].values()], mk + "-", color=col, label=lab)
    xs = np.linspace(0.7, 1.0, 50)
    axes[0].plot(xs, 1 / xs, ":", color=GREY, label="$1/c$")
    axes[0].set_xlabel("capacity fraction $c = C/C_{BOL}$ [-]")
    axes[0].set_ylabel("$W_{bat} / W_{bat,BOL}$ [-]")
    axes[0].invert_xaxis()
    axes[0].legend(loc="upper left", fontsize=7)
    for key, col, mk, lab in (("II_r", C[1], "s", "Class II, $\\varphi$ of hybrid_config"),
                              ("I_TO_r", C[2], "^", "Class I, take-off battery ($\\varphi_{TO}$ = 0.3)")):
        xs = [float(k) for k in soh[key]]
        w0 = soh[key]["1"]["WBat"]
        axes[1].plot(xs, [v["WBat"] / w0 for v in soh[key].values()], mk + "-", color=col, label=lab)
    axes[1].set_xlabel("resistance factor $r = R/R_{BOL}$ [-]")
    axes[1].legend(loc="upper left", fontsize=7)
    label_panel(axes[0], "a")
    label_panel(axes[1], "b")
    fig.tight_layout()
    save(fig, "fig_soh_sizing.pdf")

    # ---------------- taxi phi ----------------
    taxi = np.round(np.arange(0.0, 1.01, 0.25), 2)
    rows = []
    for p in taxi:
        cfg = hybrid_config("I"); cfg.mission.taxi_phi = float(p)
        a = design(cfg)
        m = a.mission
        rows.append({**class_i_candidates(a), "E_ground_fuel_MJ": m.E_ground / 1e6,
                     "E_taxi_out_takeoff_MJ": m.E_taxi_out_takeoff / 1e6,
                     "EBat_ground_MJ": m.EBat_ground / 1e6, "beta0": m.beta0})
    out["taxi_phi_sweep"] = {f"{p:g}": r for p, r in zip(taxi, rows)}
    fig, axes = plt.subplots(1, 2, figsize=(TEXTWIDTH, 2.6))
    axes[0].plot(taxi, [r["E_ground_fuel_MJ"] for r in rows], "o-", color=C[0], label="fuel (chemical)")
    axes[0].plot(taxi, [r["EBat_ground_MJ"] for r in rows], "s-", color=C[1], label="battery (terminal)")
    axes[0].set_xlabel(r"taxi supplied power ratio $\varphi_{taxi}$ [-]")
    axes[0].set_ylabel("ground-segment energy [MJ]")
    axes[0].legend(loc="center left")
    r0 = rows[0]
    for key, col, mk, lab in (("WBat", C[1], "s", "battery"), ("Wf", C[0], "o", "mission fuel"),
                              ("WTO", C[2], "^", "take-off mass")):
        axes[1].plot(taxi, [r[key] - r0[key] for r in rows], mk + "-", color=col, label=lab)
    axes[1].set_xlabel(r"taxi supplied power ratio $\varphi_{taxi}$ [-]")
    axes[1].set_ylabel("change from $\\varphi_{taxi}$ = 0 [kg]")
    axes[1].legend(loc="upper left")
    label_panel(axes[0], "a")
    label_panel(axes[1], "b")
    fig.tight_layout()
    save(fig, "fig_taxi_phi.pdf")

    # Class-II pack with an electric taxi (state at the start of the climb)
    cfg = hybrid_config("II"); cfg.mission.taxi_phi = 1.0
    out["class_ii_taxi_phi_1"] = summary(design(cfg))

    # ---------------- other configurations ----------------
    cfgs = {}
    a = design(hybrid_config("I", "Serial"))
    cfgs["serial_phi_split"] = {**class_i_candidates(a)}
    cfg = hybrid_config("I", "Serial")
    cfg.energy.gt_rated_power = 3.0e6
    cfg.energy.battery_charge_efficiency = 0.96
    a = design(cfg)
    cfgs["range_extender"] = {**class_i_candidates(a), "swing_kWh": a.weight.TotalEnergies[1] / 3.6e6,
                              "TO_PP": a.mission.TO_PP}
    a = design(fuelcell_battery_config(0.15))
    e = a.EnergyInput
    cfgs["fcb_0.15"] = {"WTO": a.weight.WTO, "WBat": a.weight.WBat, "E_bat_kWh": a.weight.TotalEnergies[1] / 3.6e6,
                        "Max_PBat": a.mission.Max_PBat, "TO_PBat": a.mission.TO_PBat,
                        "energy_mass": a.weight.TotalEnergies[1] / 3600 / (250 * 0.8),
                        "power_mass": a.mission.Max_PBat / 1500}
    out["configurations"] = cfgs
    dump("sizing.json", out)


if __name__ == "__main__":
    main()
