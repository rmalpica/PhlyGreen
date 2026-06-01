import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm
from scipy.interpolate import Rbf
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score
import pickle

# =========================================================
# 1. HELPER: PHYSICS-BASED WEIGHT ESTIMATOR
# =========================================================
# This adapts your original 'EngineWeightCalculator' class 
# to work with just Design Power.
def calculate_physics_weight(design_hp):
    # --- 1. Approximations for Cycle Params ---
    # Specific Power ~145 hp/(lb/s) is typical for modern small turboshafts
    W_air = design_hp / 145.0  
    
    # OPR usually scales slightly with size, but 14-16 is standard for this class
    OPR = 15.0 
    
    # --- 2. Your WATE++ Correlations ---
    w_comp   = 10.5 * (W_air**0.8) * (OPR**0.4) 
    w_burner = 4.5  * (W_air**0.9) * (OPR**0.15)
    w_hpt    = 14.5 * (W_air**0.85) * 2 * 0.8 
    w_pt     = 13.0 * (W_air**0.85) * 2
    w_acc    = 35.0 + 1.2 * W_air
    
    # Estimate structure/shafts as 15% of core components
    core_weight = w_comp + w_burner + w_hpt + w_pt
    w_structure = core_weight * 0.15 
    
    w_dry_engine = core_weight + w_structure + w_acc
    
    # Your original 10% growth margin
    return w_dry_engine * 1.10

# =========================================================
# 2. LOAD DATA
# =========================================================
filename = 'GT_Universal_Map.csv'
try:
    df = pd.read_csv(filename)
    print(f"Successfully loaded {filename}")
except FileNotFoundError:
    print(f"Error: {filename} not found.")
    exit()

# =========================================================
# 3. TRAIN BRAIN 1: EFFICIENCY MODEL
# =========================================================
print("Training Efficiency Model...")
X_raw = df[['Design_Power_hp', 'Altitude_ft', 'Mach', 'Actual_Power_hp']].values  #inputs
y_eff = df['Efficiency'].values #output

scaler_eff = StandardScaler()
X_scaled = scaler_eff.fit_transform(X_raw)

rbf_efficiency = Rbf(
    X_scaled[:, 0], X_scaled[:, 1], X_scaled[:, 2], X_scaled[:, 3], 
    y_eff,
    function='linear', # Prevents overshoot
    smooth=0
)

# =========================================================
# 4. TRAIN BRAIN 2: POWER LIMIT MODEL
# =========================================================
#Engines lose power at high altitudes. This section trains the AI to know those limits.
print("Training Power Limit Model...")
limits_df = df.groupby(['Design_Power_hp', 'Altitude_ft', 'Mach'])['Actual_Power_hp'].max().reset_index()
limits_df.columns = ['Design_Power_hp', 'Altitude_ft', 'Mach', 'Max_Available_Power']

X_lim_raw = limits_df[['Design_Power_hp', 'Altitude_ft', 'Mach']].values
y_lim = limits_df['Max_Available_Power'].values

scaler_lim = StandardScaler()
X_lim_scaled = scaler_lim.fit_transform(X_lim_raw)

rbf_limit = Rbf(
    X_lim_scaled[:, 0], X_lim_scaled[:, 1], X_lim_scaled[:, 2], 
    y_lim,
    function='linear', 
    smooth=0
)

# =========================================================
# 5. TRAIN BRAIN 3: WEIGHT MODEL (NEW)
# =========================================================
print("Training Weight Model...")

# Generate "Truth" data using physics function
weight_df = df[['Design_Power_hp']].drop_duplicates().sort_values(by='Design_Power_hp')
weight_df['Calculated_Weight'] = weight_df['Design_Power_hp'].apply(calculate_physics_weight)

X_wt_raw = weight_df[['Design_Power_hp']].values
y_wt = weight_df['Calculated_Weight'].values

scaler_wt = StandardScaler()
X_wt_scaled = scaler_wt.fit_transform(X_wt_raw) 

