"""Example 04 — Inspect the flight profile, and add your own segment type.

The mission profile is a sequence of segments (climb / cruise / descent). PhlyGreen builds
a continuous timeline you can query for altitude, speed, vertical rate, and the hybrid
power ratio phi at any time. Segment types live in a registry, so you can add a new one in
a few lines without touching the profile machinery.

Run it:
    cd trunk && python examples/04_flight_profile_and_custom_segment.py
"""

import numpy as np

import PhlyGreen as pg
from PhlyGreen.Mission.segments import (
    FlightSegment, SegmentResult, register_segment, CLIMB,
)
from common import hybrid_config, savefig


def inspect_profile():
    # configure(design=False) only reads inputs and builds the profile (no sizing loop).
    aircraft = pg.build_aircraft()
    aircraft.configure(hybrid_config(), design=False)
    profile = aircraft.mission.profile

    print(f"Total mission time: {profile.MissionTime2/60:.1f} min")
    print(f"{'t [min]':>8} {'alt [m]':>9} {'TAS [m/s]':>10} {'Pexc [m/s]':>11} {'phi':>6}")
    for t in np.linspace(0, profile.MissionTime2, 13):
        print(f"{t/60:8.1f} {float(profile.Altitude(t)):9.0f} "
              f"{float(profile.Velocity(t)):10.1f} {float(profile.PowerExcess(t)):11.2f} "
              f"{float(profile.SuppliedPowerRatio(t)):6.2f}")

    _plot_profile(profile)


def _plot_profile(profile):
    """Plot the continuous altitude / TAS / vertical-rate / phi timeline."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    t = np.linspace(0, profile.MissionTime2, 400)
    alt = [float(profile.Altitude(x)) for x in t]
    tas = [float(profile.Velocity(x)) for x in t]
    pexc = [float(profile.PowerExcess(x)) for x in t]
    phi = [float(profile.SuppliedPowerRatio(x)) for x in t]
    tm = t / 60.0
    fig, ax = plt.subplots(4, 1, sharex=True, figsize=(8, 9))
    ax[0].plot(tm, alt, color="tab:blue"); ax[0].set_ylabel("altitude [m]")
    ax[1].plot(tm, tas, color="tab:orange"); ax[1].set_ylabel("TAS [m/s]")
    ax[2].plot(tm, pexc, color="tab:green"); ax[2].set_ylabel("power excess [m/s]")
    ax[3].plot(tm, phi, color="tab:purple"); ax[3].set_ylabel("phi [-]")
    ax[3].set_xlabel("time [min]")
    for a in ax:
        a.grid(alpha=0.3)
    fig.suptitle("Hybrid mission profile (queried from Profile)")
    fig.tight_layout()
    print("\nFigures:")
    savefig(fig, "04_flight_profile.png")
    plt.close(fig)


def add_custom_segment():
    # A new segment type: climb for a fixed *duration* at constant gradient and speed.
    @register_segment("ConstantTimeClimb")
    class ConstantTimeClimbSegment(FlightSegment):
        category = CLIMB

        def compute(self, phase_range, distance_so_far):
            v = self.inputs["Speed"]
            duration = self.inputs["Duration"]
            return SegmentResult(
                start_altitude=self.inputs["StartAltitude"],
                vertical_rate=self.inputs["CB"] * v,
                velocity=v, duration=duration, distance=v * duration, category=CLIMB,
            )

    seg = ConstantTimeClimbSegment("Climb", {"StartAltitude": 0, "CB": 0.1,
                                             "Speed": 80, "Duration": 120})
    result = seg.compute(phase_range=0, distance_so_far=0)
    print(f"\nCustom segment climbs to {result.start_altitude + result.vertical_rate*result.duration:.0f} m "
          f"in {result.duration:.0f} s")


if __name__ == "__main__":
    inspect_profile()
    add_custom_segment()
