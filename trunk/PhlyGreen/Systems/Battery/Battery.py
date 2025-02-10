import math
import numpy as np
from PhlyGreen.Systems.Battery import Cell_Models


class BatteryError(Exception):
    """Custom exception to be caught when the battery is invalid"""


class Battery:
    def __init__(self, aircraft):
        self.aircraft = aircraft

        # this range of voltages should be defined in the model of the motor controller,
        # for now its hardcoded. Create voltage controller in the future? Integrate this
        # into the powerplant spec?
        self.controller_Vmax = 740
        self.controller_Vmin = 420 
        self._SOC_min = None
        self._it = 0
        self._i = None
        self._T = 300

    @property
    def i(self):
        return self._i

    @i.setter
    def i(self, value):
        self._i = value
        if value is None:
            raise BatteryError(
                "No real valued solution found for battery current.\nBattery underpowered."
            )

    @property
    def it(self):
        return self._it

    @it.setter
    def it(self, value):
        self._it = value
        _soc = 1 - value / (self.cell_capacity * self.P_number)
        _socmax = 1
        if not (self.SOC_min <= _soc <= _socmax):
            raise BatteryError(
                f"Fail_Condition_1\nSOC outside of allowed range:\nSOC:{_soc:.17f} Range: {self.SOC_min:.17f} ~ {_socmax:.17f}"
            )

    @property
    def T(self):
        if self._T is None:
            raise BatteryError("Fail_Condition_2\nBattery temperature unset.")
        return self._T

    @T.setter
    def T(self, value):
        self._T = value
        if value < 0:
            raise BatteryError(
                f"Fail_Condition_3\nBattery temperature must be positive:\nTemperature: {value}"
            )

    @property
    def SOC_min(self):
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
    def cell_Vout(self) -> float:
        _value = self._voltageModel(self.cell_it, self.cell_i)
        if not (self.cell_Vmin <= _value):# <= self.cell_Vmax):
            raise BatteryError(
                f"Fail_Condition_6\nCell voltage outside of allowed range:\nVoltage:{_value} Range: {self.cell_Vmin} ~ {self.cell_Vmax}"
            )
        return _value

    @property
    def cell_Voc(self) -> float:
        return self._voltageModel(self.cell_it, 0)

    @property
    def Vout(self) -> float:
        _value = self.cell_Vout * self.S_number
        if not (self.controller_Vmin <= _value):# <= self.controller_Vmax):
            raise BatteryError(
                f"Fail_Condition_7\nPack voltage outside of allowed range:\nVoltage:{_value} Range: {self.controller_Vmin} ~ {self.controller_Vmax}"
            )
        return _value

    @property
    def Voc(self) -> float:
        return self.cell_Voc * self.S_number

    @property
    def cell_it(self) -> float:
        return self.it / self.P_number

    @property
    def cell_i(self) -> float:
        _value = self.i / self.P_number
        if _value > self.cell_max_current:
            raise BatteryError(
                f"Fail_Condition_8\nCell current outside of allowed range:\nCurrent:{_value} Range:- ~ {self.cell_max_current}"
            )
        return _value

    @property
    def SOC(self) -> float:
        _value = 1 - self.cell_it / self.cell_capacity
        _socmax = 1
        if not (self.SOC_min <= _value <= _socmax):
            raise BatteryError(
                f"Fail_Condition_9\nSOC outside of allowed range:\nSOC:{_value!r} Range:{self.SOC_min!r} ~ {_socmax!r}"
            )
        return _value
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
        "Polarization constant"
        return self.polarization_ctt * math.exp(self.K_arrhenius * (1 / self.T - 1 / self.Tref))

    @property
    def R(self) -> float:
        "Internal resistance"
        return self.cell_resistance * math.exp(self.R_arrhenius * (1 / self.T - 1 / self.Tref))

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
        return V

    # Set inputs from cell model chosen
    def SetInput(self):
        """
        This gathers all the battery parameters from the cell_models.py file for the chosen battery.
        The chosen battery is read from the aircraft class and is defined by the user elsewhere
        the parameters are all input and some extra ones are calculated right away for later convenience
        """
        cell = Cell_Models[self.aircraft.CellModel]
        # Get all parameters of the cell
        self.Tref              = cell['Reference Temperature']     # in kelvin
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
        self.cell_rate         = cell['Cell C rating']                  # dimensionless
        self.cell_max_current  = self.cell_rate * self.cell_capacity    # in amperes
        self.cell_mass         = cell['Cell Mass']                      # in kg
        self.cell_radius       = cell['Cell Radius']                    # in m
        self.cell_height       = cell['Cell Height']                    # in m
        self.cell_energy_nom   = cell['Cell Nominal Energy']            # in Wh


        if not (self.cell_Vmax > self.cell_Vmin):
            raise ValueError(
                "Fail_Condition_10\nIllegal cell voltages: Vmax must be greater than Vmin"
            )
        # Number of cells in series to achieve desired voltage.
        # max voltage is preferred as it minimizes losses
        # due to lower current being needed.
        self.S_number = math.floor(
            self.controller_Vmax / self.cell_Vmax
        )

    # determine battery configuration
    # must receive the number of cells in parallel
    def Configure(self, parallel_cells):
        """WIP
            Configures the battery for the chosen P number

        Receives:
            - parallel_cells - the chosen P number
        """
        self.P_number = parallel_cells
        self.cells_total = self.P_number * self.S_number

        # physical characteristics of the whole pack:
        stack_length = self.cell_radius * math.ceil(self.S_number / 2)
        # stack_width = self.cell_radius * (2 + np.sqrt(3))
        stack_width = self.cell_radius * 2
        self.pack_volume = self.cell_height * stack_width * stack_length
        self.pack_weight = self.cell_mass * self.cells_total

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
            I_out = (-b + math.sqrt(Disc)) / (2 * a)  # just the quadratic formula

        return I_out * self.P_number

    def heatLoss(self, Ta, rho):
        """WIP Simple differential equation describing a
            simplified lumped element thermal model of the cells
        Receives:
            - Ta   - temperature of the ambient cooling air
            - rho  - density of the ambient air
        Returns:
            - dTdt - battery temperature derivative
            - P    - dissipated waste power per cell
        """
        V, Voc = self.cell_Vout, self.cell_Voc
        i = self.cell_i
        T, dEdT = self.T, self.E_slope

        P = (Voc - V) * i + dEdT * i * T
        area_surface = 0.4
        area_section = 0.05
        mdot = 5
        h = ( # taken from http://dx.doi.org/10.1016/j.jpowsour.2013.10.052
            30 * ((area_section * mdot / rho) / 5) ** 0.8
        )
        Rth = 1 / (h * area_surface)
        Cth = 1200 * self.cell_mass
        dTdt = P / Cth + (Ta - T) / (Rth * Cth)
        return dTdt, P
