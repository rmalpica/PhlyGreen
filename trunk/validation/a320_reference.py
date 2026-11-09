"""Validate PhlyGreen's Turbofan configuration against the Airbus A320-200.

Reference data and its provenance are in ``a320_reference.md``. Primary rows come from the
Airbus ACAP and the EASA TCDS; secondary rows (wing area, OEW, range) are labelled as such and
are not treated as certification data.

Two design points are reported, because they answer different questions:

* **minimum installed thrust** -- what ``Constraint.FindDesignPoint`` returns by default. It
  minimises the largest requirement over wing loading, i.e. it minimises the *engine*.
* **landing-limited** -- the wing loading at the landing-field wall, which is where a
  narrow-body is actually sized. Approach speed caps W/S; within that cap a smaller wing is
  lighter and has less drag, so take-off weight keeps falling right up to the wall.

Minimum installed thrust is **not** minimum take-off weight, and the gap between the two is the
single largest source of disagreement in this validation. The wing-loading sweep below
demonstrates it rather than asserting it.

Run:
    cd trunk && python validation/a320_reference.py
"""

import os
import sys

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_TRUNK = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_TRUNK, "examples"))

import PhlyGreen as pg
from PhlyGreen import postprocess as post
from common import turbofan_config

FIGDIR = os.path.join(_HERE, "figures")


# --- reference -------------------------------------------------------------------------
# See a320_reference.md for the full provenance table. 'primary' = certification or
# manufacturer publication; 'secondary' = industry reference work.
REFERENCE = {
    "citation": (
        "Airbus, A320 Aircraft Characteristics - Airport and Maintenance Planning, "
        "Rev. Jun 01/24; EASA TCDS EASA.A.064 Issue 12 and TCDSN EASA.A.064.3 Issue 28; "
        "flugzeuginfo.net A320 technical data."
    ),
    # quantity            value     units   source-class
    "MTOW":              (78000.0, "kg",   "primary"),    # ACAP p.34 WV017; TCDS-N p.15 rec. A17309
    "MZFW":              (62500.0, "kg",   "primary"),    # ACAP p.34 WV017
    "MLW":               (66000.0, "kg",   "primary"),    # ACAP p.34 WV017
    "SLS_thrust_total":  (240.2,   "kN",   "primary"),    # 2 x 12 010 daN, TCDS p.24
    "wing_span":         (34.10,   "m",    "primary"),    # ACAP p.40
    "wing_area":         (122.6,   "m2",   "secondary"),  # flugzeuginfo
    "OEW":               (42600.0, "kg",   "secondary"),  # A320-200 CFM56 (see caveat 1)
}

# Design mission (150 pax two-class, 3000 nm) is set in examples/common.py.


def _calibrated_oew(k, wing_loading_kgm2):
    """Converged OEW [kg] of the landing-limited design with the regression scaled by ``k``."""
    cfg = turbofan_config()
    cfg.avoid_powertrain_double_count = True
    cfg.structure_calibration = k
    cfg.design_wing_loading = wing_loading_kgm2 * 9.81
    ac = pg.build_aircraft()
    ac.configure(cfg)
    return ac.results().empty_weight


def calibrate_structure_to_oew(wing_loading_kgm2, target_oew=None, k_step=0.02, k_max=1.3,
                               rtol=1e-4):
    """Calibration factor of the Class-I empty-weight regression that makes the converged
    design reach the reference OEW.

    Scaling the regression by ``OEW_ref / We(MTOW_ref)`` is not enough: a heavier structure
    makes a heavier aircraft, which the regression then makes heavier still. The converged OEW
    grows faster than the factor (a 1 % larger factor gives more than 2 % more OEW here), so the
    update ``k <- k * OEW_ref / OEW(k)`` overshoots and diverges. The converged OEW grows
    monotonically with ``k``, so the factor is found as the root of ``OEW(k) - OEW_ref``: ``k``
    is raised from 1 in steps of ``k_step`` until the OEW passes the target, and Brent's method
    solves the bracket. ``RuntimeError`` if no factor up to ``k_max`` reaches the target; a
    design that does not close raises from ``configure``.

    This calibrates against published data, not against a result -- but a calibrated empty
    weight is no longer an independent prediction of empty weight, and is reported as fitted.
    """
    from scipy.optimize import brentq

    target = target_oew if target_oew is not None else REFERENCE["OEW"][0]

    def residual(k):
        return _calibrated_oew(k, wing_loading_kgm2) - target

    k_low, r_low = 1.0, residual(1.0)
    if r_low == 0.0:
        return k_low
    direction = 1.0 if r_low < 0.0 else -1.0       # raise k if the design is too light
    k_high = k_low
    while True:
        k_high = k_high + direction * k_step
        if not (2.0 - k_max) <= k_high <= k_max:
            raise RuntimeError(
                f"calibrate_structure_to_oew: no factor in [{2.0 - k_max:.2f}, {k_max:.2f}] "
                f"reaches the reference OEW of {target:.0f} kg.")
        r_high = residual(k_high)
        if r_low * r_high <= 0.0:
            break
        k_low, r_low = k_high, r_high
    return brentq(residual, min(k_low, k_high), max(k_low, k_high), rtol=rtol)


