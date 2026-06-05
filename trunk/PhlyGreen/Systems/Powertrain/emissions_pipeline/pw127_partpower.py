"""Phase 3 — part-power fuel-flow correction for the PW127 deck (calibrated power schedule).

The simplified deck under-predicts idle/approach fuel flow (generic maps under-represent
part-power efficiency falloff), and the SFC rise is concentrated at low power — so a single
constant parasitic loss cannot fit all four certification points. We instead calibrate the
**gas-generator gross-power schedule** G(f): for each LTO useful-power fraction f we invert the
deck's FF(gross) curve at the Excel fuel flow to get the gross power that reproduces it, then
interpolate G(f) monotonically. Running the deck at G(f) makes the combustor state (T3, P3, FAR)
self-consistent with the certified fuel flow.

For the flight envelope, gross = G(f) * delta(alt) (the correction lapses with the cycle). The
useful-fraction range the surrogate uses (0.3..1.0, approach..take-off) is exactly the
well-constrained part of the schedule; idle (f=0.07) sits below it and is only an LTO point.

Outputs the corrected combustor-state dataset `pw127_crn_inputs_corrected.csv`.
"""
import os, sys
import numpy as np
from scipy.interpolate import interp1d, PchipInterpolator

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pw127_deck as deck   # noqa: E402

TO_GROSS_HP = 3290.0
LTO_F = {"Taxi": 0.07, "App": 0.30, "Cl": 0.90, "To": 1.00}
FF_EXCEL = {"Taxi": 0.04, "App": 0.08, "Cl": 0.14, "To": 0.16}


def _delta(alt_ft):
    P_std_sl, T_std_sl = 14.696, 518.67
    T_amb = max(T_std_sl - 3.566e-3 * alt_ft, 390.0)
    return (P_std_sl * (T_amb / T_std_sl) ** 5.2561) / P_std_sl


def build_ff_curve(prob, des):
    """SLS off-design sweep -> (gross_hp, FF, T3_K, P3_Pa, FAR, mdot)."""
    od = prob.model.od_pts[0]
    grosses = np.linspace(150.0, TO_GROSS_HP, 18)
    table = []
    for g in grosses:
        s = des if abs(g - TO_GROSS_HP) < 1.0 else deck._od_state(prob, od, 0.0, 1e-3, g, des["base_W"])
        if s is not None:
            table.append([g, s["Wfuel"], s["T3_K"], s["P3_Pa"], s["FAR"], s["mdot"]])
    return np.array(table)


def calibrate_schedule(ff_curve):
    """G(f): gross power vs useful-fraction, from inverting FF(gross) at the Excel points."""
    g, ff = ff_curve[:, 0], ff_curve[:, 1]
    gross_of_ff = interp1d(ff, g, bounds_error=False, fill_value=(g[0], g[-1]))
    fracs = np.array([LTO_F[m] for m in ["Taxi", "App", "Cl", "To"]])
    req_gross = np.array([float(gross_of_ff(FF_EXCEL[m])) for m in ["Taxi", "App", "Cl", "To"]])
    return PchipInterpolator(fracs, req_gross), fracs, req_gross


def main():
    prob = deck._build()
    deck._set_design(prob, TO_GROSS_HP)
    with deck._quiet():
        prob.run_model()
    des = deck._design_state(prob)

    print("Building deck FF(gross) curve and calibrating the power schedule G(f) ...")
    ff_curve = build_ff_curve(prob, des)
    G, fracs, req_gross = calibrate_schedule(ff_curve)
    print(f"\n  useful rated (G at f=1) = {TO_GROSS_HP:.0f} hp gross; "
          f"required gross at LTO fractions:")
    for m in ["To", "Cl", "App", "Taxi"]:
        print(f"    {m:5} f={LTO_F[m]:.2f} -> gross {float(G(LTO_F[m])):6.0f} hp")

    # corrected LTO states (deck run at the scheduled gross)
    od = prob.model.od_pts[0]
    print("\n=== corrected LTO combustor state (deck at scheduled gross) ===")
    print(f"{'mode':5} {'FF_corr':>8} {'FF_excel':>9} {'err%':>6} {'T3_K':>6} {'FAR':>7}  (was)")
    was = {"To": (665, .0175), "Cl": (651, .0165), "App": (556, .0105), "Taxi": (519, .0082)}
    for m in ["To", "Cl", "App", "Taxi"]:
        gr = float(G(LTO_F[m]))
        s = des if abs(gr - TO_GROSS_HP) < 1.0 else deck._od_state(prob, od, 0.0, 1e-3, gr, des["base_W"])
        if s is None:
            print(f"{m:5}  (no converge)"); continue
        err = 100 * (s["Wfuel"] - FF_EXCEL[m]) / FF_EXCEL[m]
        print(f"{m:5} {s['Wfuel']:8.4f} {FF_EXCEL[m]:9.3f} {err:+6.1f} {s['T3_K']:6.0f} {s['FAR']:7.4f}"
              f"   (T3={was[m][0]}, FAR={was[m][1]})")

    # regenerate the flight-envelope dataset with the correction
    print("\nRegenerating corrected combustor-state envelope ...")
    # Avoid Mach=0 (static): the deck's static off-design point converges to a spurious low-T3
    # state; from ~M0.1 up the combustor state is well-behaved (T3 ~ flat with Mach).
    alts = np.linspace(0, 30000, 5); machs = np.linspace(0.10, 0.55, 4)
    rows, op_id, ok, fail = [], 0, 0, 0
    for alt in alts:
        d = _delta(alt)
        for mach in machs:
            for f in np.linspace(0.30, 1.00, 5):
                gross = float(G(f)) * d
                s = deck._od_state(prob, od, alt, mach, gross, des["base_W"])
                op_id += 1
                if s is None:
                    fail += 1; continue
                ok += 1
                rows.append([op_id, mach, alt, f, 0.0, 0.0, s["T3_K"], s["P3_Pa"], s["FAR"], s["mdot"]])
    hdr = "op_id,Mach,alt_ft,PC,time_s,dist_nm,T3_K,P3_Pa,FAR,mdot_air3_kg_s"
    out = os.path.join(HERE, "pw127_crn_inputs_corrected.csv")
    np.savetxt(out, np.array(rows), delimiter=",", header=hdr, comments="")
    arr = np.array(rows)
    print(f"  {ok} converged / {fail} failed -> {out}")
    print(f"  FAR  [{arr[:,8].min():.4f}, {arr[:,8].max():.4f}]  (was [0.0077, 0.0172])")
    print(f"  T3_K [{arr[:,6].min():.0f}, {arr[:,6].max():.0f}]  (was [447, 664])")
    np.save(os.path.join(HERE, "_schedule.npy"), np.column_stack([fracs, req_gross]))


if __name__ == "__main__":
    main()
