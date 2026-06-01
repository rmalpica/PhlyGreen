import sys
import numpy as np
import openmdao.api as om
import pycycle.api as pyc
import time
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt

# ==============================================================================
# 1. SCALING LOGIC & CALIBRATION 
# ==============================================================================
def get_scaled_efficiency(target_pwr, ref_pwr, ref_eff, n):
    """
    Scales component efficiency based on the size (Power) of the engine.
    Smaller Engine (500 HP) = Lower Efficiency.
    Formula: (1 - eta_new) = (1 - eta_ref) * (Power_ref / Power_new)^n
    """
    if target_pwr <= 0: return ref_eff
    
    # Calculate Loss Scaling Factor
    loss_factor = (ref_pwr / target_pwr) ** n
    
    # Apply to reference losses
    ref_loss = 1.0 - ref_eff
    target_loss = ref_loss * loss_factor
    
    return 1.0 - target_loss

def calibrate_scaling_exponent():
    """
    Runs the Least Squares Fit on real engine data to find the best 'n'.
    Returns: best_n (float)
    """
    print("\n" + "="*60)
    print(" 1. CALIBRATING SCALING EXPONENT (n) FROM REAL DATA")
    print("="*60)

    # REAL ENGINE DATA i took from jet_engine.net.
    # [Power (shp), SFC (lb/hp-hr)]
    data = np.array([
        [420,  0.650],  # Allison 250-C20B
        [650,  0.592],  # Allison 250-C30
        [730,  0.580],  # Turbomeca Arriel 1D1
        [1000, 0.550],  # Representative 1000hp class
        [1200, 0.540],  # P&WC PT6A-60 series
        [1700, 0.480],  # GE CT7-7A
        [2500, 0.460],  # GE T700 / CT7-8 (OUR REFERENCE)
        [4500, 0.430],  # GE T64 / AE2100 Class
        [5500, 0.640],  #Soloviev 	D-25V
    ])

    powers_shp = data[:, 0]
    sfc_data   = data[:, 1]

    # CONVERSION: SFC -> EFFICIENCY -> LOSS
    LHV_BTU_lb = 18400.0 
    eta_real = 2544.43 / (sfc_data * LHV_BTU_lb)
    loss_real = 1.0 - eta_real

    # DEFINE REFERENCE ENGINE (2500 HP one) 
    REF_IDX = 6 
    REF_PWR = powers_shp[REF_IDX]
    REF_LOSS = loss_real[REF_IDX]

    def scaling_model(pwr, n):
        return REF_LOSS * (REF_PWR / pwr) ** n

    # OPTIMIZATION
    popt, pcov = curve_fit(scaling_model, powers_shp, loss_real, p0=[0.15])
    best_n = popt[0]

    # PRINT RESULTS
    print(f"Reference Engine: {REF_PWR:.0f} HP")
    print(f"Calculated Best Fit Exponent (n): {best_n:.5f}")
    print("-" * 60)
    print(f"{'Power (hp)':<12} | {'Real Eff':<10} | {'Model Eff':<10} | {'Error'}")
    print("-" * 50)

    model_losses = scaling_model(powers_shp, best_n)
    model_etas   = 1.0 - model_losses

    for i in range(len(powers_shp)):
        err = eta_real[i] - model_etas[i]
        print(f"{powers_shp[i]:<12.0f} | {eta_real[i]:<10.3f} | {model_etas[i]:<10.3f} | {err:+.4f}")
    
    print("-" * 60)
    return best_n


# ==============================================================================
# 2. OPENMDAO/PYCYCLE CLASSES 
# ==============================================================================
# This is the PyCycle code for modelling a GT engine. I made to it some adjectments to add 
# more physics typical of this type of engines.
# --- Utility function to enforce mole fraction bounds ---
def enforce_n_bounds(n):
    floor_value = 1e-12
    return np.maximum(n, floor_value)