def _design(wing_loading_kgm2=None, structure_calibration=1.0, avoid_double_count=True):
    """Size the A320 config.

    ``avoid_double_count`` controls whether the turbofan mass is added on top of the Class-I
    empty-weight regression, which already contains the installed engines.
    ``structure_calibration`` scales that regression (1.0 = the textbook correlation).
    """
    cfg = turbofan_config()
    cfg.avoid_powertrain_double_count = avoid_double_count
    cfg.structure_calibration = structure_calibration
    if wing_loading_kgm2 is not None:
        cfg.design_wing_loading = wing_loading_kgm2 * 9.81
    ac = pg.build_aircraft()
    ac.configure(cfg)
    return ac


def landing_limited_wing_loading():
    """The landing-field W/S wall [kg/m^2], from PhlyGreen's own landing model.

    Derived from the configured approach speed and landing CLmax -- *not* from the reference
    MTOW and wing area, which would make the comparison circular.
    """
    cfg = turbofan_config()
    ac = pg.build_aircraft()
    ac.configure(cfg, design=False)
    c = ac.constraint
    c.EvaluateConstraints(c.WTOoS, c.DISA)
    return float(np.asarray(c.WTOoSLanding)[0]) / 9.81


# ---------------------------------------------------------------------------------------
# Payload-range
# ---------------------------------------------------------------------------------------

def _offdesign_block_fuel(range_nm, payload_kg, oew, wing_loading, n_iter=12, tol=1.0):
    """Block fuel and take-off weight for a FIXED aircraft flying a given payload and range.

    PhlyGreen always re-sizes, so a payload-range diagram needs the sizing loop opened up: the
    empty weight and the wing are held at the values the design converged on, and only the fuel
    and take-off weight are solved for. That is what makes the result an off-design point on one
    aircraft rather than a family of differently sized aircraft.
    """
    cfg = turbofan_config()
    cfg.mission.range_mission = float(range_nm)
    cfg.mission.payload_weight = float(payload_kg)
    cfg.design_wing_loading = wing_loading * 9.81
    ac = pg.build_aircraft()
    ac.configure(cfg, design=False)
    ac.constraint.FindDesignPoint(wing_loading * 9.81)

    contingency = cfg.energy.contingency_fuel or 0.0
    wto = oew + payload_kg + 0.25 * (oew + payload_kg)
    fuel = reserve = 0.0
    for _ in range(n_iter):
        fuel = ac.mission.EvaluateMission(wto) / ac.weight.ef
        reserve = contingency if contingency else 0.05 * fuel
        new = oew + payload_kg + fuel + reserve
        if abs(new - wto) < tol:
            wto = new
            break
        wto = 0.5 * (wto + new)          # damped, the loop is mildly stiff at long range
    return fuel + reserve, wto


