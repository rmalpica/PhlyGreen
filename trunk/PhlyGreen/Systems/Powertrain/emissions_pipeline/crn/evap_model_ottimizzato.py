# -*- coding: utf-8 -*-
"""
CRN evaporativo CFM56 – 4 modalità ICAO (ID, AP, CL, TO)

Logica allineata a:
- crn_evap_4modes.py  (chi_mixer_scale, f_vap_model = f_vap_used)
- fit_fvap_4modes.py  (parametri ottimali per ogni modo)
- UHC da liquido come TRACCIANTE ESTERNO (bypass), non reagisce in Cantera.

Per ogni modalità:
  - costruisce lo stesso CRN a 3 stadi (PZ: 9 PSR in parallelo, SZ, DZ)
  - calcola EI_NOx, EI_CO, EI_UHC_gas, EI_UHC_bypass, EI_UHC_total
  - calcola η_b secondo Eq.(6) (Villette)
Alla fine:
  - stampa un riepilogo tabellare
  - produce i 4 plot tipo Villette (EINOx, EICO, EIUHC, η_b).

Cantera 3.1
"""

import cantera as ct
import numpy as np
import matplotlib.pyplot as plt

# ---------------------------------------------------------
# Config meccanismo
# ---------------------------------------------------------
mech = "kerosene_surrogate_luche.yaml"
phase = "gas"

# ---------------------------------------------------------
# Dati per le 4 modalità ICAO del CFM56-7B27E
# (T_in, p_in [bar], mdot_air [kg/s], FAR, dP/P, chi_mixer_scale, EIUHC_ICAO)
# chi_mixer_scale sono quelli "ottimali" trovati con fit_fvap_4modes.py
# f_vap_target_best:
#   ID: 0.94, AP: 0.98, CL: 0.98, TO: 0.978758
# ---------------------------------------------------------
MODE_DATA = {
    "ID": {   # Idle
        "label": "Idle",
        "power": 7,
        "T_in": 477.0,
        "p_in_bar": 3.78,
        "mdot_air": 8.32,
        "FAR": 0.014,
        "dPqP": 0.9476,
        "chi_mixer_scale": 1.50,   # <── Aumentato per spingere f_vap verso ~0.98 perchè a 0.94 non va bene
        "EIUHC_ICAO": 1.54
    },
    "AP": {   # Approach
        "label": "Approach",
        "power": 30,
        "T_in": 619.0,
        "p_in_bar": 10.75,
        "mdot_air": 21.33,
        "FAR": 0.016,
        "dPqP": 0.9447,
        "chi_mixer_scale": 1.271698,
        "EIUHC_ICAO": 0.05
    },
    "CL": {   # Climb
        "label": "Climb",
        "power": 85,
        "T_in": 759.0,
        "p_in_bar": 24.80,
        "mdot_air": 42.80,
        "FAR": 0.024,
        "dPqP": 0.9486,
        "chi_mixer_scale": 1.071202,
        "EIUHC_ICAO": 0.02
    },
    "TO": {   # Take-Off
        "label": "Take-Off",
        "power": 100,
        "T_in": 795.0,
        "p_in_bar": 28.80,
        "mdot_air": 47.47,
        "FAR": 0.026,
        "dPqP": 0.9499,
        "chi_mixer_scale": 1.0,
        "EIUHC_ICAO": 0.03
    }
}

# ---------------------------------------------------------
# Geometria combustore (uguale per tutti i modi)
# ---------------------------------------------------------
Aref = 0.160
L    = 0.178
ARPZ = 30.82/100.0
ARSZ = 23.02/100.0
ARDZ = 46.15/100.0

LRPZ = 0.2029
LRSZ = 0.1979
LRDZ = 1.0 - LRPZ - LRSZ

V1_total = Aref * (L * LRPZ)
V2       = Aref * (L * LRSZ)
V3       = Aref * (L * LRDZ)

N_PZ = 9
V1_i = V1_total / N_PZ

T_ign = 1800.0  # K

# ---------------------------------------------------------
# Utility varie
# ---------------------------------------------------------
def get_comp_string(gas):
    return ", ".join(
        f"{sp}:{gas.X[i]:.6g}"
        for i, sp in enumerate(gas.species_names)
        if gas.X[i] > 0
    )

def ramp01_exp(t, tau):
    tau = max(tau, 1e-12)
    return 1.0 - np.exp(-max(0.0, t)/tau)

def mu_air_sutherland(T):
    # viscosità aria [Pa s] (fallback se il mech non ha transport)
    return 1.458e-6 * (T**1.5) / (T + 110.4)

