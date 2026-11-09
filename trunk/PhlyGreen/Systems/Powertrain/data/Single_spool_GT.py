import sys
import os
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
# 3. UNIVERSAL MAP GENERATION
# ==============================================================================
# The map is written for a single reference engine, with reference (unscaled) component
# efficiencies, and stored as a function of the POWER FRACTION (required / available at the
# flight condition), so it applies to any engine size. The size-dependent efficiency scaling
# (get_scaled_efficiency / calibrate_scaling_exponent above) is NOT applied here: it is a
# runtime effect, applied in PhlyGreen.Systems.Powertrain.gas_turbine_surrogate. The two
# helpers above are kept only as the reference implementation reused at runtime.

REF_PWR = 2750.0                                   # reference engine [hp], also the runtime reference
REF_EFF_COMP, REF_EFF_HPT, REF_EFF_LPT = 0.86, 0.885, 0.915
LHV_J_KG = 43e6
LBM_TO_KG = 0.45359237
HP_TO_W = 745.7

# Grid: 4 altitudes x 4 Mach numbers x 5 power fractions (0.3 .. 1.0 of the available power).
ALTITUDES_FT = np.linspace(0, 30000, 4)
MACHS = np.linspace(0.0, 0.6, 4)
POWER_FRACTIONS = np.linspace(0.3, 1.0, 5)

# pyCycle's FlightConditions is singular at MN = 0 exactly (the static-pressure residual takes
# the square root of a negative number and returns NaN, so Newton never moves and FAR stays at
# its initial guess). The "static" column is therefore solved at this small Mach number, and the
# CSV stores the Mach number actually solved.
STATIC_MACH = 0.01

# A point is accepted only if all three off-design balances are closed:
#   delivered shaft power within POWER_TOL of the target,
#   gas-generator shaft net power within POWER_TOL of the target power,
#   nozzle throat area within POWER_TOL of the design throat area.
POWER_TOL = 1e-3


def isa_pressure_ratio(alt_ft):
    """ISA pressure ratio delta = p/p_SL (troposphere, temperature floored at 390 degR)."""
    P_std_sl, T_std_sl = 14.696, 518.67
    T_amb = max(T_std_sl - 3.566e-3 * alt_ft, 390.0)
    P_amb = P_std_sl * (T_amb / T_std_sl) ** 5.2561
    return P_amb / P_std_sl


def run_quietly(prob):
    """run_model without pyCycle/OpenMDAO console output."""
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        prob.run_model()


def read_off_design_state(prob, od, target_hp):
    """Balance variables, delivered power, fuel flow and closure errors of the last solve."""
    delivered_hp = prob.get_val(f'{od}.LP_shaft.pwr_net', units='hp')[0]
    hp_shaft_net = prob.get_val(f'{od}.HP_shaft.pwr_net', units='hp')[0]
    area = prob.get_val(f'{od}.nozz.Throat:stat:area', units='inch**2')[0]
    area_design = prob.get_val(f'{od}.balance.rhs:W', units='inch**2')[0]
    wfuel_kg_s = prob.get_val(f'{od}.perf.Wfuel')[0] * LBM_TO_KG
    state = {
        "W": prob.get_val(f'{od}.balance.W')[0],
        "FAR": prob.get_val(f'{od}.balance.FAR')[0],
        "HP_Nmech": prob.get_val(f'{od}.balance.HP_Nmech')[0],
        "delivered_hp": delivered_hp,
        "wfuel_kg_s": wfuel_kg_s,
        "power_error": abs(delivered_hp - target_hp) / target_hp,
        "hp_shaft_error": abs(hp_shaft_net) / target_hp,
        "area_error": abs(area - area_design) / area_design,
    }
    finite = np.isfinite([state[k] for k in ("W", "FAR", "HP_Nmech", "delivered_hp",
                                            "wfuel_kg_s", "area_error")]).all()
    state["converged"] = bool(finite
                              and state["power_error"] < POWER_TOL
                              and state["hp_shaft_error"] < POWER_TOL
                              and state["area_error"] < POWER_TOL)
    return state


def solve_from_guess(prob, od, alt, mach, target_hp, guess):
    """Set the balance guesses, solve one off-design point and return its state."""
    prob.set_val(f'{od}.balance.W', guess["W"])
    prob.set_val(f'{od}.balance.FAR', guess["FAR"])
    prob.set_val(f'{od}.balance.HP_Nmech', guess["HP_Nmech"])
    prob.set_val(f'{od}.fc.alt', alt, units='ft')
    prob.set_val(f'{od}.fc.MN', mach)
    prob.set_val(f'{od}.balance.pwr_target', target_hp, units='hp')
    try:
        run_quietly(prob)
    except Exception:
        return {"converged": False}
    return read_off_design_state(prob, od, target_hp)


def solve_by_power_continuation(prob, od, alt, mach, start_state, start_hp, target_hp, n_steps):
    """Walk the power target from a converged state to target_hp in n_steps warm-started solves."""
    state, guess = None, start_state
    for p in np.linspace(start_hp, target_hp, n_steps + 1)[1:]:
        state = solve_from_guess(prob, od, alt, mach, p, guess)
        if not state["converged"]:
            return state
        guess = state
    return state


