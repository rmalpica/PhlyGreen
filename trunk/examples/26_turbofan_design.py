"""Example 26 — Sizing a turbofan short-haul jet.

Everything else in this tour sizes a propeller aircraft, where the installed rating is
**shaft power**. A turbofan is rated on **thrust**, and that one difference reaches further
than it looks.

`Performance.PoWTO` returns ``g*[q*V*Cd/(W/S) + beta*Ps]``, which is ``(D*V + W*ROC)/m`` --
thrust power, with no propulsive efficiency in it. So the requirement physics is already
propulsion-agnostic and ``T/W = (P/W)/(g*V)`` exactly. But the design point is *not* just a
change of units: `FindDesignPoint` minimises the largest requirement over wing loading, and
each requirement is evaluated at its own speed, so the minimum-installed-power point and the
minimum-installed-thrust point are different points and can even be set by different
constraints. `Powertrain.SizingDenominator` is what switches the diagram between the two.

Two more things follow from the choice of a jet:

* **the drag polar**. A transport cruises close to drag divergence, so the 'compressible'
  polar (Korn M_dd + Lock wave drag) is not optional decoration -- the plain quadratic polar
  has no wave drag at all and understates cruise drag exactly where the design lives.
* **the engine model**. The turbofan is a single overall-efficiency node,
  ``eta_o = F*V/(mdot_f*LHV)``, read from a pyCycle response surface. That is the same
  information as a TSFC map, since ``TSFC = V/(eta_o*LHV)``, and this script checks that
  identity on the sized aircraft rather than asserting it.

Run it:
    cd trunk && python examples/26_turbofan_design.py
"""

import numpy as np

import PhlyGreen as pg
from common import turbofan_config, savefig
from PhlyGreen.Systems.Powertrain.turbofan_surrogate import TurbofanResponseSurface

LHV = 43.0e6   # Jet-A [J/kg], the value the map was generated with


def show_engine_map():
    """The response surface on its own, before any aircraft is involved."""
    s = TurbofanResponseSurface()
    print(f"Turbofan map: {s.tag}")
    print(f"{'condition':<34}{'eta_o':>8}{'TSFC':>12}{'lapse':>9}")
    print("-" * 63)
    F00 = 240e3
    for label, alt_ft, mach, pc in [
            ("take-off      SL     M 0.25", 0., 0.25, 1.00),
            ("climb         10 kft M 0.55", 10000., 0.55, 0.90),
            ("cruise        35 kft M 0.78", 35000., 0.78, 0.70),
            ("cruise fast   35 kft M 0.85", 35000., 0.85, 0.85),
            ("descent idle  20 kft M 0.60", 20000., 0.60, 0.30)]:
        lapse = s.thrust_lapse(alt_ft, mach)
        eta, tsfc, avail, limited = s.predict(F00, alt_ft, mach, pc * F00 * lapse)
        # TSFC in the customary lb/(lbf h) so it can be read against published data.
        tsfc_imp = tsfc * 3600.0 * 9.80665
        print(f"{label:<34}{eta:>8.3f}{tsfc_imp:>9.3f} lb/lbf/h{lapse:>9.3f}")
    # The map stops at 35,000 ft because the deck's off-design solve stops converging above
    # it (see HBTF_turbofan.ENVELOPE). Inputs are clipped to that box, so asking above it
    # returns the 35,000 ft answer rather than an extrapolation -- safe, but optimistic on
    # available thrust, so it is worth seeing rather than discovering by accident.
    hi = s.thrust_lapse(39000., 0.80)
    top = s.thrust_lapse(35000., 0.80)
    print(f"note: the map is validated to 35,000 ft; a query at 39,000 ft is clipped to it "
          f"(lapse {hi:.3f} vs {top:.3f} at the ceiling of the box).")
    print()