def gaussian_weights_phi(phi_mean, sigma, n_pts):
    deltas = np.linspace(-2.0*sigma, 2.0*sigma, n_pts)
    phi_i = phi_mean + deltas
    w_raw = np.exp(-(deltas**2)/(sigma**2 + 1e-30))
    w_i = w_raw / np.sum(w_raw)
    return phi_i, w_i

def integrate_stage_stepwise(sim, reactor, t0,
                             tol_T_rel=1e-7, tol_P_rel=1e-7,
                             n_consec_ok=60, t_cap=0.5):
    t_list, T_list, P_list = [], [], []
    t_final = t0
    consec  = 0
    EPS = 1e-15
    T_prev, P_prev = reactor.T, reactor.thermo.P
    while (t_final < t0 + t_cap - EPS) and (consec < n_consec_ok):
        t_final = sim.step()
        T_now, P_now = reactor.T, reactor.thermo.P
        t_list.append(t_final)
        T_list.append(T_now)
        P_list.append(P_now)
        ok_T = abs(T_now - T_prev) <= tol_T_rel * max(1.0, T_now)
        ok_P = abs(P_now - P_prev) <= tol_P_rel * max(1.0, P_now)
        consec = consec + 1 if (ok_T and ok_P) else 0
        T_prev, P_prev = T_now, P_now
    return np.array(t_list), np.array(T_list), np.array(P_list), t_final

def mix_streams_mass(gas_prev_out, mdot_prev, gas_add_like_air, mdot_add,
                     p_target, T_air_for_h):
    gmix = ct.Solution(mech, phase)
    Y_prev = np.zeros(gmix.n_species)
    Y_add  = np.zeros(gmix.n_species)
    smap_prev = {s: i for i, s in enumerate(gas_prev_out.species_names)}
    smap_add  = {s: i for i, s in enumerate(gas_add_like_air.species_names)}
    for j, s in enumerate(gmix.species_names):
        if s in smap_prev:
            Y_prev[j] = gas_prev_out.Y[smap_prev[s]]
        if s in smap_add:
            Y_add[j] = gas_add_like_air.Y[smap_add[s]]
    mdot_tot = mdot_prev + mdot_add
    Y_mix = (mdot_prev*Y_prev + mdot_add*Y_add) / max(mdot_tot, 1e-30)

    h_prev = gas_prev_out.enthalpy_mass
    g_air  = ct.Solution(mech, phase)
    g_air.TPX = T_air_for_h, p_target, "O2:0.21, N2:0.79"
    h_add = g_air.enthalpy_mass
    h_mix = (mdot_prev*h_prev + mdot_add*h_add) / max(mdot_tot, 1e-30)

    gmix.HPY = h_mix, p_target, Y_mix
    return gmix

# ---------------------------------------------------------
# LHV, EI e efficienza (uguali a prima)
# ---------------------------------------------------------
def compute_LHV_villette(mech, phase, fuel_comp_str,
                          T_ref=298.15, T_prod=423.15,
                          P_ref=ct.one_atm, oxidizer="O2:1"):
    gas_R = ct.Solution(mech, phase)
    gas_R.TP = T_ref, P_ref
    gas_R.set_equivalence_ratio(phi=1.0,
                                fuel=fuel_comp_str,
                                oxidizer=oxidizer)
    h_R = gas_R.enthalpy_mass
    fuel_species = [sp.split(':')[0].strip()
                    for sp in fuel_comp_str.split(',')]
    Y_fuel = sum(gas_R[sp].Y[0] for sp in fuel_species
                 if sp in gas_R.species_names)
    gas_P = ct.Solution(mech, phase)
    gas_P.TPX = T_prod, P_ref, gas_R.X
    gas_P.equilibrate("TP")
    h_P = gas_P.enthalpy_mass
    return (h_R - h_P) / Y_fuel

def is_hydrocarbon(spec, gas):
    def n_el(s, e):
        return gas.n_atoms(s, e) if e in gas.element_names else 0
    nC = n_el(spec, 'C')
    nH = n_el(spec, 'H')
    return (nC > 0) and (nH > 0) and all(
        n_el(spec, e) == 0 for e in ['O', 'N', 'S', 'He', 'Ar']
    )

def EI_from_mass_fraction(Yk, FAR):
    return ((1.0 + FAR) / FAR) * Yk * 1e3  # g/kg_fuel

