"""Phase 3 steps 3.1 + 3.2 — PW127-tuned pyCycle deck: validate LTO fuel flow vs the FOCA/EASA
Excel, then generate the combustor-state envelope dataset that feeds the CRN.

Reuses the 2-shaft turboshaft classes in PhlyGreen's ``Single_spool_GT.py`` (the user agreed to
keep the simplified 2-shaft architecture). Re-tunes the design point to PW127 (OPR ~14.7, rated
power set so the sea-level-static take-off fuel flow matches the Excel ``FF_To`` = 0.16 kg/s).

Outputs (same schema as Pietrosanto's pyCycle->CRN CSV, so the CRN batch can consume it):
    op_id, Mach, alt_ft, PC, time_s, dist_nm, T3_K, P3_Pa, FAR, mdot_air3_kg_s
"""
import os, sys, io, contextlib
import numpy as np
import openmdao.api as om

os.environ["OPENMDAO_REPORTS"] = "0"
DECK_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
sys.path.insert(0, DECK_DIR)
import Single_spool_GT as deck   # noqa: E402

DEGR_TO_K, PSI_TO_PA, LBM_S_TO_KG_S = 1.0 / 1.8, 6894.757, 0.45359237
HERE = os.path.dirname(os.path.abspath(__file__))

# --- PW127 design targets ---
OPR_PW127 = 14.7
T4_DEGR = 2370.0                 # combustor exit (ITT-ish); kept from the reference deck
FF_TO_TARGET = 0.16              # Excel FF_To [kg/s] -> sets rated power
# FOCA/EASA turboprop LTO: To 100 / Cl 90 / App 30 / Idle(Taxi) 7 % of rated power.
LTO = {"To": 1.00, "Cl": 0.90, "App": 0.30, "Taxi": 0.07}
FF_EXCEL = {"To": 0.16, "Cl": 0.14, "App": 0.08, "Taxi": 0.04}


@contextlib.contextmanager
def _quiet():
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        yield


def _build():
    prob = om.Problem(reports=False)
    prob.model = deck.MPSingleSpool()
    with _quiet():
        prob.setup()
    return prob


def _set_design(prob, pwr_hp):
    prob.set_val('DESIGN.fc.alt', 0.0, units='ft')
    prob.set_val('DESIGN.fc.MN', 1e-6)
    prob.set_val('DESIGN.balance.T4_target', T4_DEGR, units='degR')
    prob.set_val('DESIGN.balance.pwr_target', pwr_hp, units='hp')
    prob.set_val('DESIGN.balance.nozz_PR_target', 1.2)
    prob.set_val('DESIGN.comp.PR', OPR_PW127)
    prob.set_val('DESIGN.comp.eff', 0.86)
    prob.set_val('DESIGN.turb.eff', 0.885)
    prob.set_val('DESIGN.pt.eff', 0.915)


def _design_state(prob):
    g = lambda p: prob.get_val('DESIGN.' + p)[0]
    return dict(T3_K=g('comp.Fl_O:tot:T') * DEGR_TO_K, P3_Pa=g('comp.Fl_O:tot:P') * PSI_TO_PA,
                FAR=g('balance.FAR'), mdot=g('inlet.Fl_O:stat:W') * LBM_S_TO_KG_S,
                Wfuel=g('perf.Wfuel_0') * LBM_S_TO_KG_S, OPR=g('perf.OPR'),
                base_W=g('inlet.Fl_O:stat:W'))


def tune_rated_power():
    """Bisect design (SLS-static, full-power = take-off) power so Wfuel == FF_To target."""
    prob = _build()
    def ff(pwr):
        _set_design(prob, pwr)
        with _quiet():
            prob.run_model()
        return _design_state(prob)["Wfuel"]
    lo, hi = 2500.0, 4200.0
    for _ in range(20):
        mid = 0.5 * (lo + hi)
        if ff(mid) < FF_TO_TARGET:
            lo = mid
        else:
            hi = mid
    rated = 0.5 * (lo + hi)
    _set_design(prob, rated)
    with _quiet():
        prob.run_model()
    return prob, rated, _design_state(prob)


