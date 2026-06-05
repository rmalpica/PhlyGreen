"""Phase 3 — recalibrate the CRN to PW127 by scanning the primary-zone air fraction ARPZ
(the dominant NOx lever) across the 4 LTO modes. A single PW127 ARPZ that best matches the ICAO
NOx (richer PZ than the CFM56 baseline 0.31) is the physical recalibration; CO is checked too.
"""
import os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import pw127_deck as deck            # noqa
import pw127_partpower as pp         # noqa
import probe_crn_levers as pr        # noqa  (crn_eval, set_split, reset)

ICAO = {"To": (1.00, 19, 2), "Cl": (0.90, 16, 2), "App": (0.30, 10, 4), "Taxi": (0.07, 5, 20)}


def lto_states():
    prob = deck._build(); deck._set_design(prob, pp.TO_GROSS_HP)
    with deck._quiet(): prob.run_model()
    des = deck._design_state(prob)
    G, _, _ = pp.calibrate_schedule(pp.build_ff_curve(prob, des))
    od = prob.model.od_pts[0]
    out = {}
    for m, (f, _, _) in ICAO.items():
        out[m] = des if f >= 0.999 else deck._od_state(prob, od, 0.0, 1e-3, float(G(f)), des["base_W"])
    return out


def main():
    states = lto_states()
    arpz_grid = [0.24, 0.26, 0.28, 0.30]
    print("CRN NOx (and CO) vs ARPZ at the PW127 LTO states  [target NOx | CO]\n")
    header = "ARPZ  " + "  ".join(f"{m}({ICAO[m][1]}|{ICAO[m][2]})" for m in ICAO)
    print(header)
    results = {}
    for arpz in arpz_grid:
        cells, nox_err = [], []
        for m in ICAO:
            n, c = pr.crn_eval(states[m], arpz=arpz)
            cells.append(f"{n:5.1f}|{c:4.1f}")
            nox_err.append((n - ICAO[m][1]) / ICAO[m][1])
        results[arpz] = np.sqrt(np.mean(np.square(nox_err)))
        print(f"{arpz:.2f}  " + "  ".join(cells) + f"   rmsNOx%={100*results[arpz]:.0f}")
    best = min(results, key=results.get)
    print(f"\nbaseline (CFM56) ARPZ = {pr.ARPZ0:.3f}; best PW127 ARPZ = {best:.2f} "
          f"(rms NOx error {100*results[best]:.0f}%)")
    print("\nFinal CRN at PW127 best ARPZ vs ICAO:")
    print(f"{'mode':5} {'NOx':>6} {'NOx_icao':>9} {'CO':>6} {'CO_icao':>8}")
    for m, (f, ni, ci) in ICAO.items():
        n, c = pr.crn_eval(states[m], arpz=best)
        print(f"{m:5} {n:6.1f} {ni:9} {c:6.1f} {ci:8}")
    np.save(os.path.join(HERE, "_pw127_arpz.npy"), np.array([best]))


if __name__ == "__main__":
    main()
