# Airbus A320-200 (A320-214, CFM56-5B4) — reference dossier

Reference data for validating PhlyGreen's `Turbofan` configuration. Every row is labelled
**primary** (certification or manufacturer publication) or **secondary** (industry reference
work). The distinction matters: only primary rows are certification-grade, and the comparison
in `a320_reference.py` says which it is using.

## Sources

| key | document | retrieved |
|---|---|---|
| **ACAP** | Airbus, *A320 Aircraft Characteristics — Airport and Maintenance Planning*, Rev. Jun 01/24 (`AC_A320_0624.pdf`, 427 pp). https://www.aircraft.airbus.com/sites/g/files/jlcbta126/files/2025-01/AC_A320_0624.pdf | 2026-09 |
| **TCDS-N** | EASA, *Type-Certificate Data Sheet for Noise* `EASA.A.064.3`, Issue 28, 18 Nov 2020, p. 15. https://www.easa.europa.eu/sites/default/files/dfu/tcdsn_easa.a.064.3_issue_28.pdf | 2026-09 |
| **TCDS** | EASA, *Type-Certificate Data Sheet* `EASA.A.064` Issue 12, 12 Sep 2013, §Powerplant (p. 24). https://www.easa.europa.eu/certification/type-certificates/docs/aircraft/EASA-TCDS-A.064_AIRBUS_A318,_A319,_A320,_A321_Single_Aisle-12-12092013.pdf | 2026-09 |
| **FZI** | flugzeuginfo.net, A320 technical data. https://www.flugzeuginfo.net/acdata_php/acdata_a320_en.php | 2026-09 |
| **ICAO-EDB** | ICAO Aircraft Engine Emissions Databank, CFM56-7B27E — as transcribed into `Systems/Powertrain/emissions_pipeline/crn/evap_model_ottimizzato.py` by the CRN's original author | in-repo |

## Primary data

The validation targets the **WV017** weight variant: the high-gross-weight A320-200 with
CFM56-5B4, which is the variant usually quoted as "the" A320-200 and the one whose range matches
a 3000 nm design mission. The ACAP lists MTOWs from 66 000 to 78 000 kg across weight variants,
so the variant must be named for the comparison to mean anything.

| quantity | value | source | note |
|---|---|---|---|
| Maximum Take-Off Weight (MTOW) | **78 000 kg** | ACAP §2-1-1 p. 34 (WV017); TCDS-N p. 15 rec. A17309 | certified |
| Maximum Ramp / Taxi Weight (MRW) | 78 400 kg | ACAP §2-1-1 p. 34 (WV017) | |
| Maximum Landing Weight (MLW) | 66 000 kg | ACAP §2-1-1 p. 34 (WV017) | |
| Maximum Zero Fuel Weight (MZFW) | **62 500 kg** | ACAP §2-1-1 p. 34 (WV017) | |
| (base variant, for reference) | MTOW 73 500 / MZFW 60 500 kg | ACAP §2-1-1 p. 33 (WV000) | WV000 |
| Wing span | 34.10 m | ACAP §2-2 dimensions drawing p. 40 | |
| Total usable fuel (CFM, wing + centre) | 15 959 l + 8 250 l = **24 209 l** | ACAP §2-1-1 p. 37 | ≈ 19 000 kg at 0.785 kg/l |
| Standard seating capacity | 180 (single-class) | ACAP §2-1-1 p. 37 | |
| Engine | CFM56-5B4 | TCDS-N p. 15 (A320-214) | SAC combustor (mod. 24251) |
| SLS take-off thrust (5 min, flat rated 30 °C) | **12 010 daN = 120.1 kN** (27 000 lbf) | TCDS §Powerplant p. 24 | per engine → 240.2 kN installed |
| SLS maximum continuous (flat rated 25 °C) | 10 840 daN = 108.4 kN | TCDS §Powerplant p. 24 | |

## Secondary data

Not certification data. Used for quantities the primary sources do not carry, and flagged as
secondary wherever compared.

| quantity | value | source | note |
|---|---|---|---|
| Wing reference area | **122.6 m²** | FZI | consistent with span: AR = 34.10²/122.6 = 9.49 |
| Operating Empty Weight (OEW), CFM56 | **42 600 kg** | A320-200 CFM56 industry figure | see caveat 1 |
| Range, typical load | 5 700 km = **3 078 nm** | FZI | basis of the design mission |
| Service ceiling | 39 800 ft | FZI | above the engine map's box — see caveat 3 |
| M_MO | 0.82 | FZI | design cruise taken as M 0.78 |
| Wing sweep at 25 % MAC | 24° 58′ ≈ **25.0°** | airliners.net | used by the Korn drag-divergence model |