def solve_point(prob, od, alt, mach, target_hp, guesses, continuation_start):
    """Solve one map point, trying each guess in order, then a power continuation.

    ``guesses`` are dicts of balance values (W, FAR, HP_Nmech), typically the converged
    neighbours. ``continuation_start`` is ``(state, power_hp)`` of a converged point at the same
    flight condition, or None. Raises RuntimeError if nothing converges: a map point is never
    written unless the deck delivered the requested power.
    """
    for guess in guesses:
        if guess is None:
            continue
        state = solve_from_guess(prob, od, alt, mach, target_hp, guess)
        if state["converged"]:
            return state
    if continuation_start is not None:
        start_state, start_hp = continuation_start
        for n_steps in (4, 10):
            state = solve_by_power_continuation(prob, od, alt, mach, start_state, start_hp,
                                                target_hp, n_steps)
            if state["converged"]:
                return state
    raise RuntimeError(
        f"Turboshaft deck did not converge at {alt:.0f} ft, Mach {mach:.2f}, "
        f"{target_hp:.1f} hp: no guess or power continuation closed the balances "
        f"(power, gas-generator shaft, nozzle area) within {POWER_TOL:.0e}.")


def generate_map(prob, base_mass_flow):
    """Sweep the grid and return rows [alt, Mach, power fraction, efficiency, target, delivered].

    Each (altitude, Mach) column is solved from full power downwards (full power is closest to
    the design point), each point warm-started from its converged neighbour. The first point of
    a column starts from the full-power point of the previous Mach column (or of the previous
    altitude), so the whole map is reached by continuation from the design point.
    """
    od = prob.model.od_pts[0]
    fresh_guess_at_sl = {"W": base_mass_flow, "FAR": 0.017, "HP_Nmech": 8070.0}
    rows = []
    previous_column_top = None          # converged full-power state of the previous column
    for alt in ALTITUDES_FT:
        delta = isa_pressure_ratio(alt)
        max_pwr_at_alt = REF_PWR * delta          # available power lapses with the ISA pressure ratio
        fresh_guess = {"W": base_mass_flow * delta, "FAR": 0.017, "HP_Nmech": 8070.0}
        for mach in MACHS:
            mach_solved = max(mach, STATIC_MACH)
            previous_in_column = None
            column_top = None
            for fraction in POWER_FRACTIONS[::-1]:
                target_hp = fraction * max_pwr_at_alt
                guesses = [previous_in_column, previous_column_top, fresh_guess, fresh_guess_at_sl]
                continuation_start = None
                if previous_in_column is not None:
                    continuation_start = (previous_in_column, previous_in_column["target_hp"])
                state = solve_point(prob, od, alt, mach_solved, target_hp, guesses,
                                    continuation_start)
                state["target_hp"] = target_hp
                eta = target_hp * HP_TO_W / (state["wfuel_kg_s"] * LHV_J_KG)
                if not 0.05 < eta < 0.6:
                    raise RuntimeError(
                        f"Implausible thermal efficiency {eta:.3f} at {alt:.0f} ft, Mach "
                        f"{mach_solved:.2f}, power fraction {fraction:.3f}.")
                rows.append([alt, mach_solved, fraction, eta, target_hp, state["delivered_hp"]])
                previous_in_column = state
                if column_top is None:
                    column_top = state
                sys.stdout.write(".")
                sys.stdout.flush()
            previous_column_top = column_top
        print(f" | {alt:.0f} ft done")
    # restore the grid order of the original map: altitude, Mach, increasing power fraction
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    return rows


if __name__ == "__main__":
    import os as _os
    _os.environ.setdefault("OPENMDAO_REPORTS", "0")

    prob = om.Problem(reports=False)
    prob.model = MPSingleSpool()
    prob.setup()

    total_start = time.time()
    print("\n" + "=" * 70)
    print(" UNIVERSAL MAP GENERATION (reference engine, unscaled)")
    print("=" * 70)
    print(f"  Reference engine {REF_PWR:.0f} hp; efficiencies comp {REF_EFF_COMP:.3f}, "
          f"HPT {REF_EFF_HPT:.3f}, PT {REF_EFF_LPT:.3f}")

    # Design point: sea-level static, T4 2370 degR, compressor PR 13.5.
    prob.set_val('DESIGN.fc.alt', 0.0, units='ft')
    prob.set_val('DESIGN.fc.MN', 1e-6)
    prob.set_val('DESIGN.balance.T4_target', 2370.0, units='degR')
    prob.set_val('DESIGN.balance.pwr_target', REF_PWR, units='hp')
    prob.set_val('DESIGN.balance.nozz_PR_target', 1.2)
    prob.set_val('DESIGN.comp.PR', 13.5)
    prob.set_val('DESIGN.comp.eff', REF_EFF_COMP)
    prob.set_val('DESIGN.turb.eff', REF_EFF_HPT)
    prob.set_val('DESIGN.pt.eff', REF_EFF_LPT)
    run_quietly(prob)
    design_power = prob.get_val('DESIGN.LP_shaft.pwr_net', units='hp')[0]
    if abs(design_power - REF_PWR) / REF_PWR > POWER_TOL:
        raise RuntimeError(f"Design point did not converge: {design_power:.1f} hp delivered "
                           f"for {REF_PWR:.0f} hp.")
    base_mass_flow = prob.get_val('DESIGN.inlet.Fl_O:stat:W')[0]
    est_weight = EngineWeightCalculator(prob, pt='DESIGN').estimate_weight()
    print(f"  > DESIGN OK. Mass Flow: {base_mass_flow:.2f} lb/s, Weight: {est_weight:.0f} lbs")

    print("  > Mapping performance...")
    training_data = generate_map(prob, base_mass_flow)

    print(f"\nTotal Run Time: {(time.time() - total_start) / 60:.1f} minutes")
    header = "Altitude_ft,Mach,Power,Efficiency,Target_hp,Delivered_hp"
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "GT_Universal_Map.csv")
    np.savetxt(out_path, training_data, delimiter=",", header=header, comments="")
    print(f"SUCCESS: '{out_path}' created ({len(training_data)} universal map points, "
          f"all converged within {POWER_TOL:.0e}).")
