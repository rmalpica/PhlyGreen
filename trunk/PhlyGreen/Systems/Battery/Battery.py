
import math

import numpy as np
from PhlyGreen.Systems.Battery import Cell_Models


class BatteryError(Exception):
    """Custom exception to be caught when the battery violates physical or model constraints."""
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


def find_parallel_cells(evaluate, n_guess, wto_ratio, n_limit):
    """Smallest feasible number of parallel cells P (the P-number search of the Class-II pack).

    Feasibility is assumed monotone in P. The search brackets the optimum and then bisects:

    1. bracket: ``n_max = n_guess`` and ``n_min = floor(n_max / 2)`` on the first call
       (``wto_ratio`` is None); otherwise ``n_max = ceil(n_guess * wto_ratio)`` and
       ``n_min = n_max - 1``, with ``n_guess`` the previous optimum;
    2. while ``n_min`` is feasible, move it to ``n_max`` and halve it;
    3. if no feasible ``n_max`` is known, double it until it is feasible, but not beyond
       ``n_limit``;
    4. bisect between the infeasible ``n_min`` and the feasible ``n_max``.

    Parameters
    ----------
    evaluate : callable
        ``evaluate(P) -> (feasible, error_code)``: flies the mission with P parallel cells.
    n_guess : int
        First guess (previous optimum).
    wto_ratio : float or None
        Ratio of the present take-off mass to the one of the previous optimum.
    n_limit : int
        Largest P the search may evaluate: the pack of ``n_limit`` strings is the heaviest
        acceptable one (the Class-II mission passes the take-off mass).

    Returns
    -------
    int
        The smallest feasible P.

    Raises
    ------
    BatteryError
        code ``PACK_HEAVIER_THAN_AIRCRAFT`` when P = ``n_limit`` (or a larger first guess) is
        infeasible: no acceptable pack flies the mission.
    """
    if wto_ratio is not None:
        n_max = math.ceil(n_guess * wto_ratio)
        n_min = n_max - 1
    else:
        n_max = n_guess
        n_min = math.floor(n_max / 2)

    # lower the minimum until it is infeasible; a feasible minimum becomes the maximum
    nmax_is_bounded = False
    while evaluate(n_min)[0]:
        n_max = n_min
        n_min = math.floor(n_min / 2)
        nmax_is_bounded = True

    # raise the maximum until it is feasible, up to the heaviest acceptable pack
    if not nmax_is_bounded:
        while True:
            feasible, code = evaluate(n_max)
            if feasible:
                break
            if n_max >= n_limit:
                raise BatteryError(
                    f"No acceptable pack flies the mission: P = {n_max} parallel cells is "
                    f"infeasible ({code}) and the limit is P = {n_limit}.",
                    code="PACK_HEAVIER_THAN_AIRCRAFT")
            n_min = n_max
            n_max = min(max(n_max * 2, 1), n_limit)

    # bisection between the infeasible n_min and the feasible n_max
    n = math.ceil((n_max + n_min) / 2)
    while True:
        feasible = evaluate(n)[0]
        if feasible and (n - n_min) == 1:
            return n
        if feasible:
            n_max = n
            n = math.floor((n_max + n_min) / 2)
        else:
            n_min = n
            n = math.ceil((n_max + n_min) / 2)


