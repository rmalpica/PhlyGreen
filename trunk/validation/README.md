# Validation

Quantitative validation of PhlyGreen designs against published reference aircraft.


| ID | aircraft | configuration | script | dossier | status |
|----|----------|---------------|--------|---------|--------|
| A320 | Airbus A320-200 (A320-214, CFM56-5B4) | `Turbofan`, Class-I | `a320_reference.py` | `a320_reference.md` | see script output |
| H2-ATR42 | hydrogen fuel-cell ATR 42 variant vs published fuel-cell regional designs (Svensson et al. 2024 mission) | `Hydrogen`, Class-I | `hydrogen_atr42_reference.py` | `docs/user-guide/reference-aircraft.md` §2 | see script output |

## Rules

1. **Do not report agreement against unverified numbers.** Every reference value carries its
   source in the dossier, labelled *primary* (certification / manufacturer) or *secondary*
   (industry reference). Anything unsourced is marked `TO VERIFY` and is excluded from the
   comparison rather than quietly compared against.
2. **Reference values are inputs, never fitting targets.** Where PhlyGreen disagrees, the
   disagreement is reported and diagnosed — it is not calibrated away.
3. Known model limitations that bias a comparison are stated *with their sign* next to the
   affected row.

Run:

```bash
cd trunk && python validation/a320_reference.py
cd trunk && python validation/hydrogen_atr42_reference.py
```

Figures are written to `validation/figures/` (headless, `matplotlib.use("Agg")`).