## Derived

| quantity | value | derivation |
|---|---|---|
| Aspect ratio | 9.49 | span² / area = 34.10² / 122.6 (both sourced) |
| Maximum payload | 19 900 kg | MZFW − OEW = 62 500 − 42 600 |
| Design payload, 150 pax two-class | **14 250 kg** | 150 × 95 kg/pax incl. baggage (Airbus standard passenger mass) |
| Wing loading at MTOW | 636.2 kg/m² | MTOW / S |
| Installed thrust-to-weight at MTOW | 0.314 | 2 × 120.1 kN / (78 000 × 9.81) |
| Empty-weight fraction | 0.546 | OEW / MTOW |

## Design mission used for the validation

150 passengers two-class (14 250 kg) over 3 000 nm, with a 200 nm alternate and a 30 min hold.
The 3 000 nm figure is the round number just below the 3 078 nm typical-load range above; it is
the mission the published masses correspond to, which is why MTOW/OEW are meaningful targets
against it. (The Phase-1 example used 1 500 nm / 15 t and came out 21 % light on MTOW — the right
answer to a different question.)

## Caveats and ambiguous points

1. **OEW is operator-specific and is *not* in the ACAP.** The ACAP publishes MRW/MTOW/MLW/MZFW
   only. The 42 600 kg used here is a secondary figure; it is however consistent with the
   certified MZFW, since MZFW − OEW = 19 900 kg reproduces the commonly quoted ~19.9 t maximum
   payload. Treat the OEW comparison as indicative, not certification-grade. Note also that
   flugzeuginfo lists "37 230 kg" as empty weight — that is the *manufacturer's* empty weight
   (MWE), a different quantity, and is **not** used here.

2. **Empty weight: two separate issues, both now fixed.**
   *(a) Double counting.* Class-I models are **empty**-weight regressions, so they already contain
   the installed powertrain; adding `Weight.WPT` on top counted the engines twice. That second
   count is now off for this configuration (`avoid_powertrain_double_count=True`), in the weight
   closure **and** in the reported empty weight.
   *(b) The textbook jet fraction is a poor fit for a narrow-body.* Raymer's
   `We/W0 = 0.97·W0^-0.06` gives 0.495 at 78 t, against ~0.546 for an A320-200 — about 10 % low.
   Used together, (a) and (b) cancelled: the totals looked right for the wrong reason. The
   `'NarrowBody'` aircraft type replaces that fraction with a regression fitted to six in-service
   narrow-bodies (A319/A320/A321, B737-700/-800/-900ER), each reproduced within 2 %:

   \[ W_e/W_0 = 4.2747\,W_0^{-0.1844} \]

   This is a fit to a **population of aircraft**, not a calibration to this design's answer, so
   MTOW, wing area and installed thrust remain independent checks. The MTOW/OEW figures those
   six pairs come from are secondary-source and are listed in `Structures.NARROW_BODY_FIT`.

3. **The engine map is validated to 35 000 ft**, below the A320's 39 800 ft service ceiling.
   `TurbofanResponseSurface` clips inputs to its training box, so a query above 35 000 ft returns
   the 35 000 ft answer — safe, but **optimistic on available thrust**. The design mission
   therefore cruises at FL330 with the ceiling requirement at FL350, both inside the box. A
   genuine FL390 ceiling constraint would need the deck extended first.

4. **This validation is Class-I only.** A Class-II (FLOPS) component build-up of the same
   aircraft, with the certified CFM56-5B4 dry weight and sourced geometry, is in
   `flops_class_ii_reference.py` (inputs: `flops_class_ii_reference.md`).

5. **Emission indices are referenced to the CFM56-7B27E**, not the -5B4, because that is the
   engine the Cantera CRN was calibrated against and the ICAO values transcribed in-repo. The
   emission *index* is engine-size-independent (a function of thrust fraction), so this is
   defensible for a CFM56-class comparison, but the two engines are not the same hardware and the
   agreement should be read at that resolution.

## TO VERIFY

- Design range at exactly 150 pax / 14 250 kg from an Airbus source (the 3 078 nm figure is
  secondary and its payload basis is not stated).
- The ICAO EDB entry for the **CFM56-5B4** specifically, to quantify how far its LTO emission
  indices sit from the -7B27E values used here.
- OEW from a manufacturer or operator publication rather than a reference site.