class Battery:
    """
    Battery electro-thermal model with safety checks.

    Handles:
    - Voltage model evaluated at cell level
    - SOC tracking through current integration
    - Max current enforcement
    - Pack configuration (series/parallel)
    - Thermal dynamics
    """
    def __init__(self, aircraft):
        self.aircraft = aircraft

        self.BatteryClass = None     # set by SetInput when a CellInput is supplied
        self.pack_Vmax = 800
        self._SOC_min = None
        self._it = 0         # integral of current [Ah], used to compute SOC
        self._i = None       # pack current [A]
        self._T = None       # cell temperature [K]
        self._cell_max_current = None
        self.mdot = 0        # cooling mass flow estimate from heat loss model

        # State of health relative to beginning of life (BOL); the defaults are BOL. See
        # set_state_of_health.
        self.capacity_fraction = 1.0   # C / C_BOL [-]
        self.resistance_factor = 1.0   # R / R_BOL [-]
        self._bol = None               # BOL values of the parameters that degrade

    # -------------------------------------------------------------------------
    #                           CORE PROPERTIES
    # -------------------------------------------------------------------------

    @property
    def i(self):
        return self._i

    @i.setter
    def i(self, value):
        """Sets pack current and checks whether a physically valid value is available."""
        self._i = value
        # print(f"cell_Iout{value}")
        if value is None:
            raise BatteryError(
                "No real valued solution found for battery current.\nBattery underpowered.",
                code = "BATT_UNDERPOWERED"
            )

    @property
    def it(self):
        return self._it

    @it.setter
    def it(self, value):
        """
        Sets the current integral.
        Converts total pack discharge to cell discharge and checks SOC boundaries.
        """
        self._it = value
        # print(f"it{self._it}")
        _soc = 1 - value / (self.cell_capacity * self.P_number)
        _socmax = 1
        if not (self.SOC_min <= _soc <= _socmax):
            raise BatteryError(
                f"Fail_Condition_1\nSOC outside of allowed range:\nSOC:{_soc:.17f} Range: {self.SOC_min:.17f} ~ {_socmax:.17f}",
                code = "SOC_OUTSIDE_LIMITS"
            )

    @property
    def T(self):
        if self._T is None:
            raise BatteryError("Fail_Condition_2\nBattery temperature unset.")
        return self._T

    @T.setter
    def T(self, value):
        """Ensures temperature remains physically valid."""
        self._T = value
        # print(f"cell_T{value}")
        if value < 0:
            raise BatteryError(
                f"Fail_Condition_3\nBattery temperature must be positive:\nTemperature: {value}",
                code = "NEG_BATT_TEMP"
            )

    @property
    def SOC_min(self):
        """Ensures SOC_min is between 0 and 1."""
        if self._SOC_min is None:
            raise BatteryError("Fail_Condition_4\nMinimum SOC unset.")
        return self._SOC_min

    @SOC_min.setter
    def SOC_min(self, value):
        self._SOC_min = value
        if not (0 <= value <= 1):
            raise BatteryError(
                f"Fail_Condition_5\nMinimum SOC outside of allowed range:\nSOC:{value} Range: 0 ~ 1"
            )

    @property
    def cell_max_current(self):
        if self._cell_max_current is None:
            raise ValueError("Fail_Condition_10\nMax current unset.")
        return self._cell_max_current

    @cell_max_current.setter
    def cell_max_current(self, value):
        """
        Ensures the chosen max current does not produce invalid cell voltage.
        This is required because cells deviate from ideal behavior near limits.
        """
        self._cell_max_current = value
        v = self._voltageModel(0, value)
        # if not self.cell_Vmax >= v >= self.cell_Vmin:
        if not v >= self.cell_Vmin:
            raise ValueError(
                f"Reevaluate the max cell current of the chosen model.({value}A)\n",
                f"The input value results in an invalid voltage: {v}V\n",
                f"Limits are {self.cell_Vmin}V ~ {self.cell_Vmax}V"
            )

    # -------------------------------------------------------------------------
    #                             CELL VOLTAGE OUTPUTS
    # -------------------------------------------------------------------------

    @property
    def cell_Vout(self) -> float:
        """
        Actual instantaneous cell voltage.
        Should never drop below the minimum safe voltage.
        """
        _value = self._voltageModel(self.cell_it, self.cell_i)
        # print(f"cell_Vout{_value}")
        if not (self.cell_Vmin <= _value):# <= self.cell_Vmax):
            raise BatteryError(
                f"Fail_Condition_6\nCell voltage outside of allowed range:\nVoltage:{_value} Range: {self.cell_Vmin} ~ {self.cell_Vmax}\nPnum is {self.P_number}",
                code = "VOLTAGE_OUTSIDE_LIMITS"
            )
        return _value

    @property
    def cell_Voc(self) -> float:
        """Open-circuit voltage at the current SOC."""
        return self._voltageModel(self.cell_it, 0)

    @property
    def Vout(self) -> float:
        """Pack-level voltage from series connection."""
        _value = self.cell_Vout * self.S_number
        # if not ( _value <= self.pack_Vmax):
        #     raise BatteryError(
        #         f"Fail_Condition_7\nPack voltage too high:\nVoltage:{_value} Max: {self.pack_Vmax}"
        #     )
        return _value

    @property
    def Voc(self) -> float:
        """Open-circuit pack voltage."""
        return self.cell_Voc * self.S_number

    @property
    def cell_it(self) -> float:
        """Discharge per cell (Ah)."""
        return self.it / self.P_number

    @property
    def cell_i(self) -> float:
        """
        Cell-level current (A).
        For parallel strings, each cell sees pack current divided by P.
        """
        _value = self.i / self.P_number
        if _value > self.cell_max_current:
            raise BatteryError(
                f"Fail_Condition_8\nCell current outside of allowed range:\nCurrent:{_value} Range:- ~ {self.cell_max_current}",
                code = "CURR_OUTSIDE_LIMITS"
            )
        return _value

    @property
    def SOC(self) -> float:
        """Real-time State-Of-Charge computed from integrated current."""
        _value = 1 - self.cell_it / self.cell_capacity
        _socmax = 1
        # print(f"cell_SOC{_value}")
        if not (self.SOC_min <= _value <= _socmax):
            raise BatteryError(
                f"Fail_Condition_9\nSOC outside of allowed range:\nSOC:{_value!r} Range:{self.SOC_min!r} ~ {_socmax!r}",
                code = "SOC_OUTSIDE_LIMITS"
            )
        return _value
    
    # -------------------------------------------------------------------------
    #                      TEMPERATURE-CORRECTED MODEL PARAMETERS
    # -------------------------------------------------------------------------

    # Set all the discharge curve parameters to already be corrected with temperature

    @property
    def E0(self) -> float:
        "Voltage constant"
        return self.voltage_ctt + self.E_slope * (self.T - self.Tref)

    @property
    def Q(self) -> float:
        "Nominal capacity"
        return self.cell_capacity + self.Q_slope * (self.T - self.Tref)

    @property
    def K(self) -> float:
        "Polarization resistance (Arrhenius temperature correction)"
        return self.polarization_ctt * np.exp(self.K_arrhenius * (1 / self.T - 1 / self.Tref))

    @property
    def R(self) -> float:
        "Internal ohmic resistance (Arrhenius temperature correction)"
        return self.cell_resistance * np.exp(self.R_arrhenius * (1 / self.T - 1 / self.Tref))

    # -------------------------------------------------------------------------
    #                          ELECTRICAL CELL MODEL
    # -------------------------------------------------------------------------

    # Thermal electric model of the voltage

    def _voltageModel(self, it, i):
        """Model that determines the voltage from the present cell state.
           It receives i and it in order to be able to provide cell
           peak voltage and open circuit voltage values at any desired state
        Receives:
            - it - cell current integral, ie. charge spent so far
            - i  - current draw from the cell
        Returns:
            - V - cell voltage output
        """
        E0, R, K, Q = self.E0, self.R, self.K, self.Q
        A, B = self.exp_amplitude, self.exp_time_ctt

        V = E0 - (i + it) * K * (Q / (Q - it)) + A * np.exp(-B * it) - i * R
        # print('_voltage returns: ', V)
        return V

    # -------------------------------------------------------------------------
    #                           INPUT SETTING
    # -------------------------------------------------------------------------

    # Set inputs from chosen cell model 

    def SetInput(self):
        """
        This grabs the CellModel object from the aircraft class where a
        dictionary defines some inputs set by the user.
        Then according to the inputs it defines the battery model to use.
        The constants come from the cell_models.py module and are modified
        according to the user input.
        """

        bat_inputs = self.aircraft.CellInput
                # set the battery model class
        self.BatteryClass = bat_inputs['Class']


        if self.BatteryClass == 'II':
            self.SOC_min = bat_inputs['Minimum SOC']
            self.aircraft.mission.startT = bat_inputs['Initial temperature'] 
            self.aircraft.mission.T_battery_limit = bat_inputs['Max operative temperature'] 

        if self.BatteryClass == 'I':
            self.Ebat = bat_inputs['SpecificEnergy']*3600
            self.pbat = bat_inputs['SpecificPower']
            self.SOC_min = bat_inputs['Minimum SOC'] 
            self._bol = {'Ebat': self.Ebat, 'pbat': self.pbat}
            return

        if self.BatteryClass != 'II':
            raise Exception(f"Unrecognized model class: {self.BatteryClass}")

        if bat_inputs.get('Model') is None: # Fallback to a default model if none is given
            model = 'Finger-Cell-Thermal'
        else:
            model = bat_inputs['Model']



        # Get all the cell parameters
        cell = Cell_Models[model]
        self.Tref              = cell['Reference Temperature']     # in kelvin
        self.T = self.Tref
        self.exp_amplitude     = cell['Exp Amplitude']                  # in volts
        self.exp_time_ctt      = cell['Exp Time constant']              # in Ah^-1 
        self.cell_resistance   = cell['Internal Resistance']            # in ohms
        self.R_arrhenius       = cell['Resistance Arrhenius Constant']  # dimensionless
        self.polarization_ctt  = cell['Polarization Constant']          # in Volts over amp hour
        self.K_arrhenius       = cell['Polarization Arrhenius Constant']# dimensionless
        self.cell_capacity     = cell['Cell Capacity']                  # in Ah
        self.Q_slope           = cell['Capacity Thermal Slope']         # in Ah per kelvin
        self.voltage_ctt       = cell['Voltage Constant']               # in volts
        self.E_slope           = cell['Voltage Thermal Slope']          # in volts per kelvin
        self.cell_Vmax         = self.exp_amplitude + self.voltage_ctt  # in volts
        self.cell_Vmin         = cell['Cell Voltage Min']               # in volts
        self.cell_max_current  = cell['Cell Current Max']                  # dimensionless
        self.cell_mass         = cell['Cell Mass']                      # in kg
        self.cell_radius       = cell['Cell Radius']                    # in m
        self.cell_height       = cell['Cell Height']                    # in m
        self.Vnom              = cell['Cell Voltage Nominal']  # in volts
        self.cell_energy_nom   = self.Vnom * self.cell_capacity

        # Verify that the voltages are correctly set
        if not (self.cell_Vmax > self.cell_Vmin):
            raise ValueError(
                "Fail_Condition_11\nIllegal cell voltages: Vmax must be greater than Vmin"
            )

        # Modify the cell according to the user specified energy and power densities
        # Modify the capacity of the cell
        # Optional keys: CellConfig.to_dict() omits the fields left at None.
        specific_energy = bat_inputs.get("SpecificEnergy")
        specific_power = bat_inputs.get("SpecificPower")
        if specific_energy is not None:
            ecell = specific_energy * self.cell_mass                # cell energy in Wh
            capcell = ecell / self.Vnom                             # cell charge in Ah
            eratio = capcell / self.cell_capacity # ratio between model charge and new charge
            #print(f"old{self.cell_capacity}    new{capcell}")

            self.cell_capacity = capcell
            self.cell_energy_nom = ecell
            self.Q_slope *= eratio  # the slope is a fraction of the capacity, so it scales with the ratio of capacities
            self.exp_time_ctt /= eratio  # divides by the ratio because its the INVERSE of the exponential zone charge

            # Scale the specific power accordingly, unless a fixed one is requested. The
            # Arrhenius constants are activation temperatures [K]: they set the temperature
            # dependence of the resistances, not their size, so they are not rescaled.
            if specific_power is None:
                self.polarization_ctt /= eratio
                self.cell_resistance /= eratio
                self.cell_max_current *= eratio


        # Modify the internal resistance and current limit to adjust power
        if specific_power is not None:
            pcell = specific_power * self.cell_mass               # cell power in W
            pcellnow = self.cell_max_current * self._voltageModel(0, self.cell_max_current)
            pratio = pcell / pcellnow
            #print(f"Current ratio:{pratio}")
            #print(f"peak power old:{pcellnow}")

            # Dividing the internal resistance by a ratio increases
            # the maximum deliverable power by the same ratio (the Arrhenius activation
            # temperatures are not rescaled, see above)
            self.polarization_ctt /= pratio
            self.cell_resistance /= pratio

            # Note: the cell max current needs to be the last thing
            # to be calculated because its setter verifies its
            # validity against the cell properties
            self.cell_max_current *= pratio
        # print(f"peak power new:{self.cell_max_current*self._voltageModel(0, self.cell_max_current)}")


        # Number of cells in series to achieve desired voltage.
        # Higher voltage is preferred as it minimizes losses
        # due to lower current being needed.
        if bat_inputs.get("Pack Voltage") is not None:
            self.pack_Vmax = bat_inputs["Pack Voltage"]
        else:
            self.pack_Vmax = 740
        self.S_number = np.floor(self.pack_Vmax / self.cell_Vmax)

        self.cell_area_surface = 2*np.pi*self.cell_radius*self.cell_height
        self.module_area_section = (2*self.cell_radius)**2-np.pi*self.cell_radius**2

        self.Rith = 3.3*(self.cell_radius/0.022)**2 # probably need a citation for this one
        self.Cth = 1000 * self.cell_mass

        self._bol = {'cell_capacity': self.cell_capacity, 'cell_energy_nom': self.cell_energy_nom,
                     'Q_slope': self.Q_slope, 'exp_time_ctt': self.exp_time_ctt,
                     'cell_resistance': self.cell_resistance,
                     'polarization_ctt': self.polarization_ctt}

    def set_state_of_health(self, capacity_fraction=1.0, resistance_factor=1.0):
        """Set the degradation state of the battery, relative to beginning of life (BOL).

        ``capacity_fraction`` = C / C_BOL and ``resistance_factor`` = R / R_BOL are the two
        outputs of the semi-empirical ageing models (e.g. Schmalstieg et al., J. Power Sources
        2014), which scale the capacities and the resistances of the cell model.

        - Class II: the cell capacity (and the charge-proportional terms of the Shepherd model,
          as in ``SetInput``) is scaled by ``capacity_fraction``; the ohmic and the polarization
          resistances by ``resistance_factor``. The cell model then enforces the SOC, voltage
          and current limits of the aged pack.
        - Class I: the specific energy is scaled by ``capacity_fraction`` and the specific power
          divided by ``resistance_factor`` (to first order the deliverable power is inversely
          proportional to the internal resistance).
        - The Class-I battery of 'FuelCellBattery' (EnergyInput specific energy/power, no
          CellInput) reads the two factors in ``Weight.FuelCellBattery``.

        Set it before the design to size the pack at end of life; set it on a sized copy to fly
        an aged pack. The pack mass per cell does not change.
        """
        if not 0.0 < capacity_fraction <= 1.0:
            raise ValueError(f"Battery capacity fraction must be in (0, 1], got {capacity_fraction!r}")
        if resistance_factor <= 0.0:
            raise ValueError(f"Battery resistance factor must be > 0, got {resistance_factor!r}")
        self.capacity_fraction = float(capacity_fraction)
        self.resistance_factor = float(resistance_factor)
        bol = self._bol
        if self.BatteryClass == 'I':
            self.Ebat = bol['Ebat'] * self.capacity_fraction
            self.pbat = bol['pbat'] / self.resistance_factor
        elif self.BatteryClass == 'II':
            self.cell_capacity = bol['cell_capacity'] * self.capacity_fraction
            self.cell_energy_nom = bol['cell_energy_nom'] * self.capacity_fraction
            self.Q_slope = bol['Q_slope'] * self.capacity_fraction
            self.exp_time_ctt = bol['exp_time_ctt'] / self.capacity_fraction
            self.cell_resistance = bol['cell_resistance'] * self.resistance_factor
            self.polarization_ctt = bol['polarization_ctt'] * self.resistance_factor

    # -------------------------------------------------------------------------
    #                     PACK CONFIGURATION (SxP)
    # -------------------------------------------------------------------------

    # determine battery configuration
    # must receive the number of cells in parallel

    def Configure(self, parallel_cells):
        """
        Defines the parallel count (P_number) and computes
        pack-level properties: mass, volume, max power, nominal energy.

        Parameters
        ----------
        parallel_cells : int
            Number of cells in parallel (P_number).

        """
        self.P_number = parallel_cells
        self.cells_total = self.P_number * self.S_number

        # physical characteristics of the whole pack:
        stack_length = self.cell_radius * np.ceil(self.S_number / 2)
        # stack_width = self.cell_radius * (2 + np.sqrt(3))
        stack_width = self.cell_radius * 2
        self.pack_volume = self.cell_height * stack_width * stack_length
        self.pack_weight = self.cell_mass * self.cells_total
        if self.pack_weight > 3000000000000000:
            raise BatteryError("OVERWEIGHT! SOMETHING IS VERY WRONG BECAUSE BATTERY IS NOT CONVERGING")
        # nominal pack values
        self.pack_energy = self.cell_energy_nom * self.cells_total
        self.pack_power_max = (
            self.cell_max_current * self._voltageModel(0, self.cell_max_current) * self.cells_total
        )
        self.pack_charge = self.cell_capacity * self.P_number

        # self.pack_config = f"S{self.S_number} P{self.P_number}"

    def Power_2_current(self, P):
        """Calculates the current output from the battery. The calculations are for a single
            cell, as that is what the model is made for. The output is the current for the entire
            battery pack however. The power is simply divided by the total number of cells, as
            every cell delivers equal power regardless of the configuration of the battery.
        Receives:
            P - power demanded from the battery
        Returns:
            I_out - current output from the battery
        """

        if P == 0:  # skips all the math if power is zero
            return 0

        # V = E0 - I*R - I*K*(Q/(Q-it)) - it*K*(Q/(Q-it)) + A*exp(-B * it)
        # V = E0 - I*R - I*Qr - it*Qr + ee <- with substitutions to make shorter
        # P = V*I = E0*I - I^2*R - I^2*Qr - I*it*Qr + I*ee 
        # P = I^2 *(-R-Qr) + I *(E0+ee-it*Qr)
        # quadratic solve: 
        # a*I^2 + b*I - P = 0
        
        E0, R, K, Q = self.E0, self.R, self.K, self.Q
        A, B = self.exp_amplitude, self.exp_time_ctt
        it = self.cell_it
        P = P / self.cells_total  # all cells deliver the same power

        Qr = K * Q / (Q - it)
        ee = A * np.exp(-B * it)
        a = -R - Qr
        b = E0 + ee - it * Qr
        c = -P
        Disc = b**2 - 4 * a * c  # quadratic formula discriminant

        if Disc < 0:
            I_out = None
            return I_out

        else:
            I_out = (-b + np.sqrt(Disc)) / (2 * a)  # just the quadratic formula

        return I_out * self.P_number

    def heatLoss(self, Ta, rho):
        """ Simple differential equation describing a
            simplified lumped element thermal model of the cells
        Receives:
            - Ta   - temperature of the ambient cooling air
            - rho  - density of the ambient air
        Returns:
            - dTdt - battery temperature derivative
            - P    - dissipated waste power per cell
        """
        Ta = max(Ta,273.15)
        # print('T ambient: ', Ta)

        V, Voc = self.cell_Vout, self.cell_Voc
        i = self.cell_i
        T, dEdT = self.T, self.E_slope
        # print('Battery temperature: ', T-273.15)
        Rith = self.Rith
        Cth = self.Cth
        # Bernardi heat for a discharge current i > 0: irreversible (Voc - V) i minus the
        # reversible (entropic) term i T dE/dT
        P = (Voc - V) * i - dEdT * i * T
        # cooling-air flow proportional to the heat; no flow when the cell absorbs heat (the
        # reversible term can make P < 0 at low current)
        self.mdot = max(0.0001*P, 0.0)
        h = max(
            (  # taken from http://dx.doi.org/10.1016/j.jpowsour.2013.10.052
                30* ( ((self.mdot) / (self.module_area_section * rho)) / 5) ** 0.8
            ),
            2)

        if (self.phi > 0.) & (T < 273.15 + self.aircraft.mission.T_battery_limit):
            h = 0.            


        # print(self.mdot)

        if h == 0:  # avoid division by 0
            dTdt = P / Cth
        else:
            Rth = 1 / (h * self.cell_area_surface) + Rith
            dTdt = P / Cth + (Ta - T) / (Rth * Cth)
        # print(f"h: {h}   R:{Rth}     surface:{self.cell_area_surface}    crosssec:{self.module_area_section}")
        return dTdt, P

    def thermal_degradation_analysis(self, charge_c_rate=None, discharge_c_rate=None,
                                     soc_start=None, flight_temp_k=None, **overrides):
        """Estimate ground fast-charge cooling load and battery cycle life (opt-in, Class II).

        *Post-design* analysis — never part of the take-off-weight sizing, so it cannot change
        a baseline design. Reads optional parameters from ``CellInput`` (typed via
        :class:`~PhlyGreen.config.CellConfig`): ``Charge C-Rate``, ``Discharge C-Rate``,
        ``Maximum SOC``, ``EoL Capacity``, ``Coolant Temperature`` [C] and
        ``Ground Cooling Coefficient``.

        The cycle is the mission last flown by the sized pack (``Mission.integral_solution``
        plus the ground legs, ``Mission.battery_end_state``):

        - depth of discharge: the pack starts the taxi-out full, so the DoD is one minus the
          lowest SOC reached, taxi-in included;
        - flight temperature: the time average of the cell temperature from the start of the
          climb to the landing;
        - recharge: from the SOC and the cell temperature at the end of the taxi-in.

        An explicit ``soc_start`` sets the recharge start and the DoD ``Maximum SOC - soc_start``;
        an explicit ``flight_temp_k`` sets the flight temperature. Without a flown mission the
        defaults are ``SOC_min`` and the present ``self.T``.

        Returns the dict from
        :meth:`~PhlyGreen.Systems.Battery.degradation.BatteryAgeingModel.analyze`
        (``recharge_time_min``, ``T_start``, ``T_final``, ``peak_cooling_w``,
        ``peak_pulldown_w``, ``peak_heat_w``, ``dod``, ``soc_start``, ``T_flight``,
        ``n_cycles``) and caches it on ``self.ageing``.
        """
        if getattr(self, 'BatteryClass', None) != 'II':
            raise BatteryError(
                "thermal_degradation_analysis requires a Class-II battery.",
                code="REQUIRES_CLASS_II")
        ci = getattr(self.aircraft, 'CellInput', None) or {}
        charge_c_rate = charge_c_rate if charge_c_rate is not None else ci.get('Charge C-Rate')
        if not charge_c_rate or charge_c_rate <= 0:
            raise BatteryError(
                "thermal_degradation_analysis needs a positive 'Charge C-Rate' "
                "(CellConfig.charge_c_rate) or a charge_c_rate=... argument.",
                code="NO_CHARGE_C_RATE")

        soc_max = ci.get('Maximum SOC', 1.0)

        # The cycle flown by the sized pack: spent charge it [A s] and cell temperature T [K]
        # from the start of the climb to the landing, and their values after the taxi-in.
        mission = self.aircraft.mission
        flown = getattr(mission, 'battery_end_state', None) is not None and bool(
            getattr(mission, 'integral_solution', None))
        if flown:
            t = np.concatenate([sol.t for sol in mission.integral_solution])
            it_flight = np.concatenate([sol.y[3] for sol in mission.integral_solution])
            T_flight = np.concatenate([sol.y[4] for sol in mission.integral_solution])
            it_end, T_end = mission.battery_end_state
            pack_charge_As = self.cell_capacity * self.P_number * 3600
            soc_end = 1 - it_end / pack_charge_As
            soc_lowest = 1 - max(np.max(it_flight), it_end) / pack_charge_As
            # trapezoidal time average (segment joins repeat a time point: zero weight)
            T_mean = np.sum(0.5 * (T_flight[1:] + T_flight[:-1]) * np.diff(t)) / (t[-1] - t[0])

        if soc_start is not None:
            dod = soc_max - soc_start
        elif flown:
            soc_start = soc_end
            dod = 1 - soc_lowest        # the pack starts the taxi-out full
        else:
            soc_start = self.SOC_min
            dod = soc_max - soc_start

        if flight_temp_k is None:
            flight_temp_k = T_mean if flown else self.T
        charge_start_temperature = T_end if flown else self.T

        from .degradation import BatteryAgeingModel
        model = BatteryAgeingModel(
            self, charge_c_rate,
            discharge_c_rate=(discharge_c_rate if discharge_c_rate is not None
                              else ci.get('Discharge C-Rate')),
            soc_start=soc_start,
            soc_max=soc_max,
            eol_capacity=ci.get('EoL Capacity', 0.8),
            coolant_temperature=ci.get('Coolant Temperature', 20.0) + 273.15,
            ground_h=ci.get('Ground Cooling Coefficient', 150.0),
            dod=dod,
            flight_temperature=flight_temp_k,
            charge_start_temperature=charge_start_temperature,
            **overrides)
        result = model.analyze()
        self.ageing = result
        return result