def main():
    show_engine_map()

    print("Sizing an A320/737-800-class turbofan ...")
    ac = pg.build_aircraft()
    ac.configure(turbofan_config(), PrintOutput=True)
    r = ac.results()

    # --- the eta_o <-> TSFC identity, checked on the sized aircraft -----------------
    # If these disagree, the fuel closure and the engine map have parted company.
    import PhlyGreen.Utilities.Speed as Speed
    cruise = ac.constraint.CruiseConstraints
    alt = cruise['Altitude']
    v = Speed.Mach2TAS(cruise['Speed'], alt, ac.constraint.DISA)

    # Actual cruise thrust from the drag polar at the converged design, rather than a guess:
    # PoWTO returns thrust power per unit mass, so thrust = PoWTO * WTO / V.
    pw_cruise = ac.performance.PoWTO(ac.DesignWTOoS, cruise['Beta'], 0, 1.,
                                     alt, ac.constraint.DISA, cruise['Speed'],
                                     cruise['Speed Type'])
    thrust_cruise = float(pw_cruise) * ac.weight.WTO / v

    print("\n--- overall efficiency vs TSFC (the same statement twice) ---")
    print(f"cruise condition           : {alt:.0f} m, M {cruise['Speed']:.2f}, "
          f"V = {v:.1f} m/s, thrust = {thrust_cruise/1000:.1f} kN")
    eta_cruise = ac.powertrain.eta('gas_turbine', alt, v, thrust_cruise * v)
    print(f"cruise eta_o               : {eta_cruise:.4f}")
    print(f"TSFC from eta_o = V/(eta*LHV): "
          f"{v/(eta_cruise*LHV)*3600*9.80665:.4f} lb/(lbf h)")
    print(f"mission-mean TSFC          : {r.mean_TSFC*3600*9.80665:.4f} lb/(lbf h)")

    print("\n--- design summary ---")
    print(f"design T/W                 : {r.DesignTW:.4f} [-]")
    print(f"design W/S                 : {ac.DesignWTOoS:.0f} N/m2 "
          f"({ac.DesignWTOoS/9.81:.0f} kg/m2)")
    print(f"SLS thrust rating          : {r.engineRating/1000:.1f} kN "
          f"({r.engineRating_units})")
    print(f"MTOW                       : {r.WTO:.0f} kg")
    print(f"OEW (empty)                : {r.empty_weight:.0f} kg")
    print(f"block fuel                 : {ac.weight.Wf + ac.weight.final_reserve:.0f} kg")
    print(f"wing area                  : {ac.WingSurface:.1f} m2")

    # --- against the real aircraft ---------------------------------------------------
    # Reference values are sourced and cited in validation/a320_reference.md: MTOW and the
    # engine thrust rating are certification data (Airbus ACAP, EASA TCDS A.064); wing area
    # and OEW are secondary-source figures. Stated, not tuned.
    print("\n--- against an A320-200 ---")
    for label, got, ref in [("MTOW  [kg]", r.WTO, 73500.0),
                            ("OEW   [kg]", r.empty_weight, 42175.0),
                            ("S     [m2]", ac.WingSurface, 122.6),
                            ("SLS thrust/engine [kN]", r.engineRating / 2000, 120.1)]:
        print(f"{label:<24}{got:>10.1f}{ref:>10.1f}   {100*(got-ref)/ref:+6.1f}%")
    print(f"{'OEW/MTOW [-]':<24}{r.empty_weight/r.WTO:>10.3f}{42175.0/73500.0:>10.3f}"
          f"   {100*((r.empty_weight/r.WTO)/(42175.0/73500.0)-1):+6.1f}%")

    print("""
Reading these numbers
---------------------
The absolute masses come out light, the empty-weight FRACTION does not. Raymer's Class-I jet
regression under-predicts this particular aircraft's empty weight by ~13 %, and that propagates
to take-off weight; the fraction it predicts is within a couple of percent. The powertrain mass
is deliberately not added on top of that regression (`avoid_powertrain_double_count`), because
an empty-weight fraction already contains the installed engines -- adding them again used to
make the totals look better only by cancelling the under-prediction.

Note too that this design point minimises installed THRUST, which is not the same as minimising
take-off weight: a narrow-body is sized at its landing-field wing-loading limit, where the wing
is smaller and the aircraft lighter. validation/a320_reference.py reports both, with a
wing-loading sweep showing the difference.""")

    return ac


if __name__ == "__main__":
    main()
