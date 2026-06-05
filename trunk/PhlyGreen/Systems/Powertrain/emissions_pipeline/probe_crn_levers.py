"""Phase 3 — probe the CRN calibration levers at the PW127 (corrected) states, to see how NOx/CO
respond before building the optimiser. Levers: chi_mixer_scale (evaporation), ARPZ (primary-zone
air fraction -> PZ richness/T), V1_total (PZ residence time).
"""
import os, sys, io, contextlib
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pw127_deck as deck            # noqa
import pw127_partpower as pp         # noqa
import crn_smoke_test as crn         # noqa
evap = crn.evap

# remember CRN defaults
ARPZ0, ARSZ0, ARDZ0 = evap.ARPZ, evap.ARSZ, evap.ARDZ
V1_0 = evap.V1_total


def set_split(arpz):
    """Set primary-zone air fraction, renormalising SZ/DZ to keep the sum."""
    rest = ARSZ0 + ARDZ0
    scale = (1.0 - arpz) / rest
    evap.ARPZ, evap.ARSZ, evap.ARDZ = arpz, ARSZ0 * scale, ARDZ0 * scale


def set_V1(mult):
    evap.V1_total = V1_0 * mult
    evap.V1_i = evap.V1_total / evap.N_PZ


def reset():
    evap.ARPZ, evap.ARSZ, evap.ARDZ = ARPZ0, ARSZ0, ARDZ0
    set_V1(1.0)


def crn_eval(state, chi=None, arpz=None, V1_mult=1.0):
    reset()
    if arpz is not None:
        set_split(arpz)
    set_V1(V1_mult)
    chi_used = chi if chi is not None else crn.chi_from_T(state["T3_K"])
    params = {"label": "probe", "power": 0., "T_in": state["T3_K"], "p_in_bar": state["P3_Pa"]/1e5,
              "mdot_air": state["mdot"], "FAR": state["FAR"], "dPqP": 0.95,
              "chi_mixer_scale": chi_used, "EIUHC_ICAO": 0.0}
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        r = evap.run_crn_evap_mode("GRID", params)
    reset()
    return r.get("EI_NOx"), r.get("EI_CO")


def main():
    prob = deck._build(); deck._set_design(prob, pp.TO_GROSS_HP)
    with deck._quiet(): prob.run_model()
    des = deck._design_state(prob)
    G, _, _ = pp.calibrate_schedule(pp.build_ff_curve(prob, des))
    od = prob.model.od_pts[0]
    To = des
    App = deck._od_state(prob, od, 0.0, 1e-3, float(G(0.30)), des["base_W"])
    states = {"To (target NOx 19, CO 2)": To, "App (target NOx 10, CO 4)": App}

    for name, s in states.items():
        print(f"\n### {name}: T3={s['T3_K']:.0f} K, FAR={s['FAR']:.4f}")
        base = crn_eval(s)
        print(f"  baseline                     NOx={base[0]:6.2f}  CO={base[1]:6.2f}")
        for chi in [3.0, 5.0]:
            n, c = crn_eval(s, chi=chi)
            print(f"  chi={chi:<4}                     NOx={n:6.2f}  CO={c:6.2f}")
        for arpz in [0.40, 0.22]:
            n, c = crn_eval(s, arpz=arpz)
            print(f"  ARPZ={arpz:<4} (base {ARPZ0:.2f})       NOx={n:6.2f}  CO={c:6.2f}")
        for vm in [0.5, 2.0]:
            n, c = crn_eval(s, V1_mult=vm)
            print(f"  V1x{vm:<4} (residence)          NOx={n:6.2f}  CO={c:6.2f}")
    print("\n(levers: chi up/ARPZ up/V1 down -> leaner-cooler-shorter -> less NOx; ARPZ down -> "
          "richer PZ -> more low-power NOx.)")


if __name__ == "__main__":
    main()
