import numpy as np
import pandas as pd
import itertools
from Propeller_System import PropellerSystem  # Import your physics class

# This script generates a comprehensive CSV map of propeller performance across a wide range of altitudes, speeds, and power levels.
# The CVS map will later be used to train a surrogate model like it was done for the GT engine.
def generate_propeller_map():
    # SETUP THE PHYSICS MODEL
    specs = {
        'diameter': 3.93,
        'n_blades': 6,
        'activity_factor': 120,
        'cli': 0.5,
        'n_engines': 2
    }
    prop_system = PropellerSystem(specs)

    # 2. DEFINE THE GRID 
    # Chosen big ranges in order to cover all mission phases.
    
    # Altitude: 0 to 10,000m
    alts = np.linspace(0, 10000, 10) 
    
    # Speed: 10 m/s (taxi/takeoff) to 180 m/s (dive)
    vels = np.linspace(10, 180, 10)
    
    # Power: 50kW (idle) to 2.5MW (max takeoff)
    powers = np.linspace(50000, 2500000, 10)

    print(f"Generating Map: {len(alts)} x {len(vels)} x {len(powers)} = {len(alts)*len(vels)*len(powers)} points.")

    data_rows = []

    # RUN THE SWEEP
    total_points = len(alts) * len(vels) * len(powers)
    counter = 0

    # itertools.product calculates the Cartesian product of the three arrays,
    # it creates every single possible combination of Altitude, Velocity, and Power. This was done
    # to take into account all the possible operative points of the propeller during a mission.
    for alt, vel, pwr in itertools.product(alts, vels, powers):
        counter += 1
        if counter % 500 == 0:
            print(f"Processing point {counter}/{total_points}...")

        # Run the solver
        res = prop_system.solve_operating_point(alt, vel, pwr, flight_phase="FLIGHT")

        if res:
            # Success
            row = {
                "Altitude": alt,
                "Velocity": vel,
                "Power": pwr,
                "RPM": res['rpm'],
                "Pitch": res['pitch'],
                "Efficiency": res['eta_real'],
                "ViscousLoss": res['power_loss_viscous']
            }
        else:
            #Not every combination on the grid is physically possible in a real mission.
            # When thesolver failes (physically impossible state, e.g., huge power at 0 speed)
            # records zeros/NaNs so the interpolator knows it's a "bad" zone. This was done without making the run crash...
            row = {
                "Altitude": alt,
                "Velocity": vel,
                "Power": pwr,
                "RPM": 0,
                "Pitch": 0,
                "Efficiency": 0.0, # Zero efficiency in failure zones
                "ViscousLoss": 0
            }
        
        data_rows.append(row)

    # 4. SAVE TO CSV to create a dataset that will be used to train a surorgate model for the propeller.
    df = pd.DataFrame(data_rows)
    df.to_csv("propeller_data_rbf.csv", index=False)
    print("✅ Database generated: propeller_data_rbf.csv")

if __name__ == "__main__":
    generate_propeller_map()