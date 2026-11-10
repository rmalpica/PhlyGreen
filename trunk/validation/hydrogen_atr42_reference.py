"""Hydrogen fuel-cell variant of the ATR 42 reference, against published fuel-cell designs.

Produces the numbers of section 2 of ``docs/user-guide/reference-aircraft.md``:

1. the hydrogen variant (``examples/common.py: hydrogen_config()``) with the Class-I and the
   Class-II thermal-management system: take-off weight, fuel-cell net rating, fuel-cell system
   mass and TMS mass;
2. the same aircraft flown on the mission inputs of Svensson, Oliveira and Groenstedt,
   Int. J. Hydrogen Energy 61 (2024) 650, doi:10.1016/j.ijhydene.2024.02.382: 648 nm design
   range, 100 nm alternate, 5,500 kg payload and a tank gravimetric index of 0.555. Their
   resized all-fuel-cell ATR 42 has an MTOW of 21.05 t;
3. the MTOW / payload ratio of the PhlyGreen variant and of the published designs listed in
   the docs table (values as printed in each publication).

Run from ``trunk/``:

    python validation/hydrogen_atr42_reference.py
"""

import os
import sys
import warnings

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "examples"))

import PhlyGreen as pg                                   # noqa: E402
from PhlyGreen.config import TMSConfig                   # noqa: E402
from common import hydrogen_config                       # noqa: E402

# Published fuel-cell regional designs: (label, design range [nm], payload [kg], MTOW [kg]).
# Sources and full citations: docs/user-guide/reference-aircraft.md, section 2.
LITERATURE = [
    ("Svensson et al. 2024 (50 pax)", 648, 5500, 21050),
    ("Eissele et al. 2023 (50 pax, FC + battery)", 432, 5300, 19600),
    ("Schlittenhardt et al. 2025 (70 pax)", 432, 6650, 23640),
    ("FlyZero FZR-1E 2022 (75 pax)", 800, 7875, 28800),
]

# Svensson et al. (2024) mission inputs.
SVENSSON_RANGE_NM = 648.0
SVENSSON_DIVERSION_NM = 100.0
SVENSSON_PAYLOAD_KG = 5500.0
SVENSSON_GRAVIMETRIC_INDEX = 0.555
SVENSSON_MTOW_KG = 21050.0


def design(cfg):
    """Size ``cfg`` and return the aircraft."""
    aircraft = pg.build_aircraft()
    aircraft.configure(cfg)
    return aircraft


def hydrogen_variant(tms_class):
    """The hydrogen ATR 42 variant with the given TMS class ('I' or 'II')."""
    cfg = hydrogen_config()
    cfg.tms = TMSConfig(tms_class=tms_class)
    return design(cfg)


def svensson_mission(tms_class):
    """The hydrogen variant flown on the Svensson et al. (2024) mission inputs."""
    cfg = hydrogen_config()
    cfg.tms = TMSConfig(tms_class=tms_class)
    cfg.mission.range_mission = SVENSSON_RANGE_NM
    cfg.mission.range_diversion = SVENSSON_DIVERSION_NM
    cfg.mission.payload_weight = SVENSSON_PAYLOAD_KG
    cfg.energy.h2_gravimetric_index = SVENSSON_GRAVIMETRIC_INDEX
    return design(cfg)


def summary_row(label, aircraft):
    r = aircraft.results()
    return (f"{label:34s} {r.WTO:9.0f} {aircraft.fuelcell.P_fc_rated / 1e6:9.3f} "
            f"{r.WPT:10.0f} {r.hex_mass:8.0f} {r.WTO / r.WPayload:8.2f}")


def main():
    warnings.simplefilter("ignore")
    header = (f"{'case':34s} {'MTOW kg':>9s} {'FC MW':>9s} {'FC sys kg':>10s} "
              f"{'TMS kg':>8s} {'MTOW/PL':>8s}")

    print("=== Hydrogen ATR 42 variant (750 nm + 220 nm, 4,560 kg payload) ===")
    print(header)
    for cls in ("I", "II"):
        print(summary_row(f"TMS Class {cls}", hydrogen_variant(cls)))

    print("\n=== Svensson et al. (2024) mission inputs "
          "(648 nm + 100 nm, 5,500 kg, gravimetric index 0.555) ===")
    print(header)
    for cls in ("I", "II"):
        a = svensson_mission(cls)
        print(summary_row(f"TMS Class {cls}", a)
              + f"   {100 * (a.weight.WTO / SVENSSON_MTOW_KG - 1):+5.1f} % vs 21,050 kg")

    print("\n=== Published designs, MTOW / payload ===")
    for label, rng, payload, mtow in LITERATURE:
        print(f"{label:44s} {rng:5.0f} nm {payload:6.0f} kg {mtow:7.0f} kg   {mtow / payload:5.2f}")


if __name__ == "__main__":
    main()
