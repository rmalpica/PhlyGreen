import numpy as np
import warnings
from scipy.optimize import brentq, minimize_scalar

# --- IMPORT MANAGEMENT ---
try:
    from PhlyGreen.Systems.FuelCell.FC_Models import FC_Database
except ImportError:
    try:
        from .FC_Models import FC_Database
    except ImportError:
        FC_Database = {}
        warnings.warn("CRITICAL: FC_Models not found. A fallback dictionary will be used if needed.")

try:
    import PhlyGreen.Utilities.Atmosphere as ISA
except ImportError:
    ISA = None

class FuelCellError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code

class FuelCell:
    """
    Fuel Cell System (FCS) - Physics-Based Model (Massaro et al. / Kulikovsky).
    Sizing Margin: Optimized for TO Peak (AIAA 2025 Compliant).
    Solver: Hybrid (Brentq + Grid Search Fallback).
    """

    # --- PHYSICAL CONSTANTS ---
    FARADAY_CONST = 96485.33     # [C/mol]
    CP_AIR = 1004.0              # [J/(kg*K)] Air specific heat
    MOLAR_MASS_H2 = 0.002016     # [kg/mol] Molar mass of Hydrogen
    DELTA_H_REACT = 286000.0     # [J/mol] Enthalpy of reaction, liquid-water product (HHV)
    # Low-temperature PEM (T_op = 80 C) produces liquid water, so the cell efficiency and the fuel
    # chemical energy are referenced to the higher heating value (HHV), consistent with the HHV
    # thermoneutral voltage (DELTA_H_REACT / 2F = 1.482 V) used for the stack heat.
    HHV_H2 = DELTA_H_REACT / MOLAR_MASS_H2   # [J/kg] = 141.87e6, Higher Heating Value of Hydrogen
    # Enthalpy of reaction with VAPOUR product water (LHV basis) [J/mol]; the difference is the
    # latent heat of the product water.
    DELTA_H_REACT_LHV = 241800.0
    # Cathode-exhaust expansion: ideal-gas molar heat capacities near the stack temperature
    # [J/(mol K)] and molar masses [kg/mol] of its species (model constants).
    CP_MOLAR = {'N2': 29.12, 'O2': 29.38, 'H2O': 33.58}
    MOLAR_MASS = {'N2': 28.013e-3, 'O2': 31.999e-3, 'H2O': 18.015e-3}
    R_GAS = 8.314462618         # [J/(mol K)]
    # The heat rejected to the COOLANT depends on the phase in which the product water leaves
    # the stack: water that leaves as vapour with the cathode exhaust carries its latent heat
    # away, so it is not rejected by the coolant. With x_v the vaporised fraction,
    #   Q_coolant = I_cell * N_cells * [ (DH_HHV - x_v (DH_HHV - DH_LHV)) / 2F - V_cell ]
    # x_v = 0 -> thermo-neutral voltage 1.48 V (all liquid); x_v = 1 -> 1.25 V (all vapour).
    # The hydrogen consumption (and the chemical power on the HHV basis) does not depend on x_v.

    def __init__(self, aircraft):
        self.aircraft = aircraft
        self._Weight = 0.0
        self.Sizing_Done = False

        # General and sizing parameters
        self.model_name = None
        self.V_cell_design = None
        self.i_max_density = None
        self.Stack_PD = None
        self.BoP_Mass_Ratio = None
        self.V_stack = None          # nominal stack (bus) design voltage [V]

        # --- KULIKOVSKY MODEL PLACEHOLDERS ---
        self.Voc = None
        self.b_tafel = None
        self.R_ohm = None
        self.i_star = None
        self.j_lim = None   
        self.B_conc = None  
        self.c_h_ref = None
        self.c_ref = None
        self.sigma_t = None
        self.l_t = None
        self.D_b = None
        self.l_b = None
        self.D_ccl = None
        
        # Operational and Auxiliary Parameters
        self.Target_Press = None 
        self.T_op = None
        self.Fixed_Aux_Load = 0.015
        self.comp_eta = 0.75
        self.turb_eta = 0.70
        self.stoich = 2.0
        # Fraction of the product water leaving the stack as vapour (see the class note);
        # computed from the cathode-exhaust saturation in SetInput unless given as input.
        self.x_vapour = 0.0
        self.inlet_rh = 0.0       # cathode inlet relative humidity at T_op set by a humidifier [-]
        self.ambient_rh = 0.0     # relative humidity of the ambient air (weather) [-]
        self.x_vapour_spec = 'auto'   # 'auto' or a fixed product-water vapour fraction
        # Constant electrical auxiliary load [W] of the Class-II thermal-management system
        # (coolant pump). Added to the electrical demand at every operating point and to the
        # stack rating, so the pump's hydrogen consumption is flown and the stack is sized for
        # it. Set by the weight loop; 0 for the Class-I TMS (no effect).
        self.P_aux_tms = 0.0
        # Hydrogen and cathode-air mass flows [kg/s] at the last ComputePRatio call.
        self.mdot_h2 = 0.0
        self.mdot_air = 0.0

        # FUNDAMENTAL GEOMETRIC AND THERMAL OUTPUTS
        self.N_cells = 0  
        self.A_cell_reale = 0.0  
        self.P_fc_rated = 0.0  
        self.Q_thermal = 0.0  
        
        # --- SUMMARY OUTPUTS (last ComputePRatio operating point) ---
        self.P_gross_last = 0.0
        self.P_comp_net_last = 0.0
        self.P_turb_last = 0.0
        self.i_op_last = 0.0      # operating current density [A/cm^2]
        self.v_cell_last = 0.0    # operating cell voltage [V]
        self.eta_fcs_last = 0.0   # net fuel-cell-system efficiency (electrical/chemical) [-]

        # --- ADEQUACY TRACKING (worst-case power-limit over the last flown mission) ---
        # Populated by ComputePRatio at every operating point and read by report_sizing().
        # Reset whenever the stack is (re)sized in _size_stack, so they always describe the
        # final, flown stack.
        self._worst_load_ratio = 0.0     # max over the mission of (required / available) net power
        self._worst_alt = None           # altitude [m] of the worst-case point
        self._worst_P_req = 0.0          # required propulsive power [W] at the worst-case point
        self._power_limited = False      # True if any point exceeded the stack's deliverable power

        # --- STATE OF HEALTH (degradation) ---
        # Relative to the beginning-of-life (BOL) parameters of FC_Database; the defaults are BOL.
        # Set before the design to size the stack at end of life, or on a sized copy to fly a
        # degraded stack (see set_state_of_health).
        self.voltage_loss = 0.0              # uniform cell-voltage loss [V]
        self.ohmic_resistance_factor = 1.0   # R_ohm / R_ohm,BOL [-] (membrane / contact ageing)
        self.exchange_current_factor = 1.0   # i_star / i_star,BOL [-] (catalyst-area loss: < 1)
        self.R_ohm_bol = None
        self.i_star_bol = None

        self.EtaPM = None
        self.EtaEM = None
        self.EtaGB = None


    def SetInput(self):
        """Loads FC parameters strictly from the aircraft dictionary and FC_Database (Fail-Fast)."""
        inp = getattr(self.aircraft, 'EnergyInput', None)
        
        # 1. Fail-Fast for EnergyInput dictionary
        if inp is None:
            raise FuelCellError("CRITICAL ERROR: 'EnergyInput' dictionary is missing in the aircraft!")

        # 2. Fail-Fast for user-defined notebook inputs
        user_required_keys = [
            'Model', 'i Rated', 'V Cell Design', 'Stack Power Density', 
            'BoP Mass Ratio', 'Eta PMAD', 'Eta Electric Motor', 'Eta Gearbox'
        ]
        
        for key in user_required_keys:
            if key not in inp:
                raise FuelCellError(f"CRITICAL ERROR: Missing '{key}' in the user's EnergyInput dictionary.")

        self.model_name = inp['Model']
        # Initial value only: _size_stack sets the design current density from the design
        # cell voltage, and falls back to this value only if no current density reaches it.
        self.i_max_density = inp['i Rated']
        self.V_cell_design = inp['V Cell Design']
        self.Stack_PD = inp['Stack Power Density']
        self.BoP_Mass_Ratio = inp['BoP Mass Ratio']
        self.EtaPM = inp['Eta PMAD']
        self.EtaEM = inp['Eta Electric Motor']
        self.EtaGB = inp['Eta Gearbox']
        # Propeller (propulsive) efficiency: shaft -> thrust. Used both to convert the required
        # thrust power into electrical demand in ComputePRatio and to size the stack rating in
        # _size_stack, so the rating and the flown mission use the same downstream efficiency.
        self.EtaProp = inp.get('Eta Propulsive', 0.8)
        # Nominal stack (bus) design voltage [V]. The stack is divided into
        # N_cells = V_stack / V_cell_design cells; this sets the stack voltage and the per-cell
        # area, but not the stack mass (which is total-area x specific-power). Default 1000 V.
        self.V_stack = inp.get('Stack Design Voltage', 1000.0)

        # 3. Fail-Fast for internal Database
        if self.model_name not in FC_Database: 
            raise FuelCellError(f"CRITICAL ERROR: FC Model '{self.model_name}' not found in FC_Database.")
            
        params = FC_Database[self.model_name]

        # 4. Fail-Fast for internal FC parameters
        db_required_keys = [
            'Voc', 'b_tafel', 'R_ohm', 'i_star', 'j_lim', 'B_conc', 
            'c_h_ref', 'c_ref', 'sigma_t', 'l_t', 'D_b', 'l_b', 'D_ccl', 
            'T_op', 'Target_Press'
        ]

        for key in db_required_keys:
            if key not in params:
                raise FuelCellError(f"CRITICAL ERROR: Missing parameter '{key}' in FC_Database for model '{self.model_name}'.")

        self.Voc = params['Voc']
        self.b_tafel = params['b_tafel']
        self.R_ohm = params['R_ohm']
        self.i_star = params['i_star']
        self.j_lim = params['j_lim']
        self.B_conc = params['B_conc']
        self.c_h_ref = params['c_h_ref']
        self.c_ref = params['c_ref']
        self.sigma_t = params['sigma_t']
        self.l_t = params['l_t']
        self.D_b = params['D_b']
        self.l_b = params['l_b']
        self.D_ccl = params['D_ccl']
        
        # Assigned from Database strictly
        self.T_op = params['T_op']
        self.Target_Press = params['Target_Press']

        # Beginning-of-life values of the parameters that degrade, then the state of health.
        self.R_ohm_bol = self.R_ohm
        self.i_star_bol = self.i_star
        self.set_state_of_health(
            voltage_loss=inp.get('FC Voltage Loss', 0.0),
            ohmic_resistance_factor=inp.get('FC Ohmic Resistance Factor', 1.0),
            exchange_current_factor=inp.get('FC Exchange Current Factor', 1.0))

        # Phase of the product water -> heat rejected to the coolant (see the class note).
        # 'FC Product Water Vapour Fraction': 'auto' (default, from the cathode-exhaust
        # saturation) or a number in [0, 1] (0 = all liquid / HHV, 1 = all vapour / LHV).
        self.inlet_rh = inp.get('FC Cathode Inlet RH', 0.0)
        # Weather: the ambient air brings its water through the compressor to the cathode.
        self.ambient_rh = inp.get('FC Ambient Relative Humidity', 0.0)
        if not 0.0 <= self.ambient_rh <= 1.0:
            raise FuelCellError("'FC Ambient Relative Humidity' must be in [0, 1]")
        spec = inp.get('FC Product Water Vapour Fraction', 'auto')
        if spec != 'auto':
            spec = float(spec)
            if not 0.0 <= spec <= 1.0:
                raise FuelCellError("'FC Product Water Vapour Fraction' must be 'auto' or in [0, 1]")
        self.x_vapour_spec = spec
        # vapour fraction at the humidifier-only inlet state (updated at every operating point)
        self.x_vapour = (self.product_water_vapour_fraction() if spec == 'auto' else spec)

    def set_state_of_health(self, voltage_loss=0.0, ohmic_resistance_factor=1.0,
                            exchange_current_factor=1.0):
        """Set the degradation state of the stack, relative to beginning of life (BOL).

        Two common ways to describe PEM degradation are supported, and they can be combined:

        - ``voltage_loss`` [V]: a uniform loss of cell voltage at every current density, the
          output of the empirical "voltage decay rate x time at load" models
          (e.g. Pessot et al., Fuel Cells 2020);
        - parameter drift of the polarization curve (e.g. the reviews of Vichard et al.,
          J. Power Sources 2021): ``ohmic_resistance_factor`` = R_ohm / R_ohm,BOL (> 1) and
          ``exchange_current_factor`` = i_star / i_star,BOL (< 1 for a loss of catalyst area).

        The state applies to every later use of the polarization curve. Set it before the
        design to size the stack at end of life; set it on a sized copy to fly a degraded
        stack. The stack mass stays referenced to the BOL curve (see :meth:`_size_stack`).
        """
        if self.R_ohm_bol is None:
            raise FuelCellError("set_state_of_health needs the BOL parameters: call SetInput first.")
        if voltage_loss < 0.0:
            raise FuelCellError(f"FC voltage loss must be >= 0, got {voltage_loss!r}")
        if ohmic_resistance_factor <= 0.0 or exchange_current_factor <= 0.0:
            raise FuelCellError("FC degradation factors must be > 0.")
        self.voltage_loss = float(voltage_loss)
        self.ohmic_resistance_factor = float(ohmic_resistance_factor)
        self.exchange_current_factor = float(exchange_current_factor)
        self.R_ohm = self.R_ohm_bol * self.ohmic_resistance_factor
        self.i_star = self.i_star_bol * self.exchange_current_factor

    def reset_adequacy(self):
        """Clear the power-adequacy trackers filled by :meth:`ComputePRatio`, so the next
        mission flown reports against the present stack and state of health."""
        self._worst_load_ratio = 0.0
        self._worst_alt = None
        self._worst_P_req = 0.0
        self._power_limited = False

    @staticmethod
    def water_saturation_pressure(T):
        """Saturation pressure of water [Pa] at T [K], Antoine equation with the commonly
        tabulated constants for water (1-100 C and 99-374 C ranges, P in mmHg)."""
        Tc = T - 273.15
        A, B, C = (8.07131, 1730.63, 233.426) if Tc <= 100.0 else (8.14019, 1810.94, 244.485)
        return 133.322 * 10.0 ** (A - B / (C + Tc))

    def product_water_vapour_fraction(self, inlet_rh=None):
        """Fraction of the product water the cathode exhaust can carry away as vapour.

        Per mole of H2 reacted: 0.5 mol O2 is consumed, the air entering is
        ``0.5 * stoich / 0.21`` mol and the dry gas leaving is that minus 0.5 mol; 1 mol of water
        is produced. The exhaust leaves saturated at most, at the stack temperature ``T_op`` and
        cathode pressure ``Target_Press``, so it can hold ``p_sat / (P - p_sat)`` mol of vapour
        per mole of dry gas; the inlet air already brings ``inlet_rh`` of saturation. The
        fraction of the product water that can leave as vapour is the remaining capacity,
        limited to [0, 1]. (The exhaust may be sub-saturated, so this is an upper bound.)
        """
        if inlet_rh is None:
            inlet_rh = self.inlet_rh
        P = self.Target_Press
        p_sat = self.water_saturation_pressure(self.T_op)
        if p_sat >= P:                       # above the boiling point: all product water is vapour
            return 1.0
        n_air_in = 0.5 * self.stoich / 0.21
        n_dry_out = n_air_in - 0.5
        p_v_in = inlet_rh * p_sat
        water_in = p_v_in / (P - p_v_in) * n_air_in
        capacity = p_sat / (P - p_sat) * n_dry_out
        return float(min(max(capacity - water_in, 0.0), 1.0))


    def ambient_water_mole_fraction(self, P_amb, T_amb):
        """Mole fraction of water vapour in the ambient air [-] for the relative humidity
        ``ambient_rh`` at the ambient pressure and temperature. The Antoine fit is used below
        0 C as well, where it slightly overestimates the (very small) vapour pressure."""
        if self.ambient_rh <= 0.0:
            return 0.0
        return min(self.ambient_rh * self.water_saturation_pressure(T_amb) / P_amb, 1.0)

    def cathode_inlet_rh(self, P_amb, T_amb):
        """Relative humidity of the cathode inlet at the stack temperature and cathode pressure
        [-]: the larger of the humidifier setting ``inlet_rh`` and the humidity the compressed
        ambient air brings (the compressor keeps the water mole fraction)."""
        p_w = self.ambient_water_mole_fraction(P_amb, T_amb) * self.Target_Press
        rh_ambient = p_w / self.water_saturation_pressure(self.T_op)
        return min(max(self.inlet_rh, rh_ambient), 1.0)

    def vapour_fraction_at(self, P_amb, T_amb):
        """Product-water vapour fraction at an ambient state: the fixed input, or the
        cathode-exhaust saturation limit for the inlet humidity there."""
        if self.x_vapour_spec != 'auto':
            return self.x_vapour_spec
        return self.product_water_vapour_fraction(self.cathode_inlet_rh(P_amb, T_amb))

    def cathode_exhaust(self, P_amb, T_amb):
        """Moles of each exhaust species per mole of H2 reacted, and the vapour fraction.

        Per mole of H2: the dry air brings 0.5 stoich mol O2 and 0.5 stoich 0.79/0.21 mol N2;
        0.5 mol O2 is consumed; the inlet humidity brings water; the product water leaves as
        vapour in the fraction x_v (the liquid is separated before the expander).
        """
        n_o2_in = 0.5 * self.stoich
        n_n2 = n_o2_in * 0.79 / 0.21
        n_air_in = n_o2_in + n_n2
        p_sat = self.water_saturation_pressure(self.T_op)
        p_v_in = min(self.cathode_inlet_rh(P_amb, T_amb) * p_sat, 0.999 * self.Target_Press)
        water_in = p_v_in / (self.Target_Press - p_v_in) * n_air_in
        x_v = self.vapour_fraction_at(P_amb, T_amb)
        return {'N2': n_n2, 'O2': n_o2_in - 0.5, 'H2O': water_in + x_v}, x_v

    def PolarizationCurve(self, i_dens, P_internal_Pa, T_amb=None, bol=False):
        """Computes the cell voltage (Kulikovsky analytical model) at the present state of
        health, or at beginning of life with ``bol=True``."""
        if self.Voc is None: self.SetInput()
        if bol:
            R_ohm, i_star, voltage_loss = self.R_ohm_bol, self.i_star_bol, 0.0
        else:
            R_ohm, i_star, voltage_loss = self.R_ohm, self.i_star, self.voltage_loss

        j0 = max(1e-5, i_dens) 
        p_bar = P_internal_Pa / 1e5
        c_h = self.c_h_ref * p_bar
        
        j_star = (self.sigma_t * self.b_tafel) / self.l_t
        D_star = (self.sigma_t * self.b_tafel) / (4 * self.FARADAY_CONST * self.c_ref)
        eps = np.sqrt((self.sigma_t * self.b_tafel) / (2 * i_star * (self.l_t**2)))
        
        j0_tilde = j0 / j_star
        c_h_tilde = c_h / self.c_ref
        D_tilde = self.D_ccl / D_star
        
        j_lim_star = (4 * self.FARADAY_CONST * self.D_b * c_h) / self.l_b
        
        ratio_lim = min(j0 / j_lim_star, 0.999) 
            
        beta = (np.sqrt(2 * j0_tilde) / (1 + np.sqrt(1.12 * j0_tilde) * np.exp(np.sqrt(2 * j0_tilde)))) + \
               (np.pi * j0_tilde / (2 + j0_tilde))
               
        term1 = np.arcsinh((eps**2 * j0_tilde**2) / (2 * c_h_tilde * (1 - np.exp(-j0_tilde / 2))))
        term2 = (1 / (c_h_tilde * D_tilde)) * (j0_tilde - np.log(1 + (j0_tilde**2) / (beta**2))) * (1 / (1 - ratio_lim))
        term3 = -np.log(1 - ratio_lim)
        
        eta_0_tilde = term1 + term2 + term3
        eta_0 = self.b_tafel * eta_0_tilde
        
        V_conc = 0.0
        if self.j_lim is not None and self.B_conc is not None:
            if j0 >= self.j_lim:
                V_conc = 2.5 # Heavy penalty to simulate physical limit
            else:
                V_conc = -self.B_conc * np.log(1 - j0 / self.j_lim)
            
        V_cell = self.Voc - (R_ohm * j0) - eta_0 - V_conc - voltage_loss
        return max(1e-3, V_cell)

    def _compute_air_system_power(self, P_amb, T_amb, I_tot):
        """Net power absorbed by the air system: the compressor raises the ambient air to the
        cathode pressure, and the expander recovers power from the cathode exhaust.

        The compressor takes the ambient air with its humidity (dry-air cp, as the water is a
        small fraction). The expander takes the cathode exhaust at the stack temperature and
        95 % of the cathode pressure: nitrogen, the oxygen left over, the inlet water and the
        product water that leaves as vapour (:meth:`cathode_exhaust`). Its mass flow, heat
        capacity and isentropic exponent R/cp are those of that mixture, not of air.
        Returns ``(P_comp_net, P_comp, P_turb)`` [W].
        """
        P_cathode = self.Target_Press
        Pressure_Ratio = max(P_cathode / P_amb, 1.0)

        if Pressure_Ratio <= 1.0:
            return 0.0, 0.0, 0.0 # No compression needed

        n_h2 = self.N_cells * I_tot / (2 * self.FARADAY_CONST)      # [mol/s] H2 reacted
        y_w = self.ambient_water_mole_fraction(P_amb, T_amb)
        m_air_dry = 3.57e-7 * self.N_cells * I_tot * self.stoich      # [kg/s] = n_h2 * 0.5 stoich / 0.21 * M_air
        m_comp = m_air_dry * (1.0 + y_w / (1.0 - y_w) * self.MOLAR_MASS['H2O'] / 0.02897)
        T_out_is = T_amb * (Pressure_Ratio**0.286 - 1)
        P_comp = (m_comp * self.CP_AIR * T_out_is) / self.comp_eta

        P_turb_in = P_cathode * 0.95
        P_turb = 0.0
        if P_turb_in > P_amb:
            moles, _ = self.cathode_exhaust(P_amb, T_amb)
            n_tot = sum(moles.values())
            cp_molar = sum(n * self.CP_MOLAR[k] for k, n in moles.items()) / n_tot
            molar_mass = sum(n * self.MOLAR_MASS[k] for k, n in moles.items()) / n_tot
            m_exh = n_h2 * n_tot * molar_mass                           # [kg/s]
            cp_exh = cp_molar / molar_mass                              # [J/(kg K)]
            PR_turb = P_turb_in / P_amb
            P_turb = (m_exh * cp_exh * self.T_op
                      * (1 - (1 / PR_turb) ** (self.R_GAS / cp_molar))) * self.turb_eta

        P_comp_net = max(P_comp - P_turb, 0.0)
        return P_comp_net, P_comp, P_turb

    def ComputeSystemEfficiency(self, i_dens, alt):
        """Computes net efficiency assuming constant pressure at the cathode."""
        if not self.Sizing_Done or self.N_cells == 0:
            return 0.0
            
        P_amb, T_amb = self._get_env(alt)
        v_cell = self.PolarizationCurve(i_dens, self.Target_Press)
        I_tot = i_dens * self.A_cell_reale
        P_gross = self.N_cells * v_cell * I_tot
        
        P_comp_net, _, _ = self._compute_air_system_power(P_amb, T_amb, I_tot)
        P_fixed = self.P_fc_rated * self.Fixed_Aux_Load
        P_net = P_gross - P_comp_net - P_fixed
        
        m_dot_h2 = (self.N_cells * I_tot) / (2 * self.FARADAY_CONST) * self.MOLAR_MASS_H2
        P_chem = m_dot_h2 * self.HHV_H2
        
        return P_net / P_chem if P_chem > 0 else 0.0

    # Single, explicit power-sizing margin for the fuel cell (replaces the former opaque
    # 1/0.8 and 1/0.85 factors). The *conservative* sizing case comes from the take-off / OEI
    # constraints the caller passes in, not from hidden fudge factors.
    SizingMargin = 1.0

    # Fraction of *gross* stack power left after the air-system (compressor) + fixed auxiliaries
    # at the sizing (peak) condition. The active area is sized from gross = net / this, so the cell
    # operates near its design voltage at the peak. The real parasitic draw is ~4 % (sea level) to
    # ~12 % (cruise altitude); 0.85 covers the worst-case parasitic with a small (~4 %) power margin
    # so the cell is not power-limited at altitude (checked by report_sizing) without over-sizing the
    # stack, which a looser factor (e.g. 0.72) would do.
    BoP_Power_Sizing_Efficiency = 0.85

    def _size_stack(self, P_propulsive_design):
        """Size the stack / BoP / electric motor from a required *propulsive* power [W].

        Sets the cell geometry (``N_cells``, ``A_cell_reale``), the rated electrical power
        ``P_fc_rated`` and the system mass ``_Weight`` (and the ``weight`` component split),
        and returns the mass. This single kernel is used by :meth:`SizeForPropulsivePower`
        and :meth:`SizeFromConstraint`.
        """
        if self.i_max_density is None or self.V_stack is None:
            self.SetInput()

        # Design current density at the design cell voltage.
        try:
            self.i_max_density = brentq(
                lambda i: self.PolarizationCurve(i, self.Target_Press) - self.V_cell_design,
                0.0001, 5.0)
        except ValueError:
            self.V_cell_design = self.PolarizationCurve(self.i_max_density, self.Target_Press)

        # Downstream efficiency from the net FC terminals to useful thrust power: electric drive
        # (motor, PMAD, gearbox) AND the propeller. This matches the chain used per-point in
        # ComputePRatio, so the rating is consistent with the power the mission actually demands and
        # the BoP_Power_Sizing_Efficiency below is a pure air-system allowance, not a hidden cover
        # for the propeller loss.
        eta_downstream = self.EtaEM * self.EtaPM * self.EtaGB * self.EtaProp
        P_elec_propulsive = P_propulsive_design / eta_downstream
        # net electrical rating [W]: propulsion + the TMS pump (0 unless Class-II TMS)
        self.P_fc_rated = P_elec_propulsive + self.P_aux_tms

        self.N_cells = max(int(self.V_stack / self.V_cell_design), 100)

        # Active area is sized so that at the *design* current density the stack delivers the net
        # rating after the air-system + fixed auxiliaries. Those parasitics are only ~4 % of gross
        # at sea level and ~12 % at cruise altitude (measured from the air-system model), so the
        # gross is the net rating divided by ~0.85 — not the former 1.30/0.65 ≈ 2x, which oversized
        # the stack and made the cell loaf at a fraction of its design current over the whole
        # mission. Any intended power margin is the explicit, single ``SizingMargin`` (applied by
        # the caller); the cell now operates near its design voltage at the sizing (peak) point.
        P_gross_design = self.P_fc_rated / self.BoP_Power_Sizing_Efficiency
        surf_power_dens = self.V_cell_design * self.i_max_density
        Total_Active_Area = P_gross_design / surf_power_dens
        self.A_cell_reale = Total_Active_Area / self.N_cells

        # The stack specific power is a hardware figure (W/kg at 0.7 V), so the mass per active
        # area is referenced to the BOL curve: a stack sized at end of life is larger, not lighter.
        try:
            i_ref = brentq(lambda i: self.PolarizationCurve(i, self.Target_Press, bol=True) - 0.7,
                           0.0001, 5.0)
        except ValueError:
            i_ref = 1.0
        kg_per_cm2 = (0.7 * i_ref) / self.Stack_PD

        M_Stack = Total_Active_Area * kg_per_cm2
        M_BoP = M_Stack * self.BoP_Mass_Ratio
        # Electric drive sized with the *same* specific powers as the hybrid powertrain, so the
        # motor + power-management mass is consistent across configurations (no hard-coded values).
        # Specific powers come from the powertrain (config), with literature current-SOA
        # fallbacks (motor 5000, inverter 10000 W/kg).
        pt = getattr(self.aircraft, 'powertrain', None)
        sp_powertrain = getattr(pt, 'SPowerPT', None) if pt is not None else None
        sp_motor = sp_powertrain[1] if sp_powertrain else 5000.0
        sp_pmad = pt.pmad_specific_power() if (pt is not None and hasattr(pt, 'pmad_specific_power')) else 10000.0
        # The PMAD carries the net electrical rating and the motor the propulsive part of it
        # downstream of the PMAD (· EtaPM). In 'FuelCellBattery' the battery feeds the same PMAD
        # and motor, so both are sized on the peak propulsive power through the drive at one
        # instant, fuel-cell and battery shares together (mission.Max_PDrive: mission,
        # take-off / OEI, ground legs, from the last flown mission), turned into electrical
        # power with the same downstream efficiency as the stack rating. It is never below
        # the fuel-cell share, so a phi = 0 design stays identical to the 'Hydrogen' one.
        P_drive_propulsive = P_propulsive_design
        if self.aircraft.Configuration == 'FuelCellBattery':
            mission = getattr(self.aircraft, 'mission', None)
            P_drive_peak = getattr(mission, 'Max_PDrive', 0.0) or 0.0
            P_drive_propulsive = max(P_propulsive_design, P_drive_peak * self.SizingMargin)
        P_drive_elec = P_drive_propulsive / eta_downstream
        M_EM = (P_drive_elec * self.EtaPM) / sp_motor
        M_PM = (P_drive_elec + self.P_aux_tms) / sp_pmad

        self._Weight = M_Stack + M_BoP + M_EM + M_PM
        self.Sizing_Done = True
        # New stack capability -> reset the adequacy trackers; the next mission fly repopulates
        # them against this stack (so report_sizing() always reflects the final, flown stack).
        self.reset_adequacy()
        if hasattr(self.aircraft, 'weight'):
            self.aircraft.weight.WPT = self._Weight
            self.aircraft.weight.WThermal = M_Stack + M_BoP + M_PM
            self.aircraft.weight.WElectric = M_EM
        return self._Weight

    def SizeForPropulsivePower(self, P_propulsive_req):
        """Size the fuel cell to deliver a required *propulsive* power [W].

        ``P_propulsive_req`` is the worst case of (mission peak, take-off, OEI climb), assembled
        by the caller (the weight loop). The only sizing margin applied is :attr:`SizingMargin`.
        """
        return self._size_stack(P_propulsive_req * self.SizingMargin)

    def SizeFromConstraint(self, WTO):
        """Seed the fuel-cell geometry from the constraint power-to-weight ``DesignPW``.

        ``DesignPW`` is the constraint-diagram envelope (which already includes the take-off
        and OEI requirements), so this gives a representative fuel cell for the *first* mission
        pass before the mission-peak resize loop refines it self-consistently.
        """
        pw = max(getattr(self.aircraft, 'DesignPW', 0.0), 155.0)
        sizing_mass = 25000.0 if WTO < 10000.0 else WTO
        return self._size_stack(pw * sizing_mass)

    def ComputeAndStoreWeights(self, WTO):
        """Backwards-compatible alias for :meth:`SizeFromConstraint`."""
        return self.SizeFromConstraint(WTO)

    @property
    def Weight(self):
        return self._Weight

    def _get_env(self, alt):
        """Ambient static pressure [Pa] and temperature [K] at ``alt``: the package ISA
        atmosphere shifted by the mission temperature deviation DISA (hot / cold day)."""
        mission = getattr(self.aircraft, 'mission', None)
        DISA = (getattr(mission, 'DISA', 0.0) or 0.0) if mission is not None else 0.0
        if ISA is not None:
            return ISA.atmosphere.Pstd(alt), ISA.atmosphere.Tstd(alt) + DISA
        T = 288.15 - 0.0065 * alt
        P = 101325.0 * (1 - 0.0065 * alt / 288.15)**5.255
        return P, T + DISA

    # Fixed point of the propeller efficiency at its own shaft power (Hamilton model).
    DRIVE_EFFICIENCY_TOL = 1e-6      # shaft-power residual, relative to P_propulsive
    DRIVE_EFFICIENCY_MAX_ITER = 50

    def drive_efficiencies(self, alt, vel, P_propulsive):
        """Electric-motor and propeller efficiencies ``(eta_em, eta_prop)`` of the drive
        delivering the propulsive power ``P_propulsive`` [W].

        Constant by default (``EtaEM``, ``EtaProp``). With the Hamilton propeller attached
        (``powertrain.Propeller``) the propeller is the powertrain's ``'propeller'`` model
        (``HamiltonPropellerEfficiency``, the one the gas-turbine graphs use, bounded to
        [0.4, 1]), evaluated at its shaft input ``P_propulsive / eta_prop``, a damped fixed
        point started at ``P_propulsive``; with the
        Class-II ('Smart') motor the motor is evaluated at its shaft output
        ``P_propulsive / (EtaGB * eta_prop)``: the conventions of ``Powertrain.eta``.

        ``P_propulsive`` is the power of the branch the caller evaluates: the whole propulsive
        power in 'Hydrogen', the fuel-cell or the battery share in 'FuelCellBattery'. There the
        two branches share the motor and the propeller, so a Class-II model is read at the
        branch power, not at the total power through it (an approximation; constant models
        are unaffected).
        """
        pt = self.aircraft.powertrain
        if hasattr(pt, 'Propeller'):
            # Fixed point on the shaft power P_shaft = P_propulsive / eta(P_shaft), damped as in
            # Powertrain._solve_at_component_powers: the step is halved whenever it changes sign
            # (a propeller at low power overshoots and oscillates otherwise).
            P_shaft = P_propulsive
            eta_prop = pt.eta('propeller', alt, vel, P_shaft)
            relax, previous_step = 1.0, 0.0
            for _ in range(self.DRIVE_EFFICIENCY_MAX_ITER):
                step = P_propulsive / eta_prop - P_shaft
                if abs(step) <= self.DRIVE_EFFICIENCY_TOL * max(P_propulsive, 1.0):
                    break
                if step * previous_step < 0.0:
                    relax *= 0.5                     # overshoot: damp the step
                previous_step = step
                P_shaft += relax * step
                eta_prop = pt.eta('propeller', alt, vel, P_shaft)
        else:
            eta_prop = self.EtaProp
        if self.aircraft.EnergyInput.get('Eta Electric Motor Model') == 'Smart':
            eta_em = pt.eta('electric_motor', alt, vel, P_propulsive / (self.EtaGB * eta_prop))
        else:
            eta_em = self.EtaEM
        return eta_em, eta_prop

    def ComputePRatio(self, alt, vel, P_req_net):
        """Computes operational state given altitude, velocity and required net power."""
        if not self.Sizing_Done: self.ComputeAndStoreWeights(1000.0)

        P_amb, T_amb = self._get_env(alt)
        
        # Electric-motor and propeller efficiencies (constant, or the Class-II models at their
        # own shaft powers, see drive_efficiencies).
        eta_em, eta_prop = self.drive_efficiencies(alt, vel, P_req_net)
        eta_mech = self.EtaGB * eta_em * self.EtaPM
        eta_mech *= eta_prop

        P_elec_propulsive = P_req_net / max(eta_mech, 0.01)
        P_elec_target = P_elec_propulsive + self.P_aux_tms      # + TMS pump (Class II)
        limit = self.j_lim if self.j_lim is not None else 2.5 

        def residual(i_guess):
            v_cell = self.PolarizationCurve(i_guess, self.Target_Press)
            if v_cell <= 0.1: return -P_elec_target * 2.0

            I_tot = i_guess * self.A_cell_reale
            P_gross = self.N_cells * v_cell * I_tot
            
            P_comp_net, _, _ = self._compute_air_system_power(P_amb, T_amb, I_tot)
            P_fixed = self.P_fc_rated * self.Fixed_Aux_Load
            
            return (P_gross - P_comp_net - P_fixed) - P_elec_target

        test_points = np.linspace(0.0001, limit * 0.95, 50)
        res_values = np.array([residual(x) for x in test_points])
        idx_change = np.where(np.diff(np.sign(res_values)))[0]

        # Operating point. residual(i) = P_net_available(i) - P_elec_target.
        # ``scale`` is 1 when the stack meets the demand. When it cannot, the stack runs at its
        # maximum-net-power point and the shortfall is supplied at that point's efficiency: the
        # flows and the heat are those of a stack ``scale`` times larger running there. This
        # keeps the hydrogen and the heat physical (they grow with the demand and with the
        # degradation) and is continuous with the feasible branch at load ratio 1;
        # ``_power_limited`` tells the caller that the stack is undersized for this demand.
        scale = 1.0
        if len(idx_change) > 0:
            # the first sign change brackets the lowest-current root
            idx = idx_change[0]
            i_op = brentq(residual, test_points[idx], test_points[idx + 1], xtol=1e-4)
            P_net_max = float(np.max(res_values)) + P_elec_target
        elif res_values[0] >= 0.0:
            # the demand is below the net power at the smallest current density of the grid
            i_op = test_points[0]
            P_net_max = float(np.max(res_values)) + P_elec_target
        else:
            # no root on the grid: refine the maximum net power around the best grid point
            best_idx = int(np.argmax(res_values))
            lo = test_points[max(best_idx - 1, 0)]
            hi = test_points[min(best_idx + 1, len(test_points) - 1)]
            i_mp = minimize_scalar(lambda i: -residual(i), bounds=(lo, hi), method='bounded',
                                   options={'xatol': 1e-6}).x
            P_net_max = residual(i_mp) + P_elec_target
            if P_net_max <= 0.0:
                raise FuelCellError(
                    f"Fuel-cell stack delivers no net power at altitude {alt:.0f} m "
                    f"(air-system and fixed auxiliaries exceed the gross stack power).",
                    code="FC_NO_NET_POWER")
            if P_net_max >= P_elec_target:
                # the demand is met between two grid points
                i_op = brentq(residual, lo, i_mp, xtol=1e-6) if residual(lo) < 0.0 else lo
            else:
                i_op = i_mp
                scale = P_elec_target / P_net_max

        # --- Adequacy tracking ---------------------------------------------------------
        # The load ratio required / available > 1 means the cell cannot meet the demand here.
        load_ratio = P_elec_target / P_net_max if P_net_max > 0.0 else float('inf')
        if load_ratio > self._worst_load_ratio:
            self._worst_load_ratio = load_ratio
            self._worst_alt = float(alt)
            self._worst_P_req = float(P_req_net)
        if load_ratio > 1.0 + 1e-6:
            self._power_limited = True

        I_final = i_op * self.A_cell_reale
        v_cell = self.PolarizationCurve(i_op, self.Target_Press)
        P_comp_net, _, P_turb = self._compute_air_system_power(P_amb, T_amb, I_final)
        self.P_gross_last = scale * self.N_cells * v_cell * I_final
        self.P_comp_net_last = scale * P_comp_net
        self.P_turb_last = scale * P_turb

        m_dot_h2 = scale * (self.N_cells * I_final) / (2 * self.FARADAY_CONST) * self.MOLAR_MASS_H2
        P_chem = m_dot_h2 * self.HHV_H2
        self.mdot_h2 = m_dot_h2
        self.mdot_air = scale * 3.57e-7 * self.N_cells * I_final * self.stoich

        Eta_FCS = P_elec_target / P_chem if P_chem > 0 else 0.01
        # propulsive share of the electrical output (1.0 without a TMS pump load)
        share = P_elec_propulsive / P_elec_target if P_elec_target > 0 else 1.0
        Eta_Total_Sys = np.clip(Eta_FCS * eta_mech * share, 0.01, 0.85)

        self.x_vapour = self.vapour_fraction_at(P_amb, T_amb)       # product-water phase here
        dh_coolant = self.DELTA_H_REACT - self.x_vapour * (self.DELTA_H_REACT - self.DELTA_H_REACT_LHV)
        p_th_cell = i_op * (dh_coolant / (2 * self.FARADAY_CONST) - v_cell)
        self.Q_thermal = scale * p_th_cell * self.N_cells * self.A_cell_reale

        # Expose the operating point for post-processing (tutorials / mission timelines).
        self.i_op_last = i_op
        self.v_cell_last = v_cell
        self.eta_fcs_last = Eta_FCS

        # Power ratios [1/eta_total, 1]. The mission and the take-off point charge hydrogen
        # from mdot_h2 * HHV, not from this clipped ratio; it is kept for callers of the API.
        return np.array([1.0/Eta_Total_Sys, 1.0])

    def report_sizing(self, raise_on_undersize=False):
        """Check that the sized fuel cell can deliver the power the mission demands.

        Mirrors :meth:`Powertrain.report_class_ii_sizing` for the fuel cell. Run *after* the
        weight-sizing loop has flown the mission: :meth:`ComputePRatio` records, at every
        operating point, the ratio of required to *available* net power (the available power
        falls with altitude as the air-system draws more), so a stack whose sea-level rating
        looks sufficient can still be **power-limited at altitude**. At such a point
        ``ComputePRatio`` runs the stack at its maximum-power point scaled to the demand, so
        the mission still closes; this check is what reports the shortfall.

        Returns a ``dict`` with the rated power, the worst-case load ratio and its altitude,
        whether the stack is ``power_limited`` and the ``min_rating`` needed to avoid it, and
        warns (or, with ``raise_on_undersize=True``, raises) when the cell is undersized.
        """
        import warnings

        ratio = self._worst_load_ratio
        flown = ratio > 0.0
        power_limited = self._power_limited or ratio > 1.0 + 1e-6
        if not flown:
            status = "unknown"
        elif power_limited:
            status = "UNDERSIZED"
        elif ratio < 0.5:
            status = "oversized"
        else:
            status = "ok"
        min_rating = self.P_fc_rated * max(ratio, 1.0)
        report = {
            "rated_power": self.P_fc_rated,
            "worst_load_ratio": ratio,
            "worst_altitude": self._worst_alt,
            "peak_demand": self._worst_P_req,
            "power_limited": power_limited,
            "min_rating": min_rating,
            "status": status,
        }
        if power_limited:
            where = f" at {self._worst_alt:.0f} m" if self._worst_alt is not None else ""
            msg = (f"fuel cell is undersized (power-limited{where}): the required power exceeds "
                   f"the stack's available power by up to {(ratio - 1) * 100:.0f}% — the cell "
                   f"cannot sustain that flight condition. Increase the stack size (rated power "
                   f"to at least {min_rating / 1e3:.0f} kW): raise FuelCell.SizingMargin, or raise "
                   f"the design cell voltage 'v_cell_design' (a larger active area, with more "
                   f"headroom to the maximum-power point).")
            if raise_on_undersize:
                raise ValueError(msg)
            warnings.warn(msg)
        return report

    # NOTE: the former FinalizeMassFromMission (which shrank the stack to the mission peak
    # *after* the mission, using opaque 1/0.8 and 1/0.85 margins and dropping the take-off/OEI
    # basis) has been removed. The fuel cell is now sized once, self-consistently, by the
    # weight loop: SizeFromConstraint (seed) -> fly -> SizeForPropulsivePower(max(mission peak,
    # take-off, OEI)) -> re-fly, so the fuel cell that flies the mission is the one that is
    # weighed, and the take-off/OEI requirement is a hard floor.