# --- Single Spool Turboshaft Cycle ---
class SingleSpoolTurboshaft(pyc.Cycle):

    def setup(self):
        design = self.options['design']
        
        # Standard Thermodynamics
        self.options['thermo_method'] = 'CEA'
        self.options['thermo_data'] = pyc.species_data.janaf
        FUEL_TYPE = 'JP-7'
    
        # Add engine elements
        self.add_subsystem('fc', pyc.FlightConditions())
        self.add_subsystem('inlet', pyc.Inlet())
        self.add_subsystem('comp', pyc.Compressor(map_data=pyc.AXI5, map_extrap=True),
                                    promotes_inputs=[('Nmech', 'HP_Nmech')])
        self.add_subsystem('burner', pyc.Combustor(fuel_type=FUEL_TYPE))
        self.add_subsystem('turb', pyc.Turbine(map_data=pyc.LPT2269, map_extrap=True),
                                    promotes_inputs=[('Nmech', 'HP_Nmech')])
        self.add_subsystem('pt', pyc.Turbine(map_data=pyc.LPT2269, map_extrap=True),
                                    promotes_inputs=[('Nmech', 'LP_Nmech')])
        self.add_subsystem('nozz', pyc.Nozzle(nozzType='CV', lossCoef='Cv'))
        self.add_subsystem('HP_shaft', pyc.Shaft(num_ports=2), promotes_inputs=[('Nmech', 'HP_Nmech')])
        self.add_subsystem('LP_shaft', pyc.Shaft(num_ports=1), promotes_inputs=[('Nmech', 'LP_Nmech')])
        self.add_subsystem('perf', pyc.Performance(num_nozzles=1, num_burners=1))

        # Connect flow stations
        self.pyc_connect_flow('fc.Fl_O', 'inlet.Fl_I', connect_w=False)
        self.pyc_connect_flow('inlet.Fl_O', 'comp.Fl_I')
        self.pyc_connect_flow('comp.Fl_O', 'burner.Fl_I')
        self.pyc_connect_flow('burner.Fl_O', 'turb.Fl_I')
        self.pyc_connect_flow('turb.Fl_O', 'pt.Fl_I')
        self.pyc_connect_flow('pt.Fl_O', 'nozz.Fl_I')

        # Connect turbomachinery elements to shaft
        self.connect('comp.trq', 'HP_shaft.trq_0')
        self.connect('turb.trq', 'HP_shaft.trq_1')
        self.connect('pt.trq', 'LP_shaft.trq_0')

        # Connect nozzle exhaust to freestream static conditions
        self.connect('fc.Fl_O:stat:P', 'nozz.Ps_exhaust')

        # Connect outputs to performance element
        self.connect('inlet.Fl_O:tot:P', 'perf.Pt2')
        self.connect('comp.Fl_O:tot:P', 'perf.Pt3')
        self.connect('burner.Wfuel', 'perf.Wfuel_0')
        self.connect('inlet.F_ram', 'perf.ram_drag')
        self.connect('nozz.Fg', 'perf.Fg_0')
        self.connect('LP_shaft.pwr_net', 'perf.power')

        # Add balances for design and off-design
        balance = self.add_subsystem('balance', om.BalanceComp())
        if design:
            balance.add_balance('W', val=27.0, units='lbm/s', eq_units=None, rhs_name='nozz_PR_target')
            self.connect('balance.W', 'inlet.Fl_I:stat:W')
            self.connect('nozz.PR', 'balance.lhs:W')

            balance.add_balance('FAR', eq_units='degR', lower=1e-4, val=.017, rhs_name='T4_target')
            self.connect('balance.FAR', 'burner.Fl_I:FAR')
            self.connect('burner.Fl_O:tot:T', 'balance.lhs:FAR')

            # Widen bounds slightly to ensure convergence
            balance.add_balance('turb_PR', val=3.0, lower=1.001, upper=10, eq_units='hp', rhs_val=0.)
            self.connect('balance.turb_PR', 'turb.PR')
            self.connect('HP_shaft.pwr_net', 'balance.lhs:turb_PR')

            balance.add_balance('pt_PR', val=3.0, lower=1.001, upper=10, eq_units='hp', rhs_name='pwr_target')
            self.connect('balance.pt_PR', 'pt.PR')
            self.connect('LP_shaft.pwr_net', 'balance.lhs:pt_PR')

        else:
            # OFF-DESIGN BALANCES
            balance.add_balance('FAR', eq_units='hp', lower=1e-4, val=.017, rhs_name='pwr_target')
            self.connect('balance.FAR', 'burner.Fl_I:FAR')
            self.connect('LP_shaft.pwr_net', 'balance.lhs:FAR')

            balance.add_balance('HP_Nmech', val=8000.0, units='rpm', lower=500., eq_units='hp', rhs_val=0.)
            self.connect('balance.HP_Nmech', 'HP_Nmech')
            self.connect('HP_shaft.pwr_net', 'balance.lhs:HP_Nmech')

            balance.add_balance('W', val=27.0, units='lbm/s', eq_units='inch**2')
            self.connect('balance.W', 'inlet.Fl_I:stat:W')
            self.connect('nozz.Throat:stat:area', 'balance.lhs:W')

        # Setup solver
        self.set_order(['fc', 'inlet', 'comp', 'burner', 'turb', 'pt', 'nozz', 'HP_shaft', 'LP_shaft', 'perf', 'balance'])

        newton = self.nonlinear_solver = om.NewtonSolver()
        newton.options['atol'] = 1e-3
        newton.options['rtol'] = 1e-3
        newton.options['iprint'] = 0 
        newton.options['maxiter'] = 25
        newton.options['solve_subsystems'] = True
        newton.options['max_sub_solves'] = 100
        newton.options['reraise_child_analysiserror'] = False

        newton.linesearch = om.ArmijoGoldsteinLS()
        newton.linesearch.options['iprint'] = -1
        newton.linesearch.options['maxiter'] = 5
        newton.linesearch.options['rho'] = 0.75
        newton.linesearch.options['print_bound_enforce'] = False

        self.linear_solver = om.DirectSolver()

        super().setup()

        # CEA Stability Hack
        try:
            chem_eq = self.pt.out_stat.base_thermo.chem_eq
            chem_eq.n = enforce_n_bounds(chem_eq.n)
        except Exception:
            pass