def _od_state(prob, od, alt_ft, mach, pwr_hp, base_W):
    """Run one off-design point; return combustor state dict or None if not converged."""
    P_std_sl, T_std_sl = 14.696, 518.67
    T_amb = max(T_std_sl - 3.566e-3 * alt_ft, 390.0)
    delta = (P_amb := P_std_sl * (T_amb / T_std_sl) ** 5.2561) / P_std_sl
    prob.set_val(f'{od}.balance.W', base_W * delta)
    prob.set_val(f'{od}.balance.FAR', 0.017)
    prob.set_val(f'{od}.balance.HP_Nmech', 5000.0)
    prob.set_val(f'{od}.fc.alt', alt_ft, units='ft')
    prob.set_val(f'{od}.fc.MN', mach)
    prob.set_val(f'{od}.balance.pwr_target', pwr_hp, units='hp')
    try:
        with _quiet():
            prob.run_model()
        g = lambda p: prob.get_val(f'{od}.' + p)[0]
        T3 = g('comp.Fl_O:tot:T') * DEGR_TO_K
        P3 = g('comp.Fl_O:tot:P') * PSI_TO_PA
        FAR = g('balance.FAR')
        mdot = g('inlet.Fl_O:stat:W') * LBM_S_TO_KG_S
        Wf = g('perf.Wfuel_0') * LBM_S_TO_KG_S
        if not np.isfinite([T3, P3, FAR, mdot]).all() or FAR <= 0 or T3 <= 0:
            return None
        return dict(T3_K=T3, P3_Pa=P3, FAR=FAR, mdot=mdot, Wfuel=Wf)
    except Exception:
        return None


def validate_lto(prob, rated, des):
    od = prob.model.od_pts[0]
    print("\n=== LTO validation: pyCycle fuel flow vs FOCA/EASA Excel (PW127G) ===")
    print(f"{'mode':5} {'%pwr':>5} {'FF_pyc':>8} {'FF_excel':>9} {'err%':>6} "
          f"{'T3_K':>7} {'P3_MPa':>7} {'FAR':>7}")
    for mode, frac in LTO.items():
        if mode == "To":
            s = des
        else:
            s = _od_state(prob, od, 0.0, 1e-3, frac * rated, des["base_W"])
        if s is None:
            print(f"{mode:5} {frac*100:5.0f}   (did not converge)")
            continue
        err = 100 * (s["Wfuel"] - FF_EXCEL[mode]) / FF_EXCEL[mode]
        print(f"{mode:5} {frac*100:5.0f} {s['Wfuel']:8.4f} {FF_EXCEL[mode]:9.3f} {err:6.1f} "
              f"{s['T3_K']:7.1f} {s['P3_Pa']/1e6:7.3f} {s['FAR']:7.4f}")


def generate_envelope(prob, rated, des, n_alt=5, n_mach=4, n_pwr=5):
    """Off-design grid over (alt, Mach, power 30-100%) -> CRN-input CSV (Pietrosanto schema)."""
    od = prob.model.od_pts[0]
    alts = np.linspace(0, 30000, n_alt)
    machs = np.linspace(0.0, 0.55, n_mach)
    rows, op_id, ok, fail = [], 0, 0, 0
    for alt in alts:
        P_std_sl, T_std_sl = 14.696, 518.67
        T_amb = max(T_std_sl - 3.566e-3 * alt, 390.0)
        delta = (P_std_sl * (T_amb / T_std_sl) ** 5.2561) / P_std_sl
        for mach in machs:
            for frac in np.linspace(0.30, 1.00, n_pwr):
                s = _od_state(prob, od, alt, mach, frac * rated * delta, des["base_W"])
                op_id += 1
                if s is None:
                    fail += 1
                    continue
                ok += 1
                rows.append([op_id, mach, alt, frac, 0.0, 0.0,
                             s["T3_K"], s["P3_Pa"], s["FAR"], s["mdot"]])
    hdr = "op_id,Mach,alt_ft,PC,time_s,dist_nm,T3_K,P3_Pa,FAR,mdot_air3_kg_s"
    out = os.path.join(HERE, "pw127_crn_inputs.csv")
    np.savetxt(out, np.array(rows), delimiter=",", header=hdr, comments="")
    print(f"\nenvelope dataset: {ok} converged / {fail} failed -> {out}")
    arr = np.array(rows)
    print(f"  T3_K   [{arr[:,6].min():.0f}, {arr[:,6].max():.0f}] K")
    print(f"  P3     [{arr[:,7].min()/1e6:.2f}, {arr[:,7].max()/1e6:.2f}] MPa")
    print(f"  FAR    [{arr[:,8].min():.4f}, {arr[:,8].max():.4f}]")
    print(f"  mdot   [{arr[:,9].min():.1f}, {arr[:,9].max():.1f}] kg/s")
    return out


def main():
    print("Tuning PW127 rated power (OPR=%.1f) to take-off FF=%.2f kg/s ..." % (OPR_PW127, FF_TO_TARGET))
    prob, rated, des = tune_rated_power()
    print(f"  rated power = {rated:.0f} hp  ({rated*0.7457:.0f} kW) | "
          f"take-off: Wfuel={des['Wfuel']:.4f} kg/s, T3={des['T3_K']:.1f} K, "
          f"P3={des['P3_Pa']/1e6:.3f} MPa, FAR={des['FAR']:.4f}, mdot={des['mdot']:.2f} kg/s")
    validate_lto(prob, rated, des)
    generate_envelope(prob, rated, des)


if __name__ == "__main__":
    main()
