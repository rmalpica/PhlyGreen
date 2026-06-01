import numpy as np

class ElectricMotor:
    """
    High-Fidelity Electric Motor Model (d-q axis).
    Wraps scaling, weight estimation, and efficiency solving into one component.
    """
    def __init__(self, design_kw, design_v, design_rpm):
        self.design_specs = {
            'kw': design_kw, 
            'v': design_v, 
            'rpm': design_rpm
        }
        # Initialize Physics Parameters immediately upon creation
        self.params = self._generate_scaled_params(design_kw, design_v, design_rpm)
        
        # Pre-calculate efficiency at rated point for weight estimation
        # need the rated torque to find the rated efficiency
        w_rated = design_rpm * 2 * np.pi / 60.0
        t_rated = (design_kw * 1000) / w_rated
        self.design_efficiency = self.solve_efficiency(design_rpm, t_rated)
        
    #It starts with a Reference Motor (a known 750 kW motor) and uses scaling laws to create the user's custom motor.
    def _generate_scaled_params(self, P_rated_kw, V_bus, RPM_rated):
        Ref_P, Ref_V, Ref_RPM = 750.0, 800.0, 3000.0
        Ref_R, Ref_L, Ref_Inoload = 0.0012, 0.00015, 20.0
        Ref_Pcore, Ref_Pconst, Ref_Windage = 8000.0, 500.0, 2.5e-6
        
        k_power = P_rated_kw/Ref_P
        k_volt = V_bus/Ref_V
        k_speed = RPM_rated/Ref_RPM

        w_rated = RPM_rated * 2 * np.pi / 60.0
        Kt_new = (V_bus / np.sqrt(3)) * 0.95 / w_rated 
        
        R_new = Ref_R * (k_volt**2) / k_power
        L_new = Ref_L * (k_volt**2) / k_power
        k_torque = k_power / k_speed
        
        return {
            'V_bus': V_bus, 'R_phase': R_new, 'Kt': Kt_new, 'Ld': L_new, 'Lq': L_new,
            'I_no_load': Ref_Inoload * k_torque, 'B_viscous': 0.01 * k_torque, 
            'P_core_rated': Ref_Pcore * k_power, 'rpm_rated': RPM_rated,
            'k_windage': Ref_Windage * k_torque, 'P_const': Ref_Pconst * k_power,
            'T_operating': 100.0
        }

    # This method calculates efficiency for any given speed and torque. It uses the d-q axis frame to simplify the calculation.
    def solve_efficiency(self, rpm, torque, v_bus_override=None):
        """
        Returns efficiency (0.0 - 1.0). Returns 0.05 (safe low value) if impossible.
        """
        # Update Voltage if battery is sagging 
        current_v = v_bus_override if v_bus_override else self.params['V_bus']
        
        T_op = self.params.get('T_operating', 100.0)
        R_hot = self.params['R_phase'] * (1.0 + 0.00393 * (T_op - 20.0))
        V_max = current_v / np.sqrt(3)    
        Kt, Ld, Lq = self.params['Kt'], self.params['Ld'], self.params['Lq']
        
        # Avoid zero division
        omega_rad = max(rpm * 2 * np.pi / 60.0, 1e-5)
        
        T_fric = (self.params['I_no_load'] * Kt) + (self.params['B_viscous'] * omega_rad)
        T_req = torque + T_fric
        
        i_q = T_req / Kt
        i_d = 0.0
        
        lambda_pm = Kt
        flux_sq = (Lq * i_q)**2 + lambda_pm**2
        V_est = omega_rad * np.sqrt(flux_sq)
        
        #High-physics typical of Electric machines...
        # Field Weakening flux limit check
        if V_est > V_max: 
            limit_sq = (V_max / omega_rad)**2
            if limit_sq < (Lq * i_q)**2: 
                return 0.05 # Voltage Saturation (Impossible point)
            i_d = (np.sqrt(limit_sq - (Lq * i_q)**2) - lambda_pm) / Ld
        
        I_mag = np.sqrt(i_q**2 + i_d**2)

        #Estimation of the Power losses inside the motor to correct the calculated efficiency.
        P_copper = 3 * (I_mag**2) * R_hot
        w_rated = self.params['rpm_rated'] * 2 * np.pi / 60.0
        P_core = self.params['P_core_rated'] * (0.5*(omega_rad/w_rated) + 0.5*(omega_rad/w_rated)**2)
        P_wind = self.params['k_windage'] * omega_rad**3
        P_const = self.params['P_const']
        
        total_loss = P_copper + P_core + P_wind + P_const
        P_out = torque * omega_rad
        
        if (P_out + total_loss) <= 0: return 0.05
        return P_out / (P_out + total_loss)

    # This method estimates the weight of the motor based on the torque density and thermal limits. 
    # It calculates both magnetic and thermal mass and returns the larger of the two as the final weight estimate.
    def get_weight(self):
        """
        Estimates motor mass based on torque density and thermal limits.
        """
        P_kw = self.design_specs['kw']
        RPM = self.design_specs['rpm']
        eff = self.design_efficiency # Calculated in __init__

        # Aerospace settings user can change those values with 
        # custom ones if they have better data for their specific design.
        sigma, q_lim = 80000, 110000 
        w = RPM * 2 * np.pi / 60.0
        T = (P_kw * 1000) / w
        
        # Magnetic sizing
        vol_mag = T / (2 * sigma) / (0.6**2)
        mass_mag = vol_mag * 7800 * 1.3
        
        # Thermal sizing
        loss = (P_kw * 1000) * (1 - eff)
        area = loss / q_lim
        d = np.sqrt(area / (2*np.pi)) 
        mass_therm = (np.pi*(d/2)**2 * 1.5*d) * 7800 * 1.3
        
        return max(mass_mag, mass_therm)