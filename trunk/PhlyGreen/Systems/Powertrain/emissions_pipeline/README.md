# GT emission-surrogate generation pipeline (offline)

Reproducible offline generation of the **PW127 emission-index surrogate** that the package ships
(`../data/PW127_Emission_Map.csv` → `../data/Emission_Model_PW127.pkl`, loaded at run time by
`../emissions_surrogate.py`). This mirrors the gas-turbine *efficiency* map's pipeline
(`../data/Single_spool_GT.py` → `../train_gas_turbine_surrogate.py`).

**Optional heavy dependencies** (only needed to *regenerate* — the shipped `.pkl`/`.csv` do not
need them): `pycycle` + `openmdao` (engine cycle) and `cantera` (the chemical reactor network).
Install e.g. `pip install pycycle openmdao cantera`.

## What it does (two-stage, certification-anchored)

```
(alt, Mach, power)  --pyCycle PW127 deck-->  combustor state (T3,P3,FAR,ṁ)  --Cantera CRN-->  EI
```

1. **`pw127_deck.py`** — re-tunes the 2-shaft turboshaft deck (`../data/Single_spool_GT.py`) to
   PW127 (OPR 14.7; rated power set so SLS take-off fuel flow matches the FOCA/EASA certification),
   and exports the combustor inlet state over a flight-envelope grid.
2. **`pw127_partpower.py`** — calibrates the gas-generator power schedule `G(f)` so the deck
   reproduces the certified part-power fuel flow (idle/approach), then writes the
   **part-power-corrected** combustor-state envelope `pw127_crn_inputs_corrected.csv` (Mach ≥ 0.1;
   Mach=0 static is a deck convergence artifact).
3. **`build_pw127_surrogate.py`** — runs the **CRN** (`crn/evap_model_ottimizzato.py`, calibrated
   to PW127 with primary-zone air fraction `ARPZ = 0.24`) over the corrected envelope. CO/UHC come
   from the CRN directly; **NOx keeps the CRN's altitude/Mach/power shape but is rescaled (anchored)
   to the PW127 ICAO NOx** at the sea-level modes. Writes `../data/PW127_Emission_Map.csv` and fits
   `../data/Emission_Model_PW127.pkl` via `../train_emission_surrogate.py`.

## Regenerate

```bash
cd PhlyGreen/Systems/Powertrain/emissions_pipeline
python pw127_partpower.py        # -> pw127_crn_inputs_corrected.csv  (pyCycle, ~1-2 min)
python build_pw127_surrogate.py  # -> ../data/PW127_Emission_Map.csv + Emission_Model_PW127.pkl (Cantera, ~2 min)
```

## Calibration provenance / how the constants were chosen
- `crn/` — the Chemical Reactor Network and its kerosene mechanism (`kerosene_surrogate_luche.yaml`),
  from A. Pietrosanto's thesis (Luche surrogate, evaporation model, 9-PSR primary zone + SZ + DZ),
  calibrated to ICAO LTO data.
- **`ARPZ = 0.24`** (richer primary zone than the CFM56 baseline 0.31) is the PW127 NOx/CO tune —
  derived by `calibrate_crn_pw127.py` (scan vs the 4 ICAO modes). With it the CRN matches PW127 CO
  at all 4 modes; NOx is too peaky for this network structure, hence the certification anchor.
- `probe_crn_levers.py`, `calibrate_crn_pw127.py`, `crn_smoke_test.py` — diagnostics for the
  calibration (lever sensitivity, ARPZ scan, single-point smoke test).

## Notes
- The NOx is *certification-anchored*, not physically calibrated; a physically-calibrated NOx would
  need a staged/pilot primary zone in the CRN (future work). Soot (omnisoot, nvPMF anchor targets)
  is documented in `EMISSIONS_MODEL_NOTES.md` for a future phase.
- The emission index is engine-size-independent (function of power fraction only), like the GT
  efficiency map — the GT efficiency size-scaling does not affect it.

---

## Turbofan (CFM56-class) branch

The CRN in `crn/` is **natively a CFM56-7B27E model** — its docstring, its air splits
(`ARPZ = 0.3082`) and its ICAO reference EIs are all CFM56. The PW127 build *monkey-patches* that
calibration at import time; the turbofan build simply does not, so retargeting is mostly a matter
of **removing** PW127-specific patches rather than re-deriving chemistry.

The turbofan combustor box lands inside the CRN's native calibration box, which is why this works:

| | CFM56 CRN calibration | turbofan map | PW127 |
|---|---|---|---|
| T3 [K] | 477–795 | 551–796 | 469–662 |
| FAR | 0.014–0.026 | 0.0153–0.0290 | 0.0091–0.0172 |
| ṁ_air3 [kg/s] | 8.3–47.5 | 9.9–42.6 | 2.2–9.5 |

```bash
# step 1 is already done by the engine deck: data/HBTF_turbofan.py exports
#   T3_K, P3_Pa, FAR, mdot_air3 alongside the efficiency map, from bld3 (true combustor inlet).
python build_turbofan_surrogate.py      # CRN -> ../data/Turbofan_Emission_Map.csv + ..._Turbofan.pkl
python validation_plots.py turbofan     # vs the CFM56 ICAO LTO data
```

Three PW127-isms are deliberately absent from `build_turbofan_surrogate.py`:

1. **the ARPZ renormalisation to 0.24** — a richer primary zone fitted to the turboprop;
2. **the `max(chi, 1.20)` floor** on the mixer scale. `chi` falls 1.50 → 1.00 as T3 rises
   477 → 795 K, so a 1.20 floor clamps everything above ~640 K. The PW127 box topped out at
   662 K so it barely bit; the turbofan box runs to 796 K, where the floor would silently
   discard the CRN's own climb (1.07) and take-off (1.00) values — i.e. it would not be running
   the CFM56 calibration at all;
3. **the flat `dPqP = 0.95`** — the HBTF deck's own burner loss (0.946) is used instead.

**NOx is not anchored here.** The PW127 anchor exists because an equal-split CRN cannot reproduce
a *staged* turboprop combustor. This CRN is native to the engine class being asked about, so its
raw NOx is reported and compared against ICAO. At the CRN's own four LTO states it gives
+16 % (take-off), +29 % (climb), +19 % (approach) on NOx — a genuine prediction, not an assertion.
Pass `--anchor-nox` to rescale to certification instead; the script then says so in its output,
and so should anything built on it.

Note the reference engine is the **CFM56-7B27E** (the CRN's calibration), while the A320
validation flies a **CFM56-5B4**. The emission *index* is engine-size independent, so this is
defensible for a CFM56-class comparison, but the two are not the same hardware.
