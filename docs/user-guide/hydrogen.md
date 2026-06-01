# Hydrogen: Fuel Cell & Tank

PhlyGreen models hydrogen-electric aircraft in two configurations: a pure fuel-cell
(`'Hydrogen'`) and a fuel-cell + battery hybrid (`'FuelCellBattery'`).

## Fuel cell

`Systems/FuelCell/FuelCell.py` is a physics-based PEM fuel-cell model (Kulikovsky
polarization curve, cathode air-system power, stack sizing). For the mission it returns,
through `ComputePRatio(alt, vel, P_net)`, the hydrogen *chemical* power required to deliver a
given net shaft power (i.e. the inverse system efficiency). The stack parameters come from
`FC_Database` (`Systems/FuelCell/FC_Models.py`); the design knobs are set in `EnergyConfig`:

```python
energy = EnergyConfig(
    Ef=120e6,                       # hydrogen lower heating value [J/kg]
    eta_gearbox=0.96, eta_pmad=0.99, eta_electric_motor=0.96,
    fc_model='PEMFC_GoodPerformance',
    i_rated=2.5,                    # rated current density [A/cm^2]
    v_cell_design=0.5,              # design cell voltage [V]
    stack_power_density=3000,       # [W/kg]
    bop_mass_ratio=0.40,            # balance-of-plant / stack mass
)
```

The mission (`Mission.HydrogenConfiguration`) integrates the hydrogen chemical energy; the
weight loop (`Weight.Hydrogen`) sizes the fuel cell to the actual mission peak
(`FuelCell.FinalizeMassFromMission`) and closes the take-off weight over structure +
fuel-cell system + hydrogen + tank + cooling. A `FuelCellBattery` design with a zero battery
share reproduces a pure `Hydrogen` design exactly.

## Cryogenic LH2 tank

`Systems/Tank/` provides `LH2_Tank`: structural + multi-layer-insulation sizing (after
Svensson et al.) and a transient `time_step` model of the tank thermodynamic state — heat
ingress self-pressurizes the tank, a valve vents at the maximum pressure, and a heater adds
power at the minimum pressure. It requires **CoolProp** (para-hydrogen properties) and is
therefore optional: with a `TankConfig` and CoolProp installed it is used for sizing;
otherwise a simple gravimetric-index mass model is used.

```python
from PhlyGreen.config import TankConfig
config.tank = TankConfig(max_diameter=2.4, number_of_tanks=1, tank_model='Svensson_Default')
```

To see the tank state evolve over the mission, switch on tracking and re-fly:

```python
aircraft.configure(config)                       # sizes the tank
aircraft.mission.track_tank = True
aircraft.mission.EvaluateMission(aircraft.weight.WTO)
from PhlyGreen import postprocess as pp
pp.plot_tank_state(aircraft)                      # pressure / mass / vent vs time
```

See example `22_hydrogen_tank.py` and notebook `03_hydrogen_fuel_cell.ipynb`.

## Fuel cell + battery

`'FuelCellBattery'` splits the propulsive power between the fuel cell and a (Class-I)
battery via the profile's supplied-power ratio φ (the battery fraction). The fuel cell uses
its physics efficiency; the battery is sized from its energy and power needs. Because the
battery stores little energy per kg, hybridization helps short power-limited segments more
than sustained cruise — see example `23_fuelcell_battery_hybrid.py`.

## Thermal management (scaffold)

`Systems/Thermal/` provides the interfaces for a future heat-exchanger-network module
(`HeatSource`, `HeatSink`, `HeatExchangerNetwork`). The fuel cell's heat load and the tank's
heat leak can register as sources today; a detailed coolant-loop sizing model will plug into
the same interfaces.
