"""Example 06 — The atmosphere and airspeed utilities.

Small, pure helpers the rest of the code is built on: the International Standard
Atmosphere and conversions between Mach, true/calibrated/equivalent airspeed. Handy for
sanity-checking inputs.

Run it:
    cd trunk && python examples/06_utilities_atmosphere_and_speeds.py
"""

import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed


def main():
    print(f"{'alt [m]':>8} {'T [K]':>8} {'p [Pa]':>10} {'a [m/s]':>9}")
    for h in (0, 4000, 8000, 11000):
        print(f"{h:8d} {ISA.atmosphere.Tstd(h):8.1f} "
              f"{ISA.atmosphere.Pstd(h):10.0f} {Speed.soundspeed(h, 0.0):9.1f}")

    print("\nAirspeed conversions at 8000 m:")
    mach = 0.4
    tas = Speed.Mach2TAS(mach, 8000)
    print(f"  Mach {mach}  ->  TAS {tas:6.1f} m/s")
    print(f"  TAS {tas:.1f} m/s  ->  CAS {Speed.TAS2CAS(tas, 8000):6.1f} m/s  "
          f"(lower than TAS: thinner air aloft)")
    print(f"  TAS {tas:.1f} m/s  ->  EAS {Speed.TAS2EAS(tas, 8000):6.1f} m/s")


if __name__ == "__main__":
    main()