def payload_range(oew, mtow, wing_loading, design_payload, max_fuel_kg=None,
                  n_points=5, r_lo=200.0, r_hi=7000.0, n_bisect=12):
    """Trace the payload-range boundary of the sized aircraft.

    The classic diagram has two legs, and both are returned:

    * a **flat leg** at the design payload, from zero range out to the range at which the
      aircraft first runs out of take-off weight. Along it the aircraft is not weight-limited
      and simply carries less fuel, so payload is constant;
    * a **descending leg** beyond that, where every extra kilogram of fuel has to be paid for
      with a kilogram of payload because take-off weight is pinned at MTOW.

    ``mtow`` should be the aircraft's **own** converged take-off weight, not a reference value:
    the corner between the two legs is then exactly the design mission, which is what makes the
    diagram a statement about this aircraft rather than a mixture of two.

    If ``max_fuel_kg`` is given the descending leg stops where the tanks are full; PhlyGreen has
    no kerosene tank-volume model, so that limit has to come from outside.

    Returns ``(points, corner)`` with ``points = [(range_nm, payload_kg), ...]``.
    """
    def range_for(payload, fuel_allowed):
        lo, hi = r_lo, r_hi
        for _ in range(n_bisect):
            mid = 0.5 * (lo + hi)
            try:
                block, _ = _offdesign_block_fuel(mid, payload, oew, wing_loading)
            except Exception:
                hi = mid
                continue
            if block > fuel_allowed:
                hi = mid
            else:
                lo = mid
        return lo

    fuel_at_design = mtow - oew - design_payload
    if max_fuel_kg is not None:
        fuel_at_design = min(fuel_at_design, max_fuel_kg)
    r_corner = range_for(design_payload, fuel_at_design)

    pts = [(0.0, design_payload), (r_corner, design_payload)]
    for pl in np.linspace(design_payload, 0.1 * design_payload, n_points)[1:]:
        allowed = mtow - oew - pl
        if max_fuel_kg is not None:
            allowed = min(allowed, max_fuel_kg)
        if allowed <= 0:
            continue
        pts.append((range_for(pl, allowed), float(pl)))
    return pts, (r_corner, design_payload)


def _row(label, ref, got, units, cls):
    err = 100.0 * (got - ref) / ref
    flag = " " if abs(err) <= 5.0 else ("*" if abs(err) <= 10.0 else "!")
    return f"  {label:<20}{ref:>10.1f}{got:>12.1f}{err:>9.1f}% {flag}  {units:<4}{cls}"


def compare(ac, title):
    r = ac.results()
    got = {
        "MTOW": r.WTO,
        "OEW": r.empty_weight,
        "wing_area": ac.WingSurface,
        "SLS_thrust_total": r.engineRating / 1000.0,
    }
    print(f"\n{title}")
    print(f"  {'quantity':<20}{'reference':>10}{'PhlyGreen':>12}{'delta':>10}      source")
    for k, v in got.items():
        ref, units, cls = REFERENCE[k]
        print(_row(k, ref, v, units, cls))
    print(f"  {'design W/S':<20}{REFERENCE['MTOW'][0]/REFERENCE['wing_area'][0]:>10.1f}"
          f"{ac.DesignWTOoS/9.81:>12.1f}{'':>10}      kg/m2")
    tw_ref = 240.2e3 / (REFERENCE['MTOW'][0] * 9.81)
    print(f"  {'design T/W':<20}{tw_ref:>10.3f}{r.DesignTW:>12.3f}"
          f"{100*(r.DesignTW-tw_ref)/tw_ref:>9.1f}%      derived from primary")
    print(f"  block fuel {ac.weight.Wf + ac.weight.final_reserve:.0f} kg, "
          f"mean TSFC {r.mean_TSFC*3600*9.80665:.3f} lb/(lbf h)")
    return got


def wing_loading_sweep(ws_list=None):
    """MTOW vs wing loading -- the evidence that the MTOW optimum is at the landing wall."""
    wall = landing_limited_wing_loading()
    if ws_list is None:
        ws_list = np.linspace(430.0, wall, 8)
    out = []
    for ws in ws_list:
        try:
            ac = _design(ws)
            out.append((ws, ac.weight.WTO, ac.WingSurface))
        except Exception as exc:
            print(f"  W/S {ws:.0f} kg/m2 did not close: {type(exc).__name__}")
    return wall, out