# ---------------------------------------------------------
# Legge vap_after_decomp_frac(T_in)
# (calibrata sui valori che hai già visto: 0.99108, 0.99638, 0.999)
# ---------------------------------------------------------
def vap_after_decomp_from_T(T_in):
    # mapping "furbo" ma semplice:
    #  - per T vicino all'Idle ~477 K -> ~0.99108
    #  - per T tipo Approach ~619 K -> ~0.99638
    #  - per T ≥ 750 K (CL/TO) -> 0.999
    if T_in <= 540.0:
        return 0.99108
    elif T_in <= 700.0:
        return 0.99638
    else:
        return 0.99900

# ---------------------------------------------------------
# Funzione principale: esegue il CRN per UN modo operativi
# ---------------------------------------------------------
def run_crn_evap_mode(mode_key, params):
    print("="*60)
    print(f"=== RUN CRN evaporativo – Mode: {mode_key} ({params['label']}) ===")

    # ------- unpack parametri di modo -------
    T_in   = params["T_in"]
    p_in   = params["p_in_bar"] * 1e5
    mdot_air = params["mdot_air"]
    FAR   = params["FAR"]
    dPqP  = params["dPqP"]
    chi_mixer_scale = params["chi_mixer_scale"]

    mdot_fuel = mdot_air * FAR
    mdot_pz_nom = mdot_air * ARPZ + mdot_fuel

    # ------- stream di base -------
    air_stream  = ct.Solution(mech, phase)
    air_stream.TPX  = T_in, p_in, "O2:0.21, N2:0.79"
    fuel_stream = ct.Solution(mech, phase)
    fuel_stream.TPX = T_in, p_in, "NC10H22:0.74, PHC3H7:0.15, CYC9H18:0.11"
    fuel_comp_str = get_comp_string(fuel_stream)

    # ------- stechiometria -------
    FAR_st = 0.06768662509412701
    phi_PZ_target = FAR / (FAR_st * ARPZ)
    phi_SZ_target = FAR / (FAR_st * (ARPZ + ARSZ))
    phi_DZ_target = FAR / FAR_st

    # ------- portate aria per zone -------
    mdot_air_PZ  = mdot_air * ARPZ
    mdot_air_SZa = mdot_air * ARSZ
    mdot_air_DZa = mdot_air * ARDZ

    mdot_sz_nom  = mdot_pz_nom + mdot_air_SZa
    mdot_dz_nom  = mdot_sz_nom + mdot_air_DZa

    # ------- back pressure -------
    P_exhaust = dPqP * p_in
    exh = ct.Solution(mech, phase)
    exh.TP = T_in, P_exhaust
    exhaust = ct.Reservoir(exh)

    # ------- tempi caratteristici / ramp -------
    rho1_0 = ct.Solution(mech, phase)
    rho1_0.TPX = T_ign, p_in, "N2:1.0"
    tau_res_PZ = (rho1_0.density * V1_total) / max(mdot_pz_nom, 1e-12)

    TRAMP_IN = np.clip(0.05 * tau_res_PZ, 1e-4, 1e-2)
    scale_in = lambda t: ramp01_exp(t, TRAMP_IN)

    # controller pressione
    eps_dp = 0.01
    K_SZ = mdot_sz_nom / (eps_dp * p_in)
    K_DZ = mdot_dz_nom / (eps_dp * max(p_in - P_exhaust, 1e-3))

    # ------- serbatoi a monte e link -------
    air_tank  = ct.Reservoir(air_stream)
    fuel_tank = ct.Reservoir(fuel_stream)

    link_PZ_SZ_mix = ct.Reservoir(ct.Solution(mech, phase))
    link_PZ_SZ_mix.thermo.TPX = T_in, p_in, "O2:0.21, N2:0.79"
    link_PZ_SZ_mix.syncState()

    link_SZ_DZ = ct.Reservoir(ct.Solution(mech, phase))
    link_SZ_DZ.thermo.TPX = T_in, p_in, "O2:0.21, N2:0.79"
    link_SZ_DZ.syncState()

    # ------- distribuzione φ_i in PZ (gaussiana) -------
    sigma_phi = 0.15 * phi_PZ_target
    phi_i_all, w_i_all = gaussian_weights_phi(phi_PZ_target, sigma_phi, N_PZ)
    idx_liquid_branch = N_PZ - 1
    mdot_air_PZ_i = w_i_all * mdot_air_PZ

    vap_indices = [i for i in range(N_PZ) if i != idx_liquid_branch]
    phi_i_vap   = phi_i_all[vap_indices]
    air_i_vap   = mdot_air_PZ_i[vap_indices]

    # =====================================================
    #      EVAPORAZIONE (Saboohi/Lefebvre) – f_vap_model
    # =====================================================
    gas_prop = ct.Solution(mech, phase)
    gas_prop.TPX = T_in, p_in, "O2:0.21, N2:0.79"
    rho_g = gas_prop.density
    try:
        mu_g = gas_prop.viscosity
    except Exception:
        mu_g = mu_air_sutherland(T_in)

    rho_f   = 800.0
    mu_f    = 1.6e-3
    sigma_f = 0.025

    dP_f   = 3.0e6
    C_smd  = 1.6

    chi_mixer_base = 0.60  # <<< come nei vecchi script
    # SMD (Lefebvre-like)
    SMD = C_smd * (mu_f**0.25)*(sigma_f**0.25)*(mdot_fuel**0.25) / (
        (rho_g**0.25)*(dP_f**0.5)
    )
    SMD = max(SMD, 5e-6)

    # D_AB semplificato
    T0, P0, D0 = 300.0, 101325.0, 2.0e-5
    D_AB = D0 * (T_in/T0)**1.75 * (P0/p_in)

    U_rel = np.sqrt(max(2.0*dP_f/rho_g, 0.0))
    Re_d  = rho_g * U_rel * SMD / max(mu_g, 1e-30)
    Sc    = mu_g / max(rho_g * D_AB, 1e-30)
    Sh    = 2.0 + 0.6*(max(Re_d, 1e-12)**0.5)*(max(Sc, 1e-12)**(1.0/3.0))

    B_M = 0.5
    K_base = 8.0 * D_AB * (rho_g/max(rho_f, 1e-30)) * np.log(1.0 + B_M)
    K_evp  = K_base * (Sh/2.0)

    tau_evp = (SMD**2) / max(K_evp, 1e-30)
    tau_mixer = chi_mixer_base * chi_mixer_scale * tau_res_PZ

    f_vap_model = float(
        np.clip(1.0 - np.exp(-tau_mixer / max(tau_evp, 1e-30)), 0.0, 1.0)
    )
    f_liq = 1.0 - f_vap_model

    print(f"[MODE] op_mode={mode_key}  T_in={T_in:.1f} K  p_in={params['p_in_bar']:.2f} bar  FAR={FAR:.3f}")
    print(f"[EVAP MODEL SABOOHI] chi_mixer_scale={chi_mixer_scale:.6f}")
    print(f"  SMD   = {SMD*1e6:.3f} µm")
    print(f"  Re_d  = {Re_d:.3f}   Sc={Sc:.3f}   Sh={Sh:.3f}")
    print(f"  D_AB  = {D_AB:.6e} m^2/s   K_evp={K_evp:.6e} m^2/s")
    print(f"  tau_evp   = {1e3*tau_evp:.3f} ms")
    print(f"  tau_res_PZ= {1e3*tau_res_PZ:.3f} ms   tau_mixer= {1e3*tau_mixer:.3f} ms")
    print(f"  f_vap_model = {f_vap_model:.6f}  -> f_liq={f_liq:.6f}")

    # =====================================================
    #    Decomposizione liquido in vap + soot + UHC (bypass)
    #    (UHC bypass NON entra in TPX; contribuisce solo a EI_UHC_bypass)
    # =====================================================
    vap_after_decomp = vap_after_decomp_from_T(T_in)
    f_soot = 0.05 * f_liq
    f_after_soot = max(f_liq - f_soot, 0.0)
    f_vap_decomp = vap_after_decomp * f_after_soot
    f_UHC        = max(f_after_soot - f_vap_decomp, 0.0)

    mdot_fuel_from_liq = f_vap_decomp * mdot_fuel

    print(f"[VAP-FRAC LAW] T_in={T_in:.1f} K -> vap_after_decomp_frac={vap_after_decomp:.6f}")
    print(f"[DECOMP FRACTIONS] f_liq={f_liq:.6f}, f_soot={f_soot:.6f}, "
          f"f_vap_decomp={f_vap_decomp:.6f}, f_UHC={f_UHC:.8f}")
    print(f"                    mdot_fuel_from_liq={mdot_fuel_from_liq:.6f} kg/s")

    # EI_UHC da bypass (massa di UHC che NON reagisce mai)
    EI_UHC_bypass = f_UHC * 1e3  # g/kg_fuel

    # =====================================================
    #      Ripartizione fuel gas nei 9 PSR (8 vap + 1 da liquido)
    # =====================================================
    FAR_i_target = phi_i_vap * FAR_st
    mdot_fuel_i_vap_req = FAR_i_target * air_i_vap
    mdot_fuel_vap_req   = float(np.sum(mdot_fuel_i_vap_req))

    mdot_fuel_vap_base = f_vap_model * mdot_fuel
    scale = 0.0 if mdot_fuel_vap_base <= 0.0 else min(
        1.0, mdot_fuel_vap_base / max(mdot_fuel_vap_req, 1e-30)
    )
    mdot_fuel_i_vap = mdot_fuel_i_vap_req * scale

    # fuel gas nei rami vap
    mdot_fuel_gas_injected = np.zeros(N_PZ)
    mdot_fuel_gas_injected[vap_indices] = mdot_fuel_i_vap

    # branch liquido: inietta SOLO la parte vap_decomp
    mdot_fuel_gas_injected[idx_liquid_branch] = mdot_fuel_from_liq

    # φ effettivi di ramo
    with np.errstate(divide="ignore", invalid="ignore"):
        FAR_i_eff = mdot_fuel_gas_injected / np.maximum(mdot_air_PZ_i, 1e-30)
    phi_i_eff = FAR_i_eff / FAR_st

    mdot_pz_nom_i = mdot_air_PZ_i + mdot_fuel_gas_injected

    # =====================================================
    #          COSTRUZIONE & INTEGRAZIONE dei 9 sub-PZ
    # =====================================================
    def make_branch(i):
        gas_inerte = ct.Solution(mech, phase)
        gas_inerte.TPX = T_ign, p_in, "N2:1.0"
        rPZ_i = ct.IdealGasReactor(gas_inerte, name=f"PZ_{i}", volume=V1_i)
        rPZ_i.energy_enabled = True
        rPZ_i.chemistry_enabled = True

        m_air_i = ct.MassFlowController(
            air_tank, rPZ_i,
            mdot=ct.Func1(lambda t, mdot_air_branch=mdot_air_PZ_i[i]:
                          mdot_air_branch * scale_in(t))
        )
        m_fuel_i = ct.MassFlowController(
            fuel_tank, rPZ_i,
            mdot=ct.Func1(lambda t, mdot_fuel_branch=mdot_fuel_gas_injected[i]:
                          mdot_fuel_branch * scale_in(t))
        )
        res_out_i = ct.Reservoir(ct.Solution(mech, phase))
        res_out_i.thermo.TPX = T_in, p_in, "O2:0.21, N2:0.79"
        res_out_i.syncState()

        K_i = (mdot_air_PZ_i[i] + mdot_fuel_gas_injected[i]) / (
            eps_dp * p_in + 1e-30
        )
        _ = ct.PressureController(rPZ_i, res_out_i, primary=m_air_i, K=K_i)
        sim_i = ct.ReactorNet([rPZ_i])
        return rPZ_i, sim_i, res_out_i

    pz_reactors = []
    pz_sims     = []
    pz_time_hist = []

    for i in range(N_PZ):
        rPZ_i, sim_i, _ = make_branch(i)
        t_i, T_i, P_i, _ = integrate_stage_stepwise(
            sim_i, rPZ_i, t0=0.0,
            tol_T_rel=1e-7, tol_P_rel=1e-7,
            n_consec_ok=80, t_cap=0.8
        )
        pz_reactors.append(rPZ_i)
        pz_sims.append(sim_i)
        pz_time_hist.append((t_i, T_i, P_i))

    # mixer PZ -> SZ
    def build_mixed_reservoir_from_branches(reactors, mdot_branches, p_target):
        gmix = ct.Solution(mech, phase)
        w = np.array(mdot_branches)
        w /= max(w.sum(), 1e-30)
        Y_mix = np.zeros(gmix.n_species)
        h_mix = 0.0
        for k, rloc in enumerate(reactors):
            gk = ct.Solution(mech, phase)
            gk.TPX = rloc.T, rloc.thermo.P, rloc.thermo.X
            Y_mix += w[k] * gk.Y
            h_mix += w[k] * gk.enthalpy_mass
        gmix.HPY = h_mix, p_target, Y_mix
        return gmix

    gas_out_PZ_mixed = build_mixed_reservoir_from_branches(
        pz_reactors, mdot_pz_nom_i, p_in
    )
    link_PZ_SZ_mix.thermo.TPX = (
        gas_out_PZ_mixed.T,
        gas_out_PZ_mixed.P,
        gas_out_PZ_mixed.X,
    )
    link_PZ_SZ_mix.syncState()

    # PZ "globale" per info (temperatura media)
    t1, T1_raw, P1_raw = pz_time_hist[0]
    T1_end = np.sum(
        [(mdot_pz_nom_i[i]/mdot_pz_nom)*pz_time_hist[i][1][-1]
         for i in range(N_PZ)]
    )
    P1_end = np.sum(
        [(mdot_pz_nom_i[i]/mdot_pz_nom)*pz_time_hist[i][2][-1]
         for i in range(N_PZ)]
    )
    T1 = T1_raw.copy()
    P1 = P1_raw.copy()
    T1[-1] = T1_end
    P1[-1] = P1_end

    # ===================== STADIO SZ =====================
    gas_up_SZ_init = mix_streams_mass(
        gas_out_PZ_mixed, mdot_pz_nom,
        air_stream, mdot_air_SZa,
        p_in, T_in
    )
    r2 = ct.IdealGasReactor(gas_up_SZ_init, name="SZ", volume=V2)
    r2.energy_enabled = True
    r2.chemistry_enabled = True

    m_SZ_pz  = ct.MassFlowController(
        link_PZ_SZ_mix, r2,
        mdot=ct.Func1(lambda t: mdot_pz_nom * scale_in(t))
    )
    m_SZ_air = ct.MassFlowController(
        air_tank, r2,
        mdot=ct.Func1(lambda t: mdot_air_SZa * scale_in(t))
    )
    _ = ct.PressureController(r2, link_SZ_DZ, primary=m_SZ_pz, K=K_SZ)

    sim2 = ct.ReactorNet([r2])
    t2, T2, P2, _ = integrate_stage_stepwise(
        sim2, r2, t0=t1[-1],
        tol_T_rel=1e-7, tol_P_rel=1e-7,
        n_consec_ok=60, t_cap=t1[-1] + 0.5
    )

    # ===================== STADIO DZ =====================
    gas_out_SZ = ct.Solution(mech, phase)
    gas_out_SZ.TPX = r2.T, r2.thermo.P, r2.thermo.X

    gas_up_DZ_init = mix_streams_mass(
        gas_out_SZ, mdot_sz_nom,
        air_stream, mdot_air_DZa,
        p_in, T_in
    )
    link_SZ_DZ.thermo.TPX = gas_out_SZ.T, gas_out_SZ.P, gas_out_SZ.X
    link_SZ_DZ.syncState()

    r3 = ct.IdealGasReactor(gas_up_DZ_init, name="DZ", volume=V3)
    r3.energy_enabled = True
    r3.chemistry_enabled = True

    m_DZ_core = ct.MassFlowController(
        link_SZ_DZ, r3,
        mdot=ct.Func1(lambda t: mdot_sz_nom * scale_in(t))
    )
    m_DZ_air  = ct.MassFlowController(
        air_tank, r3,
        mdot=ct.Func1(lambda t: mdot_air_DZa * scale_in(t))
    )
    _ = ct.PressureController(r3, exhaust, primary=m_DZ_core, K=K_DZ)

    sim3 = ct.ReactorNet([r3])
    t3, T3, P3, _ = integrate_stage_stepwise(
        sim3, r3, t0=t2[-1],
        tol_T_rel=1e-7, tol_P_rel=1e-7,
        n_consec_ok=60, t_cap=t2[-1] + 0.5
    )

    print(f"Run ok. T_end [K]: PZ(medio)={T1[-1]:.1f}, SZ={T2[-1]:.1f}, DZ={T3[-1]:.1f}")

    # ===================== EIs =====================
    fuel_comp_str = get_comp_string(fuel_stream)
    LHV = compute_LHV_villette(mech, phase, fuel_comp_str, oxidizer="O2:1")
    print(f"\nLHV = {LHV/1e6:.3f} MJ/kg_fuel")

    gas_out = ct.Solution(mech, phase)
    gas_out.TPX = r3.T, r3.thermo.P, r3.thermo.X
    Y_out = gas_out.Y
    smap = {s: i for i, s in enumerate(gas_out.species_names)}

    Y_NO  = Y_out[smap["NO"]]  if "NO"  in smap else 0.0
    Y_NO2 = Y_out[smap["NO2"]] if "NO2" in smap else 0.0
    Y_CO  = Y_out[smap["CO"]]  if "CO"  in smap else 0.0

    Y_UHC_gas = 0.0
    for s, i_sp in smap.items():
        if Y_out[i_sp] > 0.0 and is_hydrocarbon(s, gas_out):
            Y_UHC_gas += Y_out[i_sp]

    Y_NOx = Y_NO + Y_NO2
    EI_NOx = EI_from_mass_fraction(Y_NOx, FAR)
    EI_CO  = EI_from_mass_fraction(Y_CO,  FAR)
    EI_UHC_gas = EI_from_mass_fraction(Y_UHC_gas, FAR)

    EI_UHC_total = EI_UHC_gas + EI_UHC_bypass

    print("\n=== Emission Index – uscita DZ ===")
    print(f"EI_NOx = {EI_NOx:.3f} g/kg_fuel")
    print(f"EI_CO  = {EI_CO:.3f} g/kg_fuel")
    print(f"EI_UHC_gas     = {EI_UHC_gas:.6f} g/kg_fuel  (solo gas-phase)")
    print(f"EI_UHC_bypass  = {EI_UHC_bypass:.6f} g/kg_fuel  (da frazione liquida non bruciata)")
    print(f"EI_UHC_total   = {EI_UHC_total:.6f} g/kg_fuel  (somma)")

    # ===================== Efficienza (Eq.6) =====================
    T_ref = 288.15
    h_out = gas_out.enthalpy_mass
    gas_out_ref = ct.Solution(mech, phase)
    gas_out_ref.TPX = T_ref, r3.thermo.P, r3.thermo.X
    dh_t_out = h_out - gas_out_ref.enthalpy_mass

    phi_global = FAR / FAR_st
    gas_in_mix = ct.Solution(mech, phase)
    gas_in_mix.TP = T_in, p_in
    gas_in_mix.set_equivalence_ratio(phi=phi_global,
                                     fuel=fuel_comp_str,
                                     oxidizer="O2:0.21, N2:0.79")
    h_in_mix = gas_in_mix.enthalpy_mass
    X_in_mix = gas_in_mix.X

    gas_in_mix_ref = ct.Solution(mech, phase)
    gas_in_mix_ref.TPX = T_ref, p_in, X_in_mix
    dh_t_in = h_in_mix - gas_in_mix_ref.enthalpy_mass

    gas_fuel_Tin  = ct.Solution(mech, phase)
    gas_fuel_Tin.TPX  = T_in, p_in, fuel_comp_str
    gas_fuel_Tref = ct.Solution(mech, phase)
    gas_fuel_Tref.TPX = T_ref, p_in, fuel_comp_str
    dh_f = gas_fuel_Tin.enthalpy_mass - gas_fuel_Tref.enthalpy_mass

    MW_mix_out = gas_out.mean_molecular_weight
    mass_products_per_kg_fuel = 1.0 + 1.0 / FAR
    Ngas = mass_products_per_kg_fuel / MW_mix_out

    X_out = gas_out.X
    specs = gas_out.species_names
    idx = {s: i for i, s in enumerate(specs)}

    def safe_X(spec):
        return X_out[idx[spec]] if spec in idx else 0.0

    X_CO = safe_X("CO")

    X_UHC = 0.0
    for s in specs:
        if s in idx and is_hydrocarbon(s, gas_out):
            X_UHC += X_out[idx[s]]

    Ngas_CO  = X_CO  * Ngas
    Ngas_UHC = X_UHC * Ngas
    ΔH_CO  = 282_965e3
    ΔH_UHC = 802_396e3
    Q_CO   = Ngas_CO  * ΔH_CO
    Q_UHC  = Ngas_UHC * ΔH_UHC

    nb_eq6 = (LHV - Q_CO - Q_UHC) / LHV

    print("\n=== Efficienza del combustore ===")
    print(f"η_b (Eq.6) = {nb_eq6:.6f}")

    # ritorno risultati per i plot
    
    

