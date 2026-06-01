import numpy as np
import CoolProp.CoolProp as CP
import warnings

# --- DATABASE IMPORT MANAGEMENT (Strict Fail-Fast) ---
try:
    from PhlyGreen.Systems.Serbatoio_H2.TANK_Database import TANK_Database
except ImportError:
    try:
        from .TANK_Database import TANK_Database
    except ImportError:
        try:
            from TANK_Database import TANK_Database
        except ImportError:
            raise ImportError("CRITICAL ERROR: 'TANK_Database.py' file not found. Ensure the file is in the correct directory.")

# ==========================================
# 0. ATMOSPHERE MODEL HELPER
# ==========================================
def get_isa_atmosphere(altitude_m):
    """Computes ISA Temperature and Pressure up to the Tropopause."""
    T0 = 288.15; P0 = 101325.0; L = 0.0065; g = 9.80665; R_air = 287.05
    altitude_m = min(altitude_m, 11000.0) # Cap at tropopause for simplicity
    T_amb = T0 - L * altitude_m
    P_amb = P0 * (1 - L * altitude_m / T0)**(g / (R_air * L))
    return T_amb, P_amb


# ==========================================
# 1. LH2 TANK CLASS (Data-Driven)
# ==========================================
class LH2_Tank:
    def __init__(self, capacity_kg, aircraft, allow_auto_split=True):
        
        # --- 0. AUTO-FETCH DA TANK INPUT ---
        self.aircraft = aircraft
        TankInput = getattr(self.aircraft, 'TankInput', None)
        
        if TankInput is None:
            raise ValueError("CRITICAL ERROR: 'TankInput' dictionary was not found in the aircraft object!")
            
        required_keys = ['Max Diameter', 'Number of Tanks', 'Tank Model']
        for key in required_keys:
            if key not in TankInput:
                raise ValueError(f"CRITICAL ERROR: Missing '{key}' in the TankInput dictionary.")
        
        # Assegnazione automatica
        self.max_diameter_limit = TankInput['Max Diameter']
        self.n_tanks = int(TankInput['Number of Tanks'])
        model_key = TankInput['Tank Model']

        self.m_tot_capacity = capacity_kg
        self.fluid = 'ParaHydrogen'
        self.allow_auto_split = allow_auto_split 

        # --- 1. CARICAMENTO DAL DATABASE ESTERNO (TANK_Database) ---
        if model_key not in TANK_Database:
            raise ValueError(f"CRITICAL ERROR: Tank model '{model_key}' not found in TANK_Database!")
        
        params = TANK_Database[model_key]

        # Fail-Fast for internal Database variables
        db_required_keys = [
            'max_p_bar', 'min_p_bar', 'sigma_y', 'rho_al', 'E_al', 'nu_al',
            'sf_inner', 'sf_outer', 'ew', 'buckling_knockdown', 'accessory_mass_factor',
            'n_layers_mli', 't_foam', 'rho_foam', 'insulation_gap',
            'C1', 'C2', 'C3', 'Cg', 'ng', 'p_mli', 'Nt', 'eps'
        ]

        for key in db_required_keys:
            if key not in params:
                raise ValueError(f"CRITICAL ERROR: Missing parameter '{key}' in TANK_Database for model '{model_key}'.")

        # --- 2. TANK SETUP (Direct assignment without .get()) ---
        
        # Pressures
        self.P_max = params['max_p_bar'] * 1e5
        self.P_min = max(params['min_p_bar'], 1.2) * 1e5
        
        # Material Properties
        self.sigma_y = params['sigma_y']
        self.rho_al = params['rho_al']
        self.E_al = params['E_al']
        self.nu_al = params['nu_al']
        
        # Safety and Structural Factors
        self.sf_inner = params['sf_inner']
        self.sf_outer = params['sf_outer']
        self.ew = params['ew']
        self.buckling_knockdown = params['buckling_knockdown']
        self.accessory_mass_factor = params['accessory_mass_factor'] 
        
        # Insulation Properties
        self.n_layers_mli = params['n_layers_mli']
        self.t_foam = params['t_foam']
        self.rho_foam = params['rho_foam']
        self.insulation_gap = params['insulation_gap']
        
        # MLI Thermal Constants
        self.C1 = params['C1']
        self.C2 = params['C2']
        self.C3 = params['C3']
        self.Cg = params['Cg']
        self.ng = params['ng']
        self.p_mli = params['p_mli']
        self.Nt = params['Nt']
        self.eps = params['eps']

        # --- 3. GEOMETRIC SIZING & SPLITTING LOGIC ---
        try:
            rho_liq = CP.PropsSI('D', 'P', self.P_min, 'Q', 0, self.fluid)
        except Exception:
            rho_liq = 70.0 # Fallback liquid density if CoolProp fails at initialization

        self.ullage_frac = 0.04 
        sizing_ok = False
        
        while not sizing_ok:
            self.capacity_single = self.m_tot_capacity / self.n_tanks
            self.V_internal = (self.capacity_single / rho_liq) * (1 + self.ullage_frac)
            
            # Geometric constraints (subtracting clearance)
            R_limit = (self.max_diameter_limit / 2.0) - 0.15
            V_sphere_limit = (4/3) * np.pi * R_limit**3
            
            if self.V_internal <= V_sphere_limit:
                # SPHERICAL REGIME
                self.shape = "Sphere"
                self.r_inner = (self.V_internal * 3 / (4 * np.pi))**(1/3)
                self.L_cyl = 0.0
                
                self.area_sphere = 4 * np.pi * self.r_inner**2
                self.area_cyl = 0.0
                sizing_ok = True
            else:
                # CYLINDRICAL REGIME
                self.shape = "Cylinder"
                self.r_inner = R_limit 
                
                V_cyl_needed = self.V_internal - V_sphere_limit
                self.L_cyl = V_cyl_needed / (np.pi * self.r_inner**2)
                
                # Aspect Ratio check: If too long, split the tank
                if self.L_cyl > 20 * self.r_inner: 
                     self.n_tanks += 1
                else:
                     self.area_sphere = 4 * np.pi * self.r_inner**2
                     self.area_cyl = 2 * np.pi * self.r_inner * self.L_cyl
                     self.area_inner_tot = self.area_sphere + self.area_cyl
                     
                     if not self.allow_auto_split:
                         sizing_ok = True
                     else:
                         # --- GRAVIMETRIC INDEX COMPARISON ---
                         self._calculate_structure()
                         gi_cyl = self.gravimetric_index
                         
                         n_tanks_test = self.n_tanks + 1
                         cap_single_test = self.m_tot_capacity / n_tanks_test
                         V_int_test = (cap_single_test / rho_liq) * (1 + self.ullage_frac)
                         
                         shape_test = "Sphere" if V_int_test <= V_sphere_limit else "Cylinder"
                         if shape_test == "Sphere":
                             r_in_test = (V_int_test * 3 / (4 * np.pi))**(1/3)
                             L_cyl_test = 0.0
                         else:
                             r_in_test = R_limit
                             L_cyl_test = (V_int_test - V_sphere_limit) / (np.pi * r_in_test**2)
                             
                         area_sph_test = 4 * np.pi * r_in_test**2
                         area_cyl_test = 2 * np.pi * r_in_test * L_cyl_test if shape_test == "Cylinder" else 0.0
                         
                         # Backup current state
                         shape_bkp, r_in_bkp, L_cyl_bkp = self.shape, self.r_inner, self.L_cyl
                         a_sph_bkp, a_cyl_bkp, n_tanks_bkp = self.area_sphere, self.area_cyl, self.n_tanks
                         
                         # Test next configuration
                         self.shape, self.r_inner, self.L_cyl = shape_test, r_in_test, L_cyl_test
                         self.area_sphere, self.area_cyl, self.n_tanks = area_sph_test, area_cyl_test, n_tanks_test
                         self.area_inner_tot = self.area_sphere + self.area_cyl
                         self._calculate_structure()
                         gi_next = self.gravimetric_index
                         
                         # Keep current if splitting degrades gravimetric index
                         if gi_cyl >= gi_next:
                             self.shape, self.r_inner, self.L_cyl = shape_bkp, r_in_bkp, L_cyl_bkp
                             self.area_sphere, self.area_cyl, self.n_tanks = a_sph_bkp, a_cyl_bkp, n_tanks_bkp
                             sizing_ok = True
                         else:
                             self.n_tanks = n_tanks_bkp + 1
        
        self.area_inner_tot = self.area_sphere + self.area_cyl

        # --- 4. FINAL STRUCTURAL CALCULATION ---
        self._calculate_structure()
        
        # Final outer dimensions
        t_max_struct = max(self.t_wall_cyl if self.shape == "Cylinder" else 0, self.t_wall_sphere)
        self.r_outer = self.r_inner + t_max_struct + self.insulation_gap + self.t_wall_outer_cyl 
        self.D_outer = 2 * self.r_outer
        
        # Initialize Mission State
        self.m_curr = self.capacity_single
        self.P_curr = self.P_min
        
        self.history = {'t':[], 'P':[], 'm_tot':[], 'Vent':[], 'Q_in':[], 'Alt':[], 
                        'Q_heater':[], 'm_vent_cum':[]}
        self.cum_vented_mass = 0.0

    def _calculate_structure(self):
        """Computes wall thicknesses and total mass based on internal and external loads."""
        min_gauge = 0.0008 # Minimum manufacturing thickness [m]

        # 1. INNER WALL (Vessel) - Svensson Eq. 3
        # 10% overpressure for valves + 2.0x for dynamic flight loads -> P_design = 2.2 * P_max
        P_design_inner = 2.2 * self.P_max

        # Sphere
        t_req_sphere = (P_design_inner * self.r_inner * self.sf_inner) / (2 * self.sigma_y * self.ew)
        self.t_wall_sphere = max(t_req_sphere, min_gauge)
        
        # Cylinder
        if self.shape == "Cylinder":
            t_req_cyl = (P_design_inner * self.r_inner * self.sf_inner) / (1 * self.sigma_y * self.ew)
            self.t_wall_cyl = max(t_req_cyl, min_gauge)
        else:
            self.t_wall_cyl = 0.0
            
        self.mass_inner = (self.area_sphere * self.t_wall_sphere + self.area_cyl * self.t_wall_cyl) * self.rho_al
        
        # 2. OUTER WALL (Vacuum Jacket) - Svensson Eq. 6 & Eq. 7
        # Double design pressure and squared Safety Factor under the root (NASA SP-8007 buckling formula)
        P_design_outer = 2.0 * 101325.0 
        
        t_out_sphere_req = self.r_inner * np.sqrt((P_design_outer * self.sf_outer**2) / (self.buckling_knockdown * self.E_al))
        self.t_wall_outer_sphere = max(t_out_sphere_req, min_gauge)
        
        if self.shape == "Cylinder":
            self.t_wall_outer_cyl = max(t_out_sphere_req * 2.5, min_gauge) 
        else:
            self.t_wall_outer_cyl = self.t_wall_outer_sphere
            
        area_outer_sphere = 4 * np.pi * (self.r_inner + self.insulation_gap)**2
        area_outer_cyl = 2 * np.pi * (self.r_inner + self.insulation_gap) * self.L_cyl
        
        self.mass_outer = (area_outer_sphere * self.t_wall_outer_sphere + area_outer_cyl * self.t_wall_outer_cyl) * self.rho_al
        
        # 3. TOTAL MASSES & INSULATION
        # MLI mass computed via areal density (0.0272 kg/m^2/layer) per Svensson
        self.mass_insulation = self.area_inner_tot * (self.t_foam * self.rho_foam + 0.0272 * self.n_layers_mli) 
        
        structure_mass = self.mass_inner + self.mass_outer
        final_acc_factor = self.accessory_mass_factor
        
        if self.shape == "Cylinder":
            penalty_fixed = 0.15  
            penalty_variable = 0.20 * (self.L_cyl / self.r_inner)
            final_acc_factor += (penalty_fixed + penalty_variable)
            
        self.mass_single_empty = (structure_mass * final_acc_factor) + self.mass_insulation
        self.mass_system_empty = self.mass_single_empty * self.n_tanks
        
        # Gravimetric Index: M_fuel / (M_fuel + M_tank)
        self.gravimetric_index = self.m_tot_capacity / (self.m_tot_capacity + self.mass_system_empty)

    def get_heat_leak(self, T_fluid, T_amb_external):
        """Computes heat ingress through MLI (Multi-Layer Insulation)."""
        T_h = T_amb_external 
        T_c = T_fluid
        N = self.n_layers_mli
        
        term_cond = self.C1 * (self.Nt**self.C2) * (T_h + T_c) * (T_h - T_c) / (2 * (N + 1))
        term_rad = self.C3 * self.eps * (T_h**4.67 - T_c**4.67) / N
        term_gas = self.Cg * (self.p_mli / N) * (T_h**self.ng - T_c**self.ng)
        
        return (term_cond + term_rad + term_gas) * self.area_inner_tot

    def time_step(self, dt, m_dot_req_total, altitude):
        """
        Advances the thermodynamic state of the tank by one time step (dt).
        Handles boil-off, venting, and heater power.
        """
        if self.m_curr <= 1e-3:
            self.m_curr = 0.0
            t_now = self.history['t'][-1] + dt if self.history['t'] else 0
            self.history['t'].append(t_now)
            self.history['P'].append(self.P_curr/1e5)
            self.history['m_tot'].append(0.0)
            self.history['Vent'].append(0.0)
            self.history['Alt'].append(altitude)
            self.history['Q_in'].append(0.0)
            self.history['Q_heater'].append(0.0)
            self.history['m_vent_cum'].append(self.cum_vented_mass)
            return self.P_curr, 0.0, 0.0

        m_dot_fuel = m_dot_req_total / self.n_tanks
        rho_bulk = self.m_curr / self.V_internal
        T_amb, P_amb = get_isa_atmosphere(altitude)
        
        # --- THERMODYNAMIC STATE EVALUATION ---
        try:
            T_sat = CP.PropsSI('T', 'P', self.P_curr, 'Q', 0, self.fluid)
            h_liq = CP.PropsSI('H', 'P', self.P_curr, 'Q', 0, self.fluid)
            h_gas = CP.PropsSI('H', 'P', self.P_curr, 'Q', 1, self.fluid)
            rho_l = CP.PropsSI('D', 'P', self.P_curr, 'Q', 0, self.fluid)
            rho_g = CP.PropsSI('D', 'P', self.P_curr, 'Q', 1, self.fluid)
            
            delta_h = h_gas - h_liq
            rho_star = rho_g / (rho_l - rho_g)
            
            u_bulk = CP.PropsSI('U', 'P', self.P_curr, 'D', rho_bulk, self.fluid)
            dP_eps = 100.0
            u_plus = CP.PropsSI('U', 'P', self.P_curr + dP_eps, 'D', rho_bulk, self.fluid)
            du_dp_rho = (u_plus - u_bulk) / dP_eps
            phi = 1.0 / (rho_bulk * du_dp_rho)
            
        except Exception:
            # Fallback values if CoolProp numerical solver fails for a single timestep
            phi, T_sat = 0.5, 20.0
            h_liq, h_gas = 0, 445000
            delta_h, rho_star = 445000, 0.05

        Q_mli = self.get_heat_leak(T_sat, T_amb)
        
        m_dot_l = m_dot_fuel
        m_dot_g = 0.0
        
        term_heat = 1.3 * Q_mli
        term_mass = delta_h * (rho_star * m_dot_l)
        
        dP_dt = (2.0 * phi / self.V_internal) * (term_heat - term_mass)
        P_next = self.P_curr + dP_dt * dt
        
        Q_heater = 0.0

        # --- PRESSURE REGULATION LOGIC ---
        if P_next < self.P_min:
            # Add heater power to maintain minimum pressure
            dP_missing = (self.P_min - P_next)
            Q_heater = (dP_missing * self.V_internal) / (2.0 * phi * dt)
            if Q_heater < 0: Q_heater = 0
            self.P_curr = self.P_min
            
        elif P_next > self.P_max:
            # Vent gaseous hydrogen to maintain maximum pressure
            self.P_curr = self.P_max
            numerator = 1.3 * Q_mli - (delta_h * rho_star * m_dot_l)
            denominator = delta_h * (1.0 + rho_star)
            if denominator > 0: m_dot_g = numerator / denominator
            if m_dot_g < 0: m_dot_g = 0.0
            
        else:
            self.P_curr = P_next

        # Update mass
        self.m_curr -= (m_dot_l + m_dot_g) * dt
        if self.m_curr < 0: self.m_curr = 0
        
        self.cum_vented_mass += (m_dot_g * dt * self.n_tanks)
        
        # Log History
        t_now = self.history['t'][-1] + dt if self.history['t'] else 0
        self.history['t'].append(t_now)
        self.history['P'].append(self.P_curr/1e5)
        self.history['m_tot'].append(self.m_curr * self.n_tanks)
        self.history['Vent'].append(m_dot_g * self.n_tanks)
        self.history['Alt'].append(altitude)
        self.history['Q_in'].append(Q_mli * self.n_tanks)
        self.history['Q_heater'].append(Q_heater * self.n_tanks)
        self.history['m_vent_cum'].append(self.cum_vented_mass)
        
        return self.P_curr, self.m_curr * self.n_tanks, m_dot_g * self.n_tanks