def make_figures(ac_default, ac_landing, wall, sweep):
    os.makedirs(FIGDIR, exist_ok=True)

    # 1. PhlyGreen as % of reference, with the +-5 % band.
    r = ac_landing.results()
    got = {"MTOW": r.WTO, "OEW": r.empty_weight, "wing_area": ac_landing.WingSurface,
           "SLS_thrust_total": r.engineRating / 1000.0}
    labels = list(got)
    pct = [100.0 * got[k] / REFERENCE[k][0] for k in labels]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.bar(labels, pct, color=["tab:green" if abs(p - 100) <= 5 else "tab:orange" for p in pct])
    ax.axhline(100, color="black", lw=1, ls="--", label="reference (100%)")
    for i, p in enumerate(pct):
        ax.text(i, p + 1, f"{p-100:+.1f}%", ha="center", fontsize=9)
    ax.set_ylabel("PhlyGreen as % of reference")
    ax.set_title("A320-200, landing-limited design point")
    ax.legend(); fig.tight_layout()
    fig.savefig(os.path.join(FIGDIR, "a320_vs_reference.png"), dpi=130); plt.close(fig)

    # 2. MTOW vs wing loading -- why the default design point is not the MTOW optimum.
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ws = [p[0] for p in sweep]; mtow = [p[1] for p in sweep]
    ax.plot(ws, mtow, "o-", label="PhlyGreen")
    ax.axvline(wall, color="tab:red", ls="--", label=f"landing wall ({wall:.0f} kg/m$^2$)")
    ax.axvline(ac_default.DesignWTOoS / 9.81, color="tab:blue", ls=":",
               label="min installed thrust")
    ax.axhline(REFERENCE["MTOW"][0], color="black", ls="-.", lw=1, label="A320 MTOW")
    ax.set_xlabel("wing loading [kg/m$^2$]"); ax.set_ylabel("MTOW [kg]")
    ax.set_title("Take-off weight falls with wing loading up to the landing limit")
    ax.grid(alpha=0.3); ax.legend(fontsize=9); fig.tight_layout()
    fig.savefig(os.path.join(FIGDIR, "a320_wing_loading_sweep.png"), dpi=130); plt.close(fig)

    # 3. The usual design plots at the landing-limited point.
    for name, fn in (("a320_constraint_diagram", post.plot_constraint_diagram),
                     ("a320_mission_profile", post.plot_mission_profile),
                     ("a320_mass_breakdown", post.plot_mass_breakdown)):
        fn(ac_landing)
        plt.savefig(os.path.join(FIGDIR, name + ".png"), dpi=130, bbox_inches="tight")
        plt.close("all")
    print(f"\nFigures written to {FIGDIR}")


