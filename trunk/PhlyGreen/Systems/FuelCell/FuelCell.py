import numpy as np
import warnings
from scipy.optimize import brentq

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
    LHV_H2 = 119.96e6            # [J/kg] Lower Heating Value of Hydrogen
    MOLAR_MASS_H2 = 0.002016     # [kg/mol] Molar mass of Hydrogen
    DELTA_H_REACT = 286000.0     # [J/mol] Enthalpy of reaction (HHV based)

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

        # FUNDAMENTAL GEOMETRIC AND THERMAL OUTPUTS
        self.N_cells = 0  
        self.A_cell_reale = 0.0  
        self.P_fc_rated = 0.0  
        self.Q_thermal = 0.0  
        
        # --- SUMMARY OUTPUTS ---
        self.P_gross_last = 0.0
        self.P_comp_net_last = 0.0
        self.P_turb_last = 0.0

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
        self.i_max_density = inp['i Rated']
        self.V_cell_design = inp['V Cell Design']
        self.Stack_PD = inp['Stack Power Density']
        self.BoP_Mass_Ratio = inp['BoP Mass Ratio']
        self.EtaPM = inp['Eta PMAD']
        self.EtaEM = inp['Eta Electric Motor']
        self.EtaGB = inp['Eta Gearbox']
        
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


    def PolarizationCurve(self, i_dens, P_internal_Pa, T_amb=None):
        """Computes the cell voltage (Kulikovsky analytical model)."""
        if self.Voc is None: self.SetInput()
        
        j0 = max(1e-5, i_dens) 
        p_bar = P_internal_Pa / 1e5
        c_h = self.c_h_ref * p_bar
        
        j_star = (self.sigma_t * self.b_tafel) / self.l_t
        D_star = (self.sigma_t * self.b_tafel) / (4 * self.FARADAY_CONST * self.c_ref)
        eps = np.sqrt((self.sigma_t * self.b_tafel) / (2 * self.i_star * (self.l_t**2)))
        
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
            
        V_cell = self.Voc - (self.R_ohm * j0) - eta_0 - V_conc
        return max(1e-3, V_cell)

    def _compute_air_system_power(self, P_amb, T_amb, I_tot):
        """
        Helper method (DRY): Computes net power absorbed by the compressor 
        and recovered by the turbine.
        """
        P_cathode = self.Target_Press
        Pressure_Ratio = max(P_cathode / P_amb, 1.0)
        
        if Pressure_Ratio <= 1.0:
            return 0.0, 0.0, 0.0 # No compression needed
            
        m_air = 3.57e-7 * self.N_cells * I_tot * self.stoich 
        T_out_is = T_amb * (Pressure_Ratio**0.286 - 1)
        P_comp = (m_air * self.CP_AIR * T_out_is) / self.comp_eta
        
        P_turb_in = P_cathode * 0.95 
        P_turb = 0.0
        if P_turb_in > P_amb:
            PR_turb = P_turb_in / P_amb
            P_turb = (m_air * self.CP_AIR * self.T_op * (1 - (1/PR_turb)**0.286)) * self.turb_eta
            
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
        P_chem = m_dot_h2 * self.LHV_H2
        
        return P_net / P_chem if P_chem > 0 else 0.0

    def ComputeAndStoreWeights(self, WTO):
        if self.i_max_density is None: self.SetInput()

        def find_current_from_voltage(i_guess):
            return self.PolarizationCurve(i_guess, self.Target_Press) - self.V_cell_design

        try:
            self.i_max_density = brentq(find_current_from_voltage, 0.0001, 5.0)
        except ValueError:
            self.V_cell_design = self.PolarizationCurve(self.i_max_density, self.Target_Press)

        pw_constraint = getattr(self.aircraft, 'DesignPW', 0.0)
        Target_PW_Base = max(pw_constraint, 155.0)
        pw_val = Target_PW_Base * 1.65 # Oversizing Factor

        Sizing_Mass = 25000.0 if WTO < 10000.0 else WTO

        P_shaft_design = Sizing_Mass * pw_val 
        eta_downstream = self.EtaEM * self.EtaPM * self.EtaGB
        self.P_fc_rated = P_shaft_design / eta_downstream 

        self.N_cells = max(int(1000.0 / self.V_cell_design), 100)

        Efficiency_BoP_Estimate = 0.65
        P_gross_design = (self.P_fc_rated * 1.30) / Efficiency_BoP_Estimate 
        surf_power_dens = self.V_cell_design * self.i_max_density
        Total_Active_Area = P_gross_design / surf_power_dens

        self.A_cell_reale = Total_Active_Area / self.N_cells 

        try:
            i_ref = brentq(lambda i: self.PolarizationCurve(i, self.Target_Press) - 0.7, 0.0001, 5.0)
        except ValueError:
            i_ref = 1.0
            
        kg_per_cm2 = (0.7 * i_ref) / self.Stack_PD 
        
        M_Stack = Total_Active_Area * kg_per_cm2
        M_BoP = M_Stack * self.BoP_Mass_Ratio
        M_EM = (self.P_fc_rated * self.EtaPM) / 5000.0
        M_PM = self.P_fc_rated / 10000.0

        self._Weight = M_Stack + M_BoP + M_EM + M_PM
        self.Sizing_Done = True

        return self._Weight

    @property
    def Weight(self):
        return self._Weight

    def _get_env(self, alt):
        if ISA and hasattr(ISA, 'ISA'): return ISA.ISA(alt, 0)[:2]
        T = 288.15 - 0.0065 * alt
        P = 101325.0 * (1 - 0.0065 * alt / 288.15)**5.255
        return P, T

    def ComputePRatio(self, alt, vel, P_req_net):
        """Computes operational state given altitude, velocity and required net power."""
        if not self.Sizing_Done: self.ComputeAndStoreWeights(1000.0)

        P_amb, T_amb = self._get_env(alt)
        
        eta_mech = self.EtaGB * self.EtaEM * self.EtaPM
        if hasattr(self.aircraft.powertrain, 'Propeller'):
            eta_prop = self.aircraft.powertrain.Propeller.ComputePropEfficiency(alt, vel, P_req_net)
            eta_mech *= eta_prop
        else:
            eta_mech *= 0.8

        P_elec_target = P_req_net / max(eta_mech, 0.01)
        limit = self.j_lim if self.j_lim is not None else 2.5 

        def residual(i_guess):
            v_cell = self.PolarizationCurve(i_guess, self.Target_Press)
            if v_cell <= 0.1: return -P_elec_target * 2.0

            I_tot = i_guess * self.A_cell_reale
            P_gross = self.N_cells * v_cell * I_tot
            
            P_comp_net, _, _ = self._compute_air_system_power(P_amb, T_amb, I_tot)
            P_fixed = self.P_fc_rated * self.Fixed_Aux_Load
            
            return (P_gross - P_comp_net - P_fixed) - P_elec_target

        valid_solution = False
        i_op = 0.0

        test_points = np.linspace(0.0001, limit * 0.95, 50)
        res_values = np.array([residual(x) for x in test_points])
        idx_change = np.where(np.diff(np.sign(res_values)))[0]

        if len(idx_change) > 0:
            idx = idx_change[0]
            try:
                i_op = brentq(residual, test_points[idx], test_points[idx+1], xtol=1e-4)
                valid_solution = True
            except ValueError:
                valid_solution = False

        if not valid_solution:
            # Grid search fallback if root finding fails
            best_idx = np.argmax(res_values)
            if res_values[best_idx] < 0 and abs(res_values[best_idx]) < (P_elec_target * 0.01):
                i_op = test_points[best_idx]
                valid_solution = True

        if valid_solution:
            I_final = i_op * self.A_cell_reale
            v_cell = self.PolarizationCurve(i_op, self.Target_Press)
            
            self.P_gross_last = self.N_cells * v_cell * I_final
            self.P_comp_net_last, _, self.P_turb_last = self._compute_air_system_power(P_amb, T_amb, I_final)

            m_dot_h2 = (self.N_cells * I_final) / (2 * self.FARADAY_CONST) * self.MOLAR_MASS_H2
            P_chem = m_dot_h2 * self.LHV_H2
            
            Eta_FCS = P_elec_target / P_chem if P_chem > 0 else 0.01
            Eta_Total_Sys = np.clip(Eta_FCS * eta_mech, 0.01, 0.85)

            p_th_cell = i_op * (self.DELTA_H_REACT / (2 * self.FARADAY_CONST) - v_cell)
            self.Q_thermal = p_th_cell * self.N_cells * self.A_cell_reale 

            return np.array([1.0/Eta_Total_Sys, 1.0])
        else:
            # Fallback to analytical scaling if physical limits are exceeded
            P_idle_chem = (self.P_fc_rated * self.Fixed_Aux_Load) / 0.40
            P_chem_total = P_idle_chem + (P_req_net / 0.40) 
            self.Q_thermal = P_chem_total * 0.60 
            self.P_gross_last = P_chem_total * 0.40
            self.P_comp_net_last = P_chem_total * 0.10
            return np.array([P_chem_total / max(P_req_net, 1.0), 1.0])

    def FinalizeMassFromMission(self):
        """Updates Powertrain Mass considering mission peaks."""
        try:
            p_max_mission_shaft = np.max([
                self.aircraft.mission.Max_PEng,
                self.aircraft.mission.TO_PP / 0.85
            ])
        except AttributeError:
            p_max_mission_shaft = 2000000.0

        eta_chain = self.EtaEM * self.EtaPM * self.EtaGB
        self.P_fc_rated = p_max_mission_shaft / eta_chain
        
        P_gross_design = (self.P_fc_rated * 1.30) / 0.65 

        if self.V_cell_design is None: self.SetInput()

        Total_Active_Area = P_gross_design / (self.V_cell_design * self.i_max_density)
        self.A_cell_reale = Total_Active_Area / self.N_cells

        try:
            i_ref = brentq(lambda i: self.PolarizationCurve(i, self.Target_Press) - 0.7, 0.0001, 5.0)
        except ValueError: 
            i_ref = 1.0
            
        kg_per_cm2 = (0.7 * i_ref) / self.Stack_PD 
        M_Stack = Total_Active_Area * kg_per_cm2
        M_BoP = M_Stack * self.BoP_Mass_Ratio
        M_EM = (self.P_fc_rated * self.EtaPM) / 5000.0
        M_PM = self.P_fc_rated / 10000.0

        self._Weight = M_Stack + M_BoP + M_EM + M_PM

        if hasattr(self.aircraft, 'weight'):
            self.aircraft.weight.WPT = self._Weight
            self.aircraft.weight.WThermal = M_Stack + M_BoP + M_PM 
            self.aircraft.weight.WElectric = M_EM

        return self._Weight