# Multi-Point Setup 
class MPSingleSpool(pyc.MPCycle):

    def setup(self):
        # Design Point
        self.pyc_add_pnt('DESIGN', SingleSpoolTurboshaft(thermo_method='CEA'))

        self.set_input_defaults('DESIGN.HP_Nmech', 8070.0, units='rpm')
        self.set_input_defaults('DESIGN.LP_Nmech', 5000.0, units='rpm')
        self.set_input_defaults('DESIGN.fc.MN', 0.6)
        self.set_input_defaults('DESIGN.comp.MN', 0.2)
        self.set_input_defaults('DESIGN.burner.MN', 0.2)
        self.set_input_defaults('DESIGN.turb.MN', 0.4)

        self.pyc_add_cycle_param('burner.dPqP', .03)
        self.pyc_add_cycle_param('nozz.Cv', 0.99)

        # Off-design point (placeholder used for the loop)
        self.od_pts = ['OD'] 
        self.od_MNs = [0.1]
        self.od_alts =[0.0]
        self.od_pwrs =[3500.0]
        self.od_nmechs =[5000.]

        for i, pt in enumerate(self.od_pts):
            self.pyc_add_pnt(pt, SingleSpoolTurboshaft(design=False, thermo_method='CEA'))
            self.set_input_defaults(pt+'.fc.alt', self.od_alts[i], units='ft')
            self.set_input_defaults(pt+'.fc.MN', self.od_MNs[i])
            self.set_input_defaults(pt+'.LP_Nmech', self.od_nmechs[i], units='rpm')
            self.set_input_defaults(pt+'.balance.pwr_target', self.od_pwrs[i], units='hp')

        self.pyc_use_default_des_od_conns()
        self.pyc_connect_des_od('nozz.Throat:stat:area', 'balance.rhs:W')

        super().setup()