# ritorno risultati per i plot + diagnostica PSR
    return {
        "EI_NOx": EI_NOx,
        "EI_CO": EI_CO,
        "EI_UHC_gas": EI_UHC_gas,
        "EI_UHC_bypass": EI_UHC_bypass,
        "EI_UHC_total": EI_UHC_total,
        "eta_b6": nb_eq6,
        "T_DZ": r3.T,  # T uscita DZ
        # --- roba per diagnostica sui 9 PSR della PZ ---
        "phi_i_eff": phi_i_eff.copy(),
        "mdot_air_PZ_i": mdot_air_PZ_i.copy(),
        "mdot_fuel_gas_injected": mdot_fuel_gas_injected.copy(),
    }



# ---------------------------------------------------------
#  ESECUZIONE su TUTTI e 4 i MODI + PLOT tipo Villette
# ---------------------------------------------------------
if __name__ == "__main__":
    # ordine: ID, AP, CL, TO (come nei grafici)
    mode_order = ["ID", "AP", "CL", "TO"]

    power_setting = []
    EINOx_1 = []
    EICO_1  = []
    EIUHC_1 = []
    eta_b_1 = []

    # salva anche EIUHC_ICAO
    EINOx_ICAO = []
    EICO_ICAO  = []
    EIUHC_ICAO = []

    # ---- Serie 3 (CRN_villette) ----
    EINOx_3 = np.array([1.2578, 13.205, 24.756, 30.764])
    EICO_3  = np.array([17.884, 3.7325, 1.7073, 1.8906])
    EIUHC_3 = np.array([0.21558, 0.02, 0.0033, 0.0033])
    eta_b_3 = np.array([0.99578, 0.99918, 0.99966, 0.99956])

    # ---- Serie 4 (CRN_standard) – invariata ----
    EINOx_4 = np.array([2.395, 11.929, 22.141, 26.913])
    EICO_4  = np.array([27.098, 5.819, 1.637, 1.485])
    EIUHC_4 = np.array([0.353760, 0.021978, 0.000057, 0.000018])
    eta_b_4 = np.array([0.993578, 0.998638, 0.999620, 0.999655])

    for key in mode_order:
        res = run_crn_evap_mode(key, MODE_DATA[key])

        power_setting.append(MODE_DATA[key]["power"])
        EINOx_1.append(res["EI_NOx"])
        EICO_1.append(res["EI_CO"])
        EIUHC_1.append(res["EI_UHC_total"])  # gas + bypass
        eta_b_1.append(res["eta_b6"])

        # Valori ICAO
        EINOx_ICAO.append({"ID": 4.36, "AP": 9.09, "CL": 17.89, "TO": 23.94}[key])
        EICO_ICAO.append({"ID": 29.39, "AP": 2.82, "CL": 0.17, "TO": 0.31}[key])
        EIUHC_ICAO.append(MODE_DATA[key]["EIUHC_ICAO"])

    # Conversione in array
    power_setting = np.array(power_setting)
    EINOx_1 = np.array(EINOx_1)
    EICO_1  = np.array(EICO_1)
    EIUHC_1 = np.array(EIUHC_1)
    eta_b_1 = np.array(eta_b_1)

    EINOx_2 = np.array(EINOx_ICAO)
    EICO_2  = np.array(EICO_ICAO)
    EIUHC_2 = np.array(EIUHC_ICAO)
    
   # efficienza empirica (Villette) – come nel tuo script
    PLC   = 1.6
    nb_ref = 0.999
    pt_std = 1.0
    Tt = np.array([MODE_DATA[k]["T_in"] for k in mode_order])
    pt = np.array([MODE_DATA[k]["p_in_bar"] for k in mode_order])
    md = np.array([MODE_DATA[k]["mdot_air"] for k in mode_order])
    omega = md * (pt/pt_std)**1.8 * 10.0**(0.00145*(Tt - 400.0))
    omega_ref = omega[-1]  # riferimento TO
    eta_empirical = 1.0 - (1.0 - nb_ref) * (np.abs(omega/omega_ref)**PLC)
    
    # 🔁 RIBALTA la curva empirica
    eta_b_2 = eta_empirical[::-1]


    # ---------------- PLOT aggiornati ----------------
    labels_general = ["CRN_evaporation", "ICAO", "CRN_villette", "CRN_standard"]
    labels_eff     = ["CRN_evaporation", "Empirical", "CRN_villette", "CRN_standard"]

    colors  = ["tab:red", "tab:blue", "tab:green", "tab:orange"]
    markers = ["o", "s", "D", "v"]

    EINOx_all = [EINOx_1, EINOx_2, EINOx_3, EINOx_4]
    EICO_all  = [EICO_1,  EICO_2,  EICO_3,  EICO_4]
    EIUHC_all = [EIUHC_1, EIUHC_2, EIUHC_3, EIUHC_4]
    eta_all   = [eta_b_1, eta_b_2, eta_b_3, eta_b_4]

    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    (ax1, ax2), (ax3, ax4) = axes
    fig.suptitle("CFM56 – CRN_evaporation vs ICAO vs CRN_villette vs CRN_standard",
                 fontsize=16, fontweight="bold")

    def plot_multi(ax, ysets, ylabel, ylog=False, labels=None):
        if labels is None:
            labels = ["CRN", "ICAO", "CRN_villette", "CRN_standard"]
        for y, c, m, lbl in zip(ysets, colors, markers, labels):
            ax.plot(power_setting, y, marker=m, color=c,
                    linewidth=1.8, label=lbl)
        ax.set_xlabel("Power Setting [%]")
        ax.set_ylabel(ylabel)
        if ylog:
            ax.set_yscale("log")
        ax.grid(True)
        ax.legend()

    # Pannelli
    plot_multi(ax1, EINOx_all, "EINOx [g/kg_fuel]", labels=labels_general)
    plot_multi(ax2, EICO_all,  "EICO [g/kg_fuel]", labels=labels_general)
    plot_multi(ax3, EIUHC_all, "EIUHC [g/kg_fuel]", ylog=True, labels=labels_general)
    plot_multi(ax4, eta_all,   "Combustion efficiency η_b [-]", labels=labels_eff)

    plt.tight_layout()
    plt.show()
