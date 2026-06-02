"""Example 06 — The atmosphere and airspeed utilities.

Small, pure helpers the rest of the code is built on: the International Standard
Atmosphere and conversions between Mach, true/calibrated/equivalent airspeed. Handy for
sanity-checking inputs.

Run it:
    cd trunk && python examples/06_utilities_atmosphere_and_speeds.py
"""

import numpy as np

import PhlyGreen.Utilities.Atmosphere as ISA
import PhlyGreen.Utilities.Speed as Speed
from common import savefig


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

    _plot(mach)


def _plot(mach):
    """Plot the ISA profiles and the airspeed-conversion spread vs altitude."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    alts = np.linspace(0, 11000, 60)
    T = [ISA.atmosphere.Tstd(h) for h in alts]
    p = [ISA.atmosphere.Pstd(h) for h in alts]
    a = [Speed.soundspeed(h, 0.0) for h in alts]
    tas = np.array([Speed.Mach2TAS(mach, h) for h in alts])
    cas = np.array([Speed.TAS2CAS(v, h) for v, h in zip(tas, alts)])
    eas = np.array([Speed.TAS2EAS(v, h) for v, h in zip(tas, alts)])

    fig, ax = plt.subplots(1, 4, figsize=(16, 4))
    ax[0].plot(T, alts, color="tab:red"); ax[0].set_xlabel("T [K]"); ax[0].set_ylabel("altitude [m]")
    ax[0].set_title("ISA temperature")
    ax[1].plot(np.array(p) / 1e3, alts, color="tab:blue"); ax[1].set_xlabel("p [kPa]")
    ax[1].set_title("ISA pressure")
    ax[2].plot(a, alts, color="tab:green"); ax[2].set_xlabel("a [m/s]")
    ax[2].set_title("Speed of sound")
    ax[3].plot(tas, alts, label="TAS"); ax[3].plot(cas, alts, label="CAS")
    ax[3].plot(eas, alts, label="EAS"); ax[3].set_xlabel("speed [m/s]")
    ax[3].set_title(f"Airspeeds at Mach {mach}"); ax[3].legend()
    for a_ in ax:
        a_.grid(alpha=0.3)
    fig.tight_layout()
    print("\nFigures:")
    savefig(fig, "06_atmosphere_and_speeds.png")
    plt.close(fig)


if __name__ == "__main__":
    main()
