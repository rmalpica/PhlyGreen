"""Re-run the turboshaft pyCycle deck of GT_Universal_Map.csv and check it against the CSV.

The shipped map ``trunk/PhlyGreen/Systems/Powertrain/data/GT_Universal_Map.csv`` is written by
``data/Single_spool_GT.py``. Its generator accepts a point only when three off-design balances
are closed within 0.1 % (delivered shaft power, gas-generator shaft, nozzle throat area), and it
stores the target and delivered shaft power of every point. This script

1. reads those two columns and reports the largest power error of the shipped CSV;
2. re-runs the generator's own sweep (``Single_spool_GT.generate_map``, same design point, same
   grid and warm-start order), records the three closure errors of every accepted point, and
   compares the re-run efficiencies with the CSV;
3. solves one point at Mach 0 exactly (sea level, full power, fresh guesses), to document why
   the static column is solved at Mach 0.01.

Nothing in the package is modified: the results go to ../data/gt_deck_check.json.

Needs pyCycle (om-pycycle) and OpenMDAO. Runtime: about ten minutes.

    python manuals/engine-decks/scripts/check_gt_deck.py
"""

import contextlib
import io
import json
import os
import sys
import time

os.environ["OPENMDAO_REPORTS"] = "0"

HERE = os.path.dirname(os.path.abspath(__file__))
TRUNK = os.path.abspath(os.path.join(HERE, "..", "..", "..", "trunk"))
DECK_DIR = os.path.join(TRUNK, "PhlyGreen", "Systems", "Powertrain", "data")
OUT = os.path.abspath(os.path.join(HERE, "..", "data", "gt_deck_check.json"))
sys.path.insert(0, DECK_DIR)

import numpy as np                    # noqa: E402
import pandas as pd                   # noqa: E402
import openmdao.api as om             # noqa: E402
import Single_spool_GT as deck        # noqa: E402

LBM_TO_KG = 0.45359237
HP_TO_W = 745.7


def main():
    t_start = time.time()
    csv = pd.read_csv(os.path.join(DECK_DIR, "GT_Universal_Map.csv"))
    csv_power_error = ((csv.Delivered_hp - csv.Target_hp).abs() / csv.Target_hp)

    prob = om.Problem(reports=False)
    prob.model = deck.MPSingleSpool()
    with contextlib.redirect_stdout(io.StringIO()):
        prob.setup()

    # Design point of Single_spool_GT.py (sea-level static, 2750 hp, T4 2370 degR, PR 13.5).
    prob.set_val('DESIGN.fc.alt', 0.0, units='ft')
    prob.set_val('DESIGN.fc.MN', 1e-6)
    prob.set_val('DESIGN.balance.T4_target', 2370.0, units='degR')
    prob.set_val('DESIGN.balance.pwr_target', deck.REF_PWR, units='hp')
    prob.set_val('DESIGN.balance.nozz_PR_target', 1.2)
    prob.set_val('DESIGN.comp.PR', 13.5)
    prob.set_val('DESIGN.comp.eff', deck.REF_EFF_COMP)
    prob.set_val('DESIGN.turb.eff', deck.REF_EFF_HPT)
    prob.set_val('DESIGN.pt.eff', deck.REF_EFF_LPT)
    deck.run_quietly(prob)
    base_w = prob.get_val('DESIGN.inlet.Fl_O:stat:W')[0]
    design_wfuel = prob.get_val('DESIGN.perf.Wfuel')[0] * LBM_TO_KG
    design_opr = prob.get_val('DESIGN.perf.OPR')[0]
    design_far = prob.get_val('DESIGN.balance.FAR')[0]

    # Re-run the generator's sweep, recording the state of every accepted point.
    accepted = []
    original_solve_point = deck.solve_point

    def recording_solve_point(prob_, od, alt, mach, target_hp, guesses, continuation_start):
        state = original_solve_point(prob_, od, alt, mach, target_hp, guesses,
                                     continuation_start)
        accepted.append({"alt_ft": float(alt), "Mach": float(mach), "target_hp": float(target_hp),
                         "delivered_hp": float(state["delivered_hp"]),
                         "FAR": float(state["FAR"]),
                         "power_error": float(state["power_error"]),
                         "hp_shaft_error": float(state["hp_shaft_error"]),
                         "area_error": float(state["area_error"])})
        return state

    deck.solve_point = recording_solve_point
    with contextlib.redirect_stdout(io.StringIO()):
        rows = deck.generate_map(prob, base_w)
    deck.solve_point = original_solve_point
    rerun = pd.DataFrame(rows, columns=["Altitude_ft", "Mach", "Power", "Efficiency",
                                        "Target_hp", "Delivered_hp"])
    eta_diff = np.abs(rerun.Efficiency.values - csv.Efficiency.values)

    # One point at Mach 0 exactly: sea level, full power, fresh guesses.
    od = prob.model.od_pts[0]
    mach0 = deck.solve_from_guess(prob, od, 0.0, 0.0, deck.REF_PWR,
                                  {"W": base_w, "FAR": 0.017, "HP_Nmech": 8070.0})
    mach0 = {k: (float(v) if not isinstance(v, bool) else v) for k, v in mach0.items()}

    out = {"design": {"inlet_flow_lbm_s": float(base_w), "fuel_flow_kg_s": float(design_wfuel),
                      "OPR": float(design_opr), "FAR": float(design_far),
                      "eta": float(deck.REF_PWR * HP_TO_W / (design_wfuel * deck.LHV_J_KG))},
           "csv": {"n_points": int(len(csv)), "machs": sorted(csv.Mach.unique().tolist()),
                   "max_power_error": float(csv_power_error.max())},
           "rerun": {"n_points": int(len(rerun)), "n_solves_recorded": len(accepted),
                     "max_eta_abs_diff_vs_csv": float(eta_diff.max()),
                     "max_power_error": float(max(a["power_error"] for a in accepted)),
                     "max_hp_shaft_error": float(max(a["hp_shaft_error"] for a in accepted)),
                     "max_area_error": float(max(a["area_error"] for a in accepted)),
                     "FAR_range": [float(min(a["FAR"] for a in accepted)),
                                   float(max(a["FAR"] for a in accepted))],
                     "points": accepted},
           "mach0_exact": mach0,
           "runtime_s": time.time() - t_start}
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print(f"{len(rerun)} points re-run; max |eta - csv| {eta_diff.max():.2e}; max power error "
          f"{out['rerun']['max_power_error']:.1e}; Mach 0: {mach0}; "
          f"{out['runtime_s']:.0f} s -> {OUT}")


if __name__ == "__main__":
    main()