# Engine Weight Calculator
class EngineWeightCalculator:
    def __init__(self, prob, pt='DESIGN'):
        self.prob = prob
        self.pt = pt
        
    def get_val(self, path):
        return self.prob.get_val(f'{self.pt}.{path}')[0]

    def estimate_weight(self):
        # Cycle Parameters
        try:
            W_air = self.get_val('inlet.Fl_O:stat:W')
            OPR = self.get_val('perf.OPR')
            HP_trq = abs(self.get_val('HP_shaft.trq_0')) 
            LP_trq = abs(self.get_val('LP_shaft.trq_0'))
        except Exception:
            return 0.0
        
        # WATE++ Style Correlations
        comp_stages = np.ceil(np.log(OPR) / np.log(1.35)) 
        w_comp = 10.5 * (W_air**0.8) * (OPR**0.4) 
        w_burner = 4.5 * (W_air**0.9) * (OPR**0.15)
        w_hpt = 14.5 * (W_air**0.85) * 2 * 0.8 
        w_pt = 13.0 * (W_air**0.85) * 2
        w_shafts = 0.035 * HP_trq**0.6 + 0.05 * LP_trq**0.6
        w_acc = 35.0 + 1.2 * W_air
        
        w_dry_engine = w_comp + w_burner + w_hpt + w_pt + w_shafts + w_acc
        return w_dry_engine * 1.10

