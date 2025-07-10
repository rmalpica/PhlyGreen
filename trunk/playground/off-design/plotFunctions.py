import sys
import numpy as np
from scipy.interpolate import griddata
import matplotlib.pyplot as plt
from pathos.multiprocessing import ProcessingPool as Pool
import os
from tqdm import tqdm
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from offDesignFunctions import sim_offdesign_wrapped

image_folder = 'cma_scatter_frames'

def plot_cma_diagnostics(fitness_history,scatter_history,fidelity,id):

    if fitness_history is None: 
        print('NO DATA TO PLOT!')
        return 

    output_dir = f'{image_folder}_{id}_fidelity_{fidelity}' 
    os.makedirs(output_dir, exist_ok=True)

    # Plot convergence
    fig, ax = plt.subplots(figsize=(3.5,3))
    ax.plot(fitness_history)
    ax.grid(visible=True)
    ax.set_xlabel("Generation")
    ax.set_ylabel("Best fitness - Fuel burn [kg]")
    ax.set_ylim([0., 500])
    ax.set_title(f"Fidelity {fidelity} CMA convergence")
    fig.savefig(f'{output_dir}/CMA_fitness.png', dpi=800, transparent=False, bbox_inches='tight')

    all_feasible_fuel = np.concatenate([
        [fuel for _, fuel in points if fuel < 9999]
        for points in scatter_history.values()
    ])
    if len(all_feasible_fuel) == 0:
        vmin, vmax = 0, 500  # Default color range if nothing is feasible
    else:
        vmin = np.min(all_feasible_fuel)
        vmax = np.max(all_feasible_fuel)

    for gen, points in scatter_history.items():
        phi_array = np.array([p[0] for p in points])
        fuel_array = np.array([p[1] for p in points])
    
        feasible_mask = fuel_array < 9999
        infeasible_mask = ~feasible_mask

        fig, ax = plt.subplots(figsize=(4, 3))

        # Plot feasible points with fixed colormap range
        if np.any(feasible_mask):
            sc = ax.scatter(
                phi_array[feasible_mask, 0],
                phi_array[feasible_mask, 1],
                c=fuel_array[feasible_mask],
                cmap='viridis',
                s=80,
                edgecolor='k',
                label='Feasible',
                vmin=vmin,
                vmax=vmax
            )
            plt.colorbar(sc, ax=ax, label='Fuel burn [kg]')

        # Plot unfeasible points as red Xs
        if np.any(infeasible_mask):
            ax.scatter(
                phi_array[infeasible_mask, 0],
                phi_array[infeasible_mask, 1],
                marker='x',
                color='red',
                s=80,
                label='Unfeasible'
            )
    
        ax.set_xlabel(r'$\phi_{\mathrm{CL}}$')
        ax.set_ylabel(r'$\phi_{\mathrm{CR}}$')
        ax.set_xlim([0,1])
        ax.set_ylim([0,1])
        ax.set_title(f'CMA gen {gen}, Battery fidelity {fidelity}')
        ax.grid(True)
        plt.tight_layout()
        plt.savefig(f'{output_dir}/CMA_fidelity_scatter_gen_{gen:03d}.png', dpi=300)
        plt.close()


def plot_fuel_contour(aircraft, typical_range, payload, fidelity, resolution=40):

    soc_min = aircraft.battery.SOC_min
    # Grid of phi_CL and phi_CRZ
    phi_CL_vals = np.linspace(0.0, 1.0, resolution)
    phi_CRZ_vals = np.linspace(0.0, 1.0, resolution)

    args_list = []
    for phi_CRZ in phi_CRZ_vals:
        for phi_CL in phi_CL_vals:
            phi_vec = [phi_CL, phi_CRZ]
            args_list.append((phi_vec, aircraft, typical_range, payload, fidelity, soc_min))

    print(f"Launching parallel contour simulation with {len(args_list)} cases...")

    # Run with progress bar
    with Pool() as pool:
        results = list(tqdm(pool.imap(sim_offdesign_wrapped, args_list), total=len(args_list), desc="Evaluating grid"))

    # Extract results
    fuel_vals = np.array([r[3] for r in results]).reshape((resolution, resolution))
    feasible_mask = np.array([r[2] for r in results]).reshape((resolution, resolution))

    # Optional: mask infeasible points
    fuel_vals_masked = np.where(feasible_mask, fuel_vals, np.nan)

    # Plot
    X, Y = np.meshgrid(phi_CL_vals, phi_CRZ_vals)
    fig, ax = plt.subplots(figsize=(6, 5))
    levels = np.linspace(np.nanmin(fuel_vals_masked), np.nanmax(fuel_vals_masked), 20)
    contour = ax.contourf(X, Y, fuel_vals_masked, levels=levels, cmap='viridis')
    plt.colorbar(contour, label="Fuel burn [kg]")

    # Optional: outline feasibility
    ax.contour(X, Y, feasible_mask, levels=[0.5], colors='red', linestyles='dashed', linewidths=1)
    ax.set_xlabel("phi_CL")
    ax.set_ylabel("phi_CRZ")
    ax.set_title(f"Fuel Burn Contour (Class {fidelity})")
    ax.grid(True)
    plt.tight_layout()
    plt.savefig(f"fuel_contour_fidelity_{fidelity}.png", dpi=300)



def plot_adaptive_fuel_contour(evaluated_points, fuel_vals, feasible_mask, fidelity="I", resolution=100):
    """
    Plots a fuel burn contour using interpolated data from a coarse-to-fine adaptive evaluation.
    """
    evaluated_points = np.array(evaluated_points)
    fuel_vals = np.array(fuel_vals)
    feasible_mask = np.array(feasible_mask)

    # Filter feasible data
    feasible_points = evaluated_points[feasible_mask]
    feasible_fuels = fuel_vals[feasible_mask]

    if len(feasible_points) == 0:
        print("No feasible points to plot.")
        return

    # Define regular grid
    grid_x, grid_y = np.linspace(0, 1, resolution), np.linspace(0, 1, resolution)
    X, Y = np.meshgrid(grid_x, grid_y)

    # Interpolate fuel values (only feasible points)
    Z = griddata(feasible_points, feasible_fuels, (X, Y), method='linear')

    # Plot
    fig, ax = plt.subplots(figsize=(6, 5))
    levels = np.linspace(np.nanmin(Z), np.nanmax(Z), 20)
    contour = ax.contourf(X, Y, Z, levels=levels, cmap='viridis')
    cbar = plt.colorbar(contour, label="Fuel burn [kg]")

    # Optional: scatter the actual evaluated points
    ax.scatter(evaluated_points[:, 0], evaluated_points[:, 1], c='black', s=10, alpha=0.2, label='Evaluated Points')
    ax.scatter(feasible_points[:, 0], feasible_points[:, 1], c='white', s=20, edgecolors='k', label='Feasible Points')

    ax.set_xlabel("phi_CL")
    ax.set_ylabel("phi_CRZ")
    ax.set_title(f"Fuel Burn Contour (Fidelity {fidelity}) - Adaptive")
    ax.legend()
    ax.grid(True)
    plt.tight_layout()
    plt.savefig(f"fuel_contour_adaptive_fidelity_{fidelity}.png", dpi=300)