rbf_weight = Rbf(
    X_wt_scaled[:, 0], 
    y_wt,
    function='cubic', # Cubic smooths the weight curve nicely
    smooth=0
)

# =========================================================
# 6. SMART PREDICTION FUNCTION (UPDATED)
# =========================================================
def get_engine_performance(design_hp, altitude, mach, actual_hp):
    # --- A. CHECK PHYSICAL POWER LIMITS ---
    lim_input_scaled = scaler_lim.transform([[design_hp, altitude, mach]])
    max_possible = rbf_limit(lim_input_scaled[0,0], lim_input_scaled[0,1], lim_input_scaled[0,2])
    
    used_power = actual_hp
    limit_hit = False
    
    if actual_hp > max_possible:
        used_power = float(max_possible)
        limit_hit = True
        
    # --- B. PREDICT EFFICIENCY ---
    eff_input_scaled = scaler_eff.transform([[design_hp, altitude, mach, used_power]])
    eff = rbf_efficiency(
        eff_input_scaled[0,0], eff_input_scaled[0,1], eff_input_scaled[0,2], eff_input_scaled[0,3]
    )
    
    # Clamp Efficiency
    final_eff = float(eff)
    if final_eff > 0.45: final_eff = 0.45
    if final_eff < 0.01: final_eff = 0.01
    
    # --- C. PREDICT WEIGHT (NEW) ---
    wt_input_scaled = scaler_wt.transform([[design_hp]])
    est_weight = rbf_weight(wt_input_scaled[0,0])
    
    return final_eff, limit_hit, float(max_possible), float(est_weight)

# =========================================================
# 7. VISUALIZATION: WEIGHT CURVE
# =========================================================
print("Generating Weight Curve...")
plt.figure(figsize=(8, 5))

# Plot the training points (from our estimator)
plt.scatter(weight_df['Design_Power_hp'], weight_df['Calculated_Weight'], color='black', label='Physics Points')

# Plot the RBF fit
x_smooth = np.linspace(weight_df['Design_Power_hp'].min(), weight_df['Design_Power_hp'].max(), 100)
x_smooth_scaled = scaler_wt.transform(x_smooth.reshape(-1, 1))
y_smooth = [rbf_weight(val) for val in x_smooth_scaled]

plt.plot(x_smooth, y_smooth, color='green', linestyle='--', linewidth=2, label='RBF Weight Model')
plt.title('Engine Weight vs Design Power')
plt.xlabel('Design Power (hp)')
plt.ylabel('Dry Weight (lbs)')
plt.grid(True)
plt.legend()
plt.show()

# =========================================================
# 8. MANUAL TEST (UPDATED PRINT)
# =========================================================
print("\n--- MANUAL TEST ---")
my_design_hp   = 2750    
my_altitude    = 0   
my_mach        = 0.2     
my_power       = 500   

eff, limited, limit_val, weight = get_engine_performance(my_design_hp, my_altitude, my_mach, my_power)

print(f"INPUTS:")
print(f"  > Design Power: {my_design_hp} hp")
print(f"  > Altitude:     {my_altitude} ft")
print(f"  > Mach:         {my_mach}")
print(f"  > Req Power:    {my_power} hp")

print("-" * 30)
print(f"RESULTS:")
print(f"  > Engine Weight:    {weight:.1f} lbs")
print(f"  > Max Power Avail:  {limit_val:.1f} hp")
print(f"  > Efficiency:       {eff:.4f}")

if limited: 
    print("  > ⚠️ WARNING: Power limited by altitude/mach!")

# =========================================================
# 9. SAVE EVERYTHING
# =========================================================
full_model_package = {
    "scaler_eff": scaler_eff, "model_eff": rbf_efficiency,
    "scaler_lim": scaler_lim, "model_lim": rbf_limit,
    "scaler_wt":  scaler_wt,  "model_wt":  rbf_weight
}

model_filename = 'GT_Engine_Model_Complete.pkl'
with open(model_filename, 'wb') as f:
    pickle.dump(full_model_package, f)
print(f"\nSUCCESS: Full Model (Eff + Limits + Weight) saved to '{model_filename}'")