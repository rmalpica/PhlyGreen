import sys
import numpy as np
import cma
from collections import defaultdict
from pathos.multiprocessing import ProcessingPool as Pool
import os
from tqdm import tqdm
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
from offDesignFunctions import sim_offdesign_wrapped
from plotFunctions import plot_adaptive_fuel_contour 

def coarse_to_fine_parallel_search(aircraft, typical_range, payload, fidelity='I', soc_min=0.2, 
                                    total_budget=200, coarse_points=10, fine_points=10, fine_delta=0.1):
    """
    Hierarchical grid search with parallel evaluation and coarse-to-fine refinement.

    Returns:
        best_phi (np.array): Optimal design point [phi_CL, phi_CRZ]
        best_fuel (float): Corresponding fuel burn
    """

    def make_args(grid_phi):
        return [(phi, aircraft, typical_range, payload, fidelity, soc_min) for phi in grid_phi]

    # Step 1: Coarse grid over full [0, 1] domain
    phi_vals = np.linspace(0, 1, coarse_points)
    grid_coarse = np.array([[cl, crz] for cl in phi_vals for crz in phi_vals])

    print(f"Evaluating {len(grid_coarse)} coarse points in parallel...")
    with Pool(processes=os.cpu_count()) as pool:
        results = list(tqdm(pool.imap(sim_offdesign_wrapped, make_args(grid_coarse)), total=len(grid_coarse)))

    # Filter feasible and get top K
    feasible = [(t, phi, fuel) for t, phi, is_feas, fuel in results if is_feas]
    if not feasible:
        print("No feasible points found in coarse search.")
        return None, None

    feasible.sort(key=lambda x: x[2])  # sort by fuel burn
    top_feasible = feasible[:min(5, len(feasible))]

    print(f"Refining {len(top_feasible)} best regions with fine search...")

    best_phi = None
    best_fuel = float('inf')
    all_fine_results = []

    # Step 2: Fine local searches
    evals_left = total_budget - len(grid_coarse)
    fine_per_region = max(1, evals_left // len(top_feasible))
    fine_grid_1d = np.linspace(-fine_delta, fine_delta, int(np.sqrt(fine_per_region)))
    fine_offset = np.array([[dx, dy] for dx in fine_grid_1d for dy in fine_grid_1d])

    for _, center_phi, _ in top_feasible:
        local_grid = np.clip(center_phi + fine_offset, 0.0, 1.0)
        with Pool(processes=os.cpu_count()) as pool:
            results = list(tqdm(pool.imap(sim_offdesign_wrapped, make_args(local_grid)), total=len(local_grid)))
            all_fine_results.extend(results)

    #    for t, phi, is_feas, fuel in results:
    #        if is_feas and fuel < best_fuel:
    #            best_phi = phi
    #            best_fuel = fuel
    # Filter all feasible fine results
    feasible_fine = [(fuel, phi) for _, phi, is_feas, fuel in all_fine_results if is_feas]

    if not feasible_fine:
        print("No feasible solution found.")
        return None, None

    

    # Find minimum fuel value
    min_fuel = min(f for f, _ in feasible_fine)
    tol = 10  # Tolerance on fuel to consider equivalent solutions

    # Select among those with min fuel ± tol, the one with lowest infinity norm
    candidate_minima = [(phi, fuel) for fuel, phi in feasible_fine if abs(fuel - min_fuel) < tol]
    best_phi, best_fuel = min(candidate_minima, key=lambda x: np.linalg.norm(x[0], ord=2))

    print("  phi:", best_phi)
    print("  Fuel burn:", best_fuel)

    # PLOT the contour
    # Combine coarse and fine results
    all_results = results + all_fine_results  # 'results' is from coarse phase, 'all_fine_results' from fine phase
    # Extract required data
    evaluated_points = [phi for _, phi, _, _ in all_results]
    fuel_vals = [fuel for _, _, _, fuel in all_results]
    feasible_mask = [is_feas for _, _, is_feas, _ in all_results]
    plot_adaptive_fuel_contour(evaluated_points, fuel_vals, feasible_mask, fidelity, resolution=100)

    return best_phi, best_fuel

def optimise_phi_T_cma(aircraft, typical_range, payload, fidelity,
                       x0guess=(0.3, 0.2),
                       lower_bounds = [0.0, 0.0],
                       upper_bounds = [1.0, 1.0],
                       delta = 1,
                       maxiter = 50,
                       popsize = 6,
                       tolx = 1e-2
                       ):

    soc_min = aircraft.battery.SOC_min
    best_phi = None
    best_fuel = float('inf')

    x0 = np.array(x0guess)
    sigma0 = delta / 4

    es = cma.CMAEvolutionStrategy(x0, sigma0, {
        'bounds': [lower_bounds, upper_bounds],
        'popsize': popsize,
        'maxiter': maxiter,
        'tolx': tolx,
        'verb_disp': 1,
    })

    fitness_history = []
    scatter_history = defaultdict(list)  # generation -> list of (phi, fuel)

    # Parallel pool
    # Parallel pool using pathos (supports unpicklable objects)
    with Pool(nodes=os.cpu_count()) as pool:
        while not es.stop():
            candidates = es.ask()
            args_list = [(c, aircraft, typical_range, payload, fidelity, soc_min) for c in candidates]
            results = pool.map(sim_offdesign_wrapped, args_list)

            for c, (total, phi, feasible, fuel) in zip(candidates, results):
                scatter_history[es.countiter].append((phi.copy(), fuel))

            fitness = []
            for total, phi, feasible, fuel in results:
                fitness.append(total)
                if feasible and fuel < best_fuel:
                    best_phi = phi.copy()
                    best_fuel = fuel

            es.tell(candidates, fitness)
            fitness_history.append(min(fitness))
            print(f"Generation {es.countiter}: best fitness = {es.best.f:.2f}, mean = {np.mean(fitness):.2f}, std = {np.std(fitness):.2f}")
            print(f"   Current best phi = {es.best.x}")
            print(f"   Sigma = {es.sigma:.4f}")
            print(f"   Feasible best fuel so far = {best_fuel:.2f}")
            print(" ################################################ ")



    if best_phi is None:
        print("No feasible solution found — all violated constraints.")
        return None, None, None, None

    print('Best feasible phi:', best_phi)
    print('Fuel burn:', best_fuel)   

    return best_phi, best_fuel, fitness_history, scatter_history

def adaptive_bounds(phi_low, delta=0.1, asym_scale=2.0):
    """
    Creates asymmetric bounds for high-fidelity search:
    If a phi is high (e.g., > 0.6), lower bound is expanded more to explore lower values.
    If a phi is low, upper bound is expanded to explore higher values.
    """
    lower_bounds = []
    upper_bounds = []

    for phi in phi_low:
        if phi > 0.6:
            lower = max(0.0, phi - asym_scale * delta)
            upper = min(1.0, phi + 0.5 * delta)
        else:
            lower = max(0.0, phi - delta)
            upper = min(1.0, phi + delta)

        lower_bounds.append(lower)
        upper_bounds.append(upper)

    return np.clip(lower_bounds,0.0,1.0), np.clip(upper_bounds,0.0,1.0)


def is_close(phi1, phi2, tol=0.05):
    return np.linalg.norm(np.array(phi1) - np.array(phi2), np.inf) < tol