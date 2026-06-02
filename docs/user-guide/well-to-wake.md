# Well-To-Wake Analysis

The **Well-To-Wake** (WTW) module (`WellToWake/WellToWake.py`) quantifies the *primary*
(source) energy that must be produced and delivered upstream of the aircraft to fly the
mission, and how much of it comes from electricity versus fuel. It runs at the end of the
sizing loop, after the mission energies are known.

It is enabled by supplying a `WellToTankInput` (typed: `WellToTankConfig`); without it the WTW
quantities are simply not computed.

---

## Two energy pathways

The mission consumes two kinds of on-board energy — fuel chemical energy and battery
electrical energy — each traced back to the primary source through a chain of efficiencies:

- **Electricity:** Source → **Grid** generation & distribution → **Charger** → Battery
- **Fuel:** Source → **Extraction** → **Production / refining** → **Transport** → Fuel tank

The aggregate well-to-tank efficiencies are the products of the chain:

\[
\eta_{\text{src}\to\text{bat}} = \eta_{\text{charge}}\,\eta_{\text{grid}},
\qquad
\eta_{\text{src}\to\text{fuel}} = \eta_{\text{extraction}}\,\eta_{\text{production}}\,
\eta_{\text{transport}} .
\]

---

## Source energy and the electricity fraction

Given the mission energies `aircraft.weight.TotalEnergies = [E_fuel, E_battery]`, the upstream
(source) demand of each pathway is the delivered energy divided by its chain efficiency:

\[
E_{\text{src,fuel}} = \frac{E_{\text{fuel}}}{\eta_{\text{src}\to\text{fuel}}},
\qquad
E_{\text{src,bat}} = \frac{E_{\text{battery}}}{\eta_{\text{src}\to\text{bat}}} .
\]

The module then reports:

- **`SourceEnergy`** — total well-to-wake primary energy, \(E_{\text{src,fuel}} +
  E_{\text{src,bat}}\) [J];
- **`Psi`** — the fraction of source energy that comes from electricity,
  \(\Psi = E_{\text{src,bat}}/(E_{\text{src,bat}} + E_{\text{src,fuel}})\) (0 for a fuel-only
  aircraft, →1 as the design electrifies).

Both are surfaced on `AircraftResults` (`SourceEnergy`, `Psi`).

---

## Inputs

`WellToTankInput` (typed: `WellToTankConfig`):

- `"Eta Charge"` — charger efficiency
- `"Eta Grid"` — grid generation & distribution efficiency
- `"Eta Extraction"` — resource extraction efficiency
- `"Eta Production"` — fuel production / refining efficiency
- `"Eta Transportation"` — fuel distribution / logistics efficiency

A low `Eta Transportation` (or `Eta Grid`) is how you penalize, e.g., a poorly-sourced fuel or
a carbon-heavy grid in the *energy* accounting.

---

## Usage

```python
aircraft.configure(hybrid_config())            # hybrid carries a WellToTankInput
print(aircraft.welltowake.SourceEnergy / 1e6)  # MJ of primary energy
print(aircraft.welltowake.Psi)                 # electricity source fraction

r = aircraft.results()
print(r.SourceEnergy, r.Psi)                    # same values, on the results dataclass
```

See example `14_welltowake_and_climate.py`.

---

## Relationship to emissions

The WTW module intentionally computes only **energy**, not emissions. CO₂-equivalent and
pollutant accounting is done downstream by the [Emissions & Climate Impact](emissions.md)
module, which applies fuel/grid CO₂ intensities and a full radiative-forcing model on top of
the mission.