# ==============================================================================
# 3. MAIN EXECUTION
# ==============================================================================
if __name__ == "__main__":

    # ------------------------------------------------------------------
    # STEP 1: CALIBRATE THE SCALING EXPONENT
    # ------------------------------------------------------------------
    CALIBRATED_N = calibrate_scaling_exponent()
    
    # Pause briefly so user can read the calibration table
    time.sleep(2)

    # ------------------------------------------------------------------
    # STEP 2: SETUP PYCYCLE
    # ------------------------------------------------------------------
    prob = om.Problem()
    prob.model = mp_single_spool = MPSingleSpool()
    prob.setup()

    # ------------------------------------------------------------------
    # STEP 3: RUN THE UNIVERSAL GRID (Using the Calibrated N)
    # ------------------------------------------------------------------
    # This part is used for the creation of the CSV map that will be used later to train the surrogate model.
    # Here the user can define any range of powers to run PyCycle codes for each design point.
    design_powers_to_run = [500.0, 2750.0, 6000.0] 

    # Reference Constants (ATR-72 Class Baseline)
    REF_PWR = 2750.0  
    REF_EFF_COMP, REF_EFF_HPT, REF_EFF_LPT = 0.86, 0.885, 0.915
    
    # Storage for CSV file.
    training_data = [] 
    
    total_start = time.time()
    
    print("\n" + "="*70)
    print(" 2. STARTING UNIVERSAL MAP GENERATION")
    print(f"    Using Calibrated Scaling Exponent n = {CALIBRATED_N:.4f}")
    print("="*70)

    # LOOP: ENGINE SIZING
    for des_pwr in design_powers_to_run:
        print(f"\n--- SIZING ENGINE: {des_pwr:.0f} HP ---")

        # A. SCALE EFFICIENCIES USING CALIBRATED N
        scaled_comp_eff = get_scaled_efficiency(des_pwr, REF_PWR, REF_EFF_COMP, n=CALIBRATED_N)
        scaled_hpt_eff  = get_scaled_efficiency(des_pwr, REF_PWR, REF_EFF_HPT, n=CALIBRATED_N)
        scaled_lpt_eff  = get_scaled_efficiency(des_pwr, REF_PWR, REF_EFF_LPT, n=CALIBRATED_N)
        
        print(f"  Efficiencies -> Comp: {scaled_comp_eff:.3f}, HPT: {scaled_hpt_eff:.3f}, LPT: {scaled_lpt_eff:.3f}")

        # B. SET DESIGN INPUTS
        prob.set_val('DESIGN.fc.alt', 0.0, units='ft')
        prob.set_val('DESIGN.fc.MN', 1e-6)
        prob.set_val('DESIGN.balance.T4_target', 2370.0, units='degR')
        prob.set_val('DESIGN.balance.pwr_target', des_pwr, units='hp')
        prob.set_val('DESIGN.balance.nozz_PR_target', 1.2)
        prob.set_val('DESIGN.comp.PR', 13.5)
        prob.set_val('DESIGN.comp.eff', scaled_comp_eff)
        prob.set_val('DESIGN.turb.eff', scaled_hpt_eff)
        prob.set_val('DESIGN.pt.eff', scaled_lpt_eff)

        # C. RUN DESIGN POINT
        try:
            prob.run_model()
            
            # Get Sizing Info
            base_mass_flow = prob.get_val('DESIGN.inlet.Fl_O:stat:W')[0]
            weight_calc = EngineWeightCalculator(prob, pt='DESIGN')
            est_weight = weight_calc.estimate_weight()
            
            print(f"  > DESIGN OK. Mass Flow: {base_mass_flow:.2f} lb/s, Weight: {est_weight:.0f} lbs")
            
        except Exception:
            print(f"  > DESIGN FAILED for {des_pwr} HP. Skipping.")
            continue

        # D. OFF-DESIGN MAPPING
        od = mp_single_spool.od_pts[0]
        
        # Grid: 4 Altitudes, 4 Machs. The user can change those ranges and densities as they wish to create a custom map for their specific use case.
        alts = np.linspace(0, 30000, 4)   
        machs = np.linspace(0.0, 0.6, 4)  
        
        print(f"  > Mapping performance...")
        
        for alt in alts:
            # Atmosphere (Standard)
            P_std_sl, T_std_sl = 14.696, 518.67
            T_amb = T_std_sl - 3.566e-3 * alt
            if T_amb < 390.0: T_amb = 390.0
            P_amb = P_std_sl * (T_amb / T_std_sl)**5.2561
            delta = P_amb / P_std_sl

            # Max power decreases with altitude
            max_pwr_at_alt = des_pwr * delta
            
            # Idle ~30%
            current_powers = np.linspace(max_pwr_at_alt*0.3, max_pwr_at_alt, 5) 
            guess_W = base_mass_flow * delta

            for mach in machs:
                # Reset Guesses
                prob.set_val(f'{od}.balance.W', guess_W)
                prob.set_val(f'{od}.balance.FAR', 0.017)
                prob.set_val(f'{od}.balance.HP_Nmech', 5000.0)

                for pwr in current_powers:
                    prob.set_val(f'{od}.fc.alt', alt, units='ft')
                    prob.set_val(f'{od}.fc.MN', mach)
                    prob.set_val(f'{od}.balance.pwr_target', pwr, units='hp')

                    try:
                        prob.run_model()
                        
                        Wfuel = prob.get_val(f'{od}.perf.Wfuel')[0]
                        P_out_watts = pwr * 745.7 
                        eta = P_out_watts / (max(Wfuel, 1e-6) * 0.45359237 * 43e6)
                        
                        if 0.05 < eta < 0.6:
                            training_data.append([des_pwr, alt, mach, pwr, eta])
                            sys.stdout.write(".")
                        else:
                            sys.stdout.write("x") 
                    except:
                        sys.stdout.write("F") 
                    sys.stdout.flush()
            print(f" | {alt:.0f} ft done")

    # SAVE DATA 
    print(f"\nTotal Run Time: {(time.time()-total_start)/60:.1f} minutes")
    
    header = "Design_Power_hp,Altitude_ft,Mach,Actual_Power_hp,Efficiency"
    np.savetxt("GT_Universal_Map.csv", training_data, delimiter=",", header=header, comments="")
    
    print("\nSUCCESS: 'GT_Universal_Map.csv' created.")