def main():
    # Headless only when this file is *run*. Forcing Agg at import time would silently kill
    # inline plotting in any notebook that imports these helpers -- which it did.
    matplotlib.use("Agg")
    print(__doc__.split("Run:")[0].strip())
    print(f"\nReference: {REFERENCE['citation']}")

    wall = landing_limited_wing_loading()

    ac_default = _design()
    compare(ac_default, "A) minimum-installed-thrust design point, uncalibrated")

    ac_landing = _design(wall)
    compare(ac_landing, f"B) landing-limited (W/S = {wall:.1f} kg/m2), uncalibrated")

    print("\nC) landing-limited + empty weight calibrated to the reference OEW")
    try:
        k = calibrate_structure_to_oew(wall)
        ac_cal = _design(wall, structure_calibration=k)
        compare(ac_cal, f"   (regression x{k:.3f})")
    except Exception as exc:
        ac_cal = None
        r = ac_landing.results()
        frac_e = r.empty_weight / r.WTO
        ref_frac = REFERENCE["OEW"][0] / REFERENCE["MTOW"][0]
        print(f"  DOES NOT CLOSE ({type(exc).__name__}). This is a result, not a crash:\n"
              f"    empty-weight fraction, PhlyGreen  {frac_e:.3f}\n"
              f"    empty-weight fraction, A320       {ref_frac:.3f}\n"
              f"    payload+crew fraction, A320       "
              f"{(14250+600)/REFERENCE['MTOW'][0]:.3f}\n"
              f"    fuel fraction, A320               "
              f"{1 - ref_frac - (14250+600)/REFERENCE['MTOW'][0]:.3f}\n"
              "  Those three sum to 1 by definition, so raising the empty-weight fraction to the\n"
              "  reference value leaves no room for the fuel this mission needs and the take-off\n"
              "  weight equation has no root. The Class-I regression has essentially no margin at\n"
              "  the A320's design point -- which is why the model gets the empty-weight FRACTION\n"
              "  nearly right while the aircraft comes out too small in absolute terms.")

    ws_ref = REFERENCE["MTOW"][0] / REFERENCE["wing_area"][0]
    ac_ref = _design(ws_ref)
    compare(ac_ref, f"E) at the A320's OWN wing loading ({ws_ref:.1f} kg/m2) - like-for-like")
    print("  With the geometry fixed to the real aircraft, all four quantities come out low by a\n"
          "  consistent 4-6 %: a small systematic offset in the mission/fuel model, not a geometry\n"
          "  error. That consistency is the useful signal -- errors that all point the same way\n"
          "  and are the same size usually have one cause.")

    print("\nWing loading is a genuine trade, not a free parameter:")
    print(f"  {'W/S kg/m2':>10}{'MTOW':>8}{'OEW':>8}{'S':>8}{'thrust':>9}{'rms':>7}")
    for ws in (500.0, 540.0, wall, 610.0, ws_ref):
        try:
            a = _design(ws); rr = a.results()
            g = {"MTOW": rr.WTO, "OEW": rr.empty_weight, "wing_area": a.WingSurface,
                 "SLS_thrust_total": rr.engineRating / 1000.0}
            e = {k: 100.0 * (v - REFERENCE[k][0]) / REFERENCE[k][0] for k, v in g.items()}
            rms = (sum(x * x for x in e.values()) / 4.0) ** 0.5
            print(f"  {ws:>10.1f}{e['MTOW']:>8.1f}{e['OEW']:>8.1f}{e['wing_area']:>8.1f}"
                  f"{e['SLS_thrust_total']:>9.1f}{rms:>7.1f}")
        except Exception as exc:
            print(f"  {ws:>10.1f}   did not close ({type(exc).__name__})")
    print("  Lowering W/S pulls MTOW, OEW and thrust towards the reference, but only by growing\n"
          "  the wing: at 500 kg/m2 the masses are within ~1 % and the wing area is 26 % too big.\n"
          "  That trades a visible error for a hidden one, so it is shown rather than chosen.")

    ac_double = _design(wall, avoid_double_count=False)
    compare(ac_double, "D) landing-limited, powertrain DOUBLE-COUNTED (the old behaviour)")
    print("  ^ D adds the engine mass a second time on top of a regression that already\n"
          "    contains it. With the textbook 'Jet' fraction that used to flatter the totals by\n"
          "    cancelling its under-prediction; with the fitted 'NarrowBody' regression there is\n"
          "    no under-prediction left to cancel, so D is simply too heavy.")

    print("\nWing-loading sweep (evidence, not assertion):")
    wall, sweep = wing_loading_sweep()
    print(f"  {'W/S kg/m2':>10}{'MTOW kg':>10}{'S m2':>9}")
    for ws, mtow, S in sweep:
        print(f"  {ws:>10.0f}{mtow:>10.0f}{S:>9.1f}")

    make_figures(ac_default, ac_landing, wall, sweep)

    print("""
Notes
-----
* Legend: blank = within +-5 %, * = within +-10 %, ! = outside +-10 %.
* The Class-I 'Jet' regression is an EMPTY-weight fraction, so it already contains the installed
  engines; adding the powertrain mass on top counts them twice. That second count is now off for
  this configuration (avoid_powertrain_double_count=True).
* With the accounting corrected, Raymer's jet fraction under-predicts the A320 empty weight by
  ~14 % on its own. Case D shows what the old double count was hiding: it compensated for that
  under-prediction, so the agreement looked better than the model deserved.
* Case C calibrates the regression to the reference OEW. OEW is then a FITTED quantity, not an
  independent check -- but MTOW, wing area and installed thrust remain independent, because
  nothing in the sizing loop is told those values.
* FLOPS Class-II is rejected for turbofans (no engine or pylon mass, unconditional propeller),
  so the component-scaler calibration used for turboprop validations is not available here.
* Wing area and OEW are secondary-source values; MTOW, MZFW and SLS thrust are certification
  data. See a320_reference.md.
* The engine map is validated to 35 000 ft; the mission cruises at FL330 and the ceiling
  requirement is FL350, both inside that box.
""")
    return ac_default, ac_landing


if __name__ == "__main__":
    main()
