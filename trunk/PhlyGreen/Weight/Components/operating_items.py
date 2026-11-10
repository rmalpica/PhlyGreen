"""FLOPS propulsion-system and operating items (Aviary transport equations), imperial units.

These are the FLOPS groups of the operating empty weight that are neither airframe structure
nor the engines themselves:

* fuel system (``fuel_system.py``, ``TransportFuelSystemMass``);
* unusable fuel (``unusable_fuel.py``, ``TransportUnusableFuelMass``);
* engine oil (``engine_oil.py``, ``TransportEngineOilMass``);
* starter (``starter.py``) and engine controls (``engine_controls.py``);
* thrust reversers (``thrust_reverser.py``), when ``FLOPSInput['ENGINE']['THRUST_REVERSERS']``
  is True;
* passenger service (``passenger_service.py``, ``PassengerServiceMass``).

The fuel-system and unusable-fuel equations describe a kerosene fuel system; the starter,
engine controls and oil describe gas turbines. In the fuel-cell configurations
('Hydrogen', 'FuelCellBattery') there is no gas turbine, and the hydrogen tank system is
sized separately (``Weight._hydrogen_tank_mass``), so these items are zero there. Cargo
containers and the flight and cabin crew are not in this group: the crew is the mission
input ``'Crew Weight'``.
"""

from .sizing_inputs import (max_mach, design_range_nm, engine_count_factor,
                            sls_thrust_per_engine_lbf, wing_area_ft2)

FUEL_CELL_CONFIGURATIONS = ('Hydrogen', 'FuelCellBattery')


class OperatingItems:

    def __init__(self, aircraft, input):
        self.aircraft = aircraft
        self.input = input

    def _has_gas_turbine(self):
        return self.aircraft.Configuration not in FUEL_CELL_CONFIGURATIONS

    def _total_sls_thrust_lbf(self):
        n_engines = self.input['ENGINE']['N_ENGINES']
        return sls_thrust_per_engine_lbf(self.aircraft, self.input) * n_engines

    def FuelSystemMass(self):
        """1.07 * capacity^0.58 * N_eng^0.43 * M_max^0.34 [lb], capacity = maximum fuel mass [lb]."""
        if not self._has_gas_turbine():
            return 0.0
        capacity = self.input['FUEL']['MAX_CAPACITY']
        n_eng = engine_count_factor(self.input['ENGINE']['N_ENGINES'])
        return 1.07 * capacity**0.58 * n_eng**0.43 * max_mach(self.aircraft, self.input)**0.34

    def UnusableFuelMass(self):
        """(11.5 * N_eng * (T/N_eng)^0.2 + 0.07 * S + 1.6 * n_tanks * capacity^0.28) * rho/6.7
        [lb], with T the total SLS thrust [lbf], S the wing area [ft^2] and rho the fuel
        density [lb/US gal] (6.7 for Jet A)."""
        if not self._has_gas_turbine():
            return 0.0
        fuel = self.input['FUEL']
        n_eng = engine_count_factor(self.input['ENGINE']['N_ENGINES'])
        thrust_factor = self._total_sls_thrust_lbf() / n_eng
        density_ratio = fuel.get('DENSITY', 6.7) / 6.7
        return ((11.5 * n_eng * thrust_factor**0.2
                 + 0.07 * wing_area_ft2(self.aircraft, self.input)
                 + 1.6 * fuel['NUM_TANKS'] * fuel['MAX_CAPACITY']**0.28) * density_ratio)

    def EngineOilMass(self):
        """0.082 * N_eng * (T/N_eng)^0.65 [lb]."""
        if not self._has_gas_turbine():
            return 0.0
        n_eng = engine_count_factor(self.input['ENGINE']['N_ENGINES'])
        return 0.082 * n_eng * (self._total_sls_thrust_lbf() / n_eng)**0.65

    def StarterMass(self):
        """11.0 * N_eng * M^0.32 * D_nacelle^1.6 [lb] (nacelle diameter [ft])."""
        if not self._has_gas_turbine():
            return 0.0
        n_engines = self.input['ENGINE']['N_ENGINES']
        n_eng = engine_count_factor(n_engines)
        d_nacelle = self.input['NACELLE']['AVG_DIAM']
        if n_engines > 4:
            d_nacelle = 0.5 * d_nacelle * n_engines**0.5
        return 11.0 * n_eng * max_mach(self.aircraft, self.input)**0.32 * d_nacelle**1.6

    def EngineControlsMass(self):
        """0.26 * N_eng * (T/N_eng)^0.5 [lb]."""
        if not self._has_gas_turbine():
            return 0.0
        n_eng = engine_count_factor(self.input['ENGINE']['N_ENGINES'])
        return 0.26 * n_eng * (self._total_sls_thrust_lbf() / n_eng)**0.5

    def ThrustReverserMass(self):
        """0.034 * T * n_nacelles [lb], T the SLS thrust per engine [lbf]; zero unless the
        input ``FLOPSInput['ENGINE']['THRUST_REVERSERS']`` is True."""
        if not self.input['ENGINE'].get('THRUST_REVERSERS', False):
            return 0.0
        n_engines = self.input['ENGINE']['N_ENGINES']
        nacelle_count = n_engines + (n_engines % 2) * 0.5
        return 0.034 * sls_thrust_per_engine_lbf(self.aircraft, self.input) * nacelle_count

    def PassengerServiceMass(self):
        """(5.164 * first + 3.846 * business + 2.529 * economy) * (R/M)^0.225 [lb], R the
        design range [nm]."""
        se = self.input['SYSTEM_EQUIPMENT']
        seats = (5.164 * se['N_FIRST_CLASS'] + 3.846 * se['N_BUSINESS_CLASS']
                 + 2.529 * se['N_TOURIST_CLASS'])
        return seats * (design_range_nm(self.aircraft) / max_mach(self.aircraft, self.input))**0.225

    def OperatingItemsMass(self):
        self.fuel_system_mass = self.FuelSystemMass()
        self.unusable_fuel_mass = self.UnusableFuelMass()
        self.engine_oil_mass = self.EngineOilMass()
        self.starter_mass = self.StarterMass()
        self.engine_controls_mass = self.EngineControlsMass()
        self.thrust_reverser_mass = self.ThrustReverserMass()
        self.passenger_service_mass = self.PassengerServiceMass()
        self.operating_items_mass = (
            self.fuel_system_mass + self.unusable_fuel_mass + self.engine_oil_mass
            + self.starter_mass + self.engine_controls_mass + self.thrust_reverser_mass
            + self.passenger_service_mass)
        return None
