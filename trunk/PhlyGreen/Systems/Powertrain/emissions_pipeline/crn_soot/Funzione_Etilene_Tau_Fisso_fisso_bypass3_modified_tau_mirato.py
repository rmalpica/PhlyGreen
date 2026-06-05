from tabnanny import verbose
import cantera as ct
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from omnisoot import PerfectlyStirredReactor, PlugFlowReactor, SootGas

def CFM_engine_omnisoot(
    T_in,
    p_in,
    mdot_air,
    FAR,
    dPqP,
    fraz_bypass_9B,
    fraz_bypass_SZ1,
    factor_T,
    inception_pref,
    adsorption_pref,
    taub_max,
    frac_evap_min, 
    K_corr,
    K_dP,
    m_dot_SZ=0.2302,
    verbose=True):
    """
    fraz_bypass_9B : float [0,1]
        Frazione del flusso in uscita dal reattore 9B che NON si mescola
        con gli altri rami PZ ma procede direttamente verso il PFR
        omnisoot della Secondary Zone (Ramo 1 SZ).
        Il complemento (1-fraz_bypass_9B) confluisce nel mixing PZ e
        poi nel Ramo 0 (Cantera) di SZ insieme a tutta l'aria SZ.

    frac_evap_min : float [0,1]  (default=1.0)
        Percentuale minima di evaporazione del fuel nel reattore 9B,
        raggiunta alla portata d'aria massima (mdot_air_max).
        A portata minima (mdot_air_min) si assume evaporazione completa (1.0).
        Varia linearmente con mdot_air: alpha_evap = interp(mdot_air,
        [mdot_air_min, mdot_air_max], [1.0, frac_evap_min]).
        La quota di fuel NON evaporata (mdot_fuel_unvap) viene iniettata
        in fase vapore all'ingresso del PFR omnisoot della SZ (Ramo 1 SZ),
        aggiunta alla composizione del gas bypass 9B.

    fraz_bypass_SZ1 : float [0,1]
        Frazione del flusso in uscita dal PFR omnisoot della SZ (Ramo 1 SZ)
        che NON partecipa al mixing SZ ma procede direttamente verso il PFR
        omnisoot della Dilution Zone (Ramo 1 DZ).
        Il complemento (1-fraz_bypass_SZ1) si mescola con l'uscita del
        Ramo 0 Cantera SZ e confluisce nel Ramo 0 (Cantera) della DZ
        insieme a tutta l'aria DZ.

    Architettura:
        SZ: Ramo 0 (Cantera)  = intero gas PZ mixed + tutta aria SZ
             Ramo 1 (omnisoot) = intero bypass 9B
        Split SZ1: (1-fraz_bypass_SZ1) → mixing SZ → DZ Ramo 0
                    fraz_bypass_SZ1     → DZ Ramo 1 omnisoot (bypass diretto)
        DZ: Ramo 0 (Cantera)  = gas SZ mixed (Ramo0 SZ + quota Ramo1 SZ) + tutta aria DZ
             Ramo 1 (omnisoot) = quota bypass dal Ramo 1 SZ
        omnisoot usato SOLO per PSR 9B, PFR SZ Ramo 1, PFR DZ Ramo 1.
    """
    
    mech = "Caltech.yaml"
    phase="gas"
    DINAMICA="Monodisperse"  
    Modello_PAH="IrreversibleDimerization"  
    ads_coeff = adsorption_pref 
    inc_coeff = inception_pref
    Tempo_residenza_liquido = 0.010
    
    # ======== PUNTO OPERATIVO ========
    mdot_fuel = mdot_air * FAR  # kg/s
    print(f"Portata aria: {mdot_air:.2f} kg/s, Portata fuel: {mdot_fuel:.2f} kg/s, FAR: {FAR:.4f}")
    
    # --- Geometria combustore ---
    Aref = 0.160;  L = 0.178
    ARPZ = 30.82/100.0; ARSZ = m_dot_SZ; ARDZ =1-30.82/100.0-m_dot_SZ
    LRPZ = 0.2029; LRSZ = 0.1979; LRDZ = 1.0 - LRPZ - LRSZ
    V1_total = Aref * (L * LRPZ)
    V2       = Aref * (L * LRSZ)
    V3       = Aref * (L * LRDZ)
    N_PZ = 9
    print(f"Volume totale PZ: {V1_total:.6f} m3  (V1={V1_total*ARPZ:.6f} m3, V2={V2:.6f} m3, V3={V3:.6f} m3)")
    # [MODIFICA] Rimossa la divisione fissa V1_i = V1_total / N_PZ
    eps_dp=0.01
    # --- Innesco termico PZ ---
    T_ign = 2500.0  # K
    
    # --------------------
    # Utility (Invariate)
    # --------------------
    def get_comp_string(gas):
        return ", ".join([f"{sp}:{gas.X[i]:.6g}"
                          for i, sp in enumerate(gas.species_names)
                          if gas.X[i] > 0])
                          
    def mix_streams_mass(gas_prev_out, mdot_prev, gas_add_like_air, mdot_add, p_target, T_air_for_h):
        gmix = ct.Solution(mech, phase)
        Y_prev = np.zeros(gmix.n_species); Y_add  = np.zeros(gmix.n_species)
        smap_prev = {s: i for i, s in enumerate(gas_prev_out.species_names)}
        smap_add  = {s: i for i, s in enumerate(gas_add_like_air.species_names)}
        for j, s in enumerate(gmix.species_names):
            if s in smap_prev: Y_prev[j] = gas_prev_out.Y[smap_prev[s]]
            if s in smap_add:  Y_add[j]  = gas_add_like_air.Y[smap_add[s]]
        mdot_tot = mdot_prev + mdot_add
        Y_mix = (mdot_prev * Y_prev + mdot_add * Y_add) / max(mdot_tot, 1e-30)
        h_prev = gas_prev_out.enthalpy_mass
        g_air  = ct.Solution(mech, phase); g_air.TPX = T_air_for_h, p_target, "O2:0.21, N2:0.79"
        h_add = g_air.enthalpy_mass
        h_mix = (mdot_prev * h_prev + mdot_add * h_add) / max(mdot_tot, 1e-30)
        gmix.HPY = h_mix, p_target, Y_mix
        return gmix
        
    def ramp01_exp(t, tau):
        tau = max(tau, 1e-12)
        return 1.0 - np.exp(-max(0.0, t)/tau)
        
    def mu_air_sutherland(T):
        return 1.458e-6 * (T**1.5) / (T + 110.4)
        
    def integrate_stage_stepwise(sim, reactor, t0, tol_T_rel=1e-7, tol_P_rel=1e-7, n_consec_ok=60, t_cap=0.5, callback=None, callback_interval=5):
        t_list, T_list, P_list = [], [], []
        t_final = t0; consec = 0; step_count = 0
        EPS = 1e-15
        T_prev, P_prev = reactor.T, reactor.thermo.P
        while (t_final < t0 + t_cap - EPS) and (consec < n_consec_ok):
            t_final = sim.step(); step_count += 1
            if (callback is not None) and (step_count % max(1, callback_interval) == 0):
                try: callback(sim, reactor, t_final)
                except Exception as e: print("[WARN] callback error:", e)
            T_now, P_now = reactor.T, reactor.thermo.P
            t_list.append(t_final); T_list.append(T_now); P_list.append(P_now)
            ok_T = abs(T_now - T_prev) <= tol_T_rel * max(1.0, T_now)
            ok_P = abs(P_now - P_prev) <= tol_P_rel * max(1.0, P_now)
            consec = consec + 1 if (ok_T and ok_P) else 0
            T_prev, P_prev = T_now, P_now
        return np.array(t_list), np.array(T_list), np.array(P_list), t_final

    # --------------------
    # Stream di base
    # --------------------
    air_stream  = ct.Solution(mech, phase); air_stream.TPX  = T_in, p_in, "O2:0.21, N2:0.79"
    fuel_stream = ct.Solution(mech, phase); fuel_stream.TPX = T_in, p_in,  "C2H4:1.0"
    fuel_comp_str = get_comp_string(fuel_stream)
    
    # --------------------
    # Stechiometria / φ target
    # --------------------
    FAR_st = 0.06768662509412701
    phi_PZ_target = FAR / (FAR_st * ARPZ)
    
    # --------------------
    # Portate nominali
    # --------------------
    mdot_air_PZ  = mdot_air * ARPZ
    mdot_air_SZa = mdot_air * ARSZ
    mdot_air_DZa = mdot_air * ARDZ
    mdot_pz_nom  = mdot_air_PZ + mdot_fuel
    mdot_sz_nom  = mdot_pz_nom + mdot_air_SZa
    mdot_dz_nom  = mdot_sz_nom + mdot_air_DZa
    
    P_exhaust = dPqP * p_in
    exh = ct.Solution(mech, phase); exh.TP = T_in, P_exhaust
    exhaust = ct.Reservoir(exh)
    
    rho1_0 = ct.Solution(mech, phase); rho1_0.TPX = T_ign, p_in, "N2:1.0"
    tau_res_PZ = (rho1_0.density * V1_total) / max(mdot_pz_nom, 1e-12)
    TRAMP_IN = np.clip(0.05 * tau_res_PZ, 1e-4, 1e-2)
    scale_in = lambda t: ramp01_exp(t, TRAMP_IN)
    
    air_tank  = ct.Reservoir(air_stream)
    fuel_tank = ct.Reservoir(fuel_stream)

    # --------------------
    # Costruzione PZ: pesi gaussiani su φ_i
    # --------------------
    def gaussian_weights_phi(phi_mean, sigma, n_pts):
        deltas = np.linspace(-2.0*sigma, 2.0*sigma, n_pts)
        phi_i = phi_mean + deltas
        w_raw = np.exp(-(deltas**2)/(sigma**2 + 1e-30))
        w_i = w_raw / np.sum(w_raw)
        return phi_i, w_i
        
    sigma_phi = 0.15 * phi_PZ_target
    phi_i_all, w_i_all = gaussian_weights_phi(phi_PZ_target, sigma_phi, N_PZ)
    idx_liquid_branch = N_PZ - 1
    mdot_air_PZ_i = w_i_all * mdot_air_PZ
    vap_indices = [i for i in range(N_PZ) if i != idx_liquid_branch]
    phi_i_vap   = phi_i_all[vap_indices]
    air_i_vap   = mdot_air_PZ_i[vap_indices]
    
    # =========================================================
    #  EVAPORAZIONE: modello SABOOHI/LEFEBVRE (Invariato)
    # =========================================================
    gas_prop = ct.Solution(mech, phase); gas_prop.TPX = T_in, p_in, "O2:0.21, N2:0.79"
    rho_g = gas_prop.density
    try: mu_g = gas_prop.viscosity
    except Exception: mu_g = mu_air_sutherland(T_in)
    mdot_air_max = 47.47
    rho_f  = 800.0
    mu_f   = 1.6e-3 
    sigma_f= 0.025
    f_idle = 1.0 - mdot_air / mdot_air_max

    # Bump di RIDUZIONE della pressione iniettore centrato su approach
    f_dP_reduction = np.exp(-((f_idle - 0.55)**2) / 0.04)

    # dP_f base scala con p_in (fisico), poi viene ulteriormente
    # ridotto in approach dalla gaussiana
    dP_f_base = 3.0e6 * (p_in / 28.20e5)
    dP_f = 3.0e6 * (1.0 - K_dP * f_dP_reduction)
    #dP_f = 3.0e6 * (p_in / 28.20e5)
    C_smd  = 1.6
    chi_mixer = 0.60
    
    SMD = C_smd * (mu_f**0.25) * (sigma_f**0.25) * (mdot_fuel**0.25) / ((rho_g**0.25) * (dP_f**0.5))
    SMD = max(SMD, 5e-6)
    
    T0, P0, D0 = 300.0, 101325.0, 2.0e-5
    D_AB = D0 * (T_in/T0)**1.75 * (P0/p_in)
    
    U_rel = np.sqrt(max(2.0*dP_f/rho_g, 0.0))
    Re_d  = rho_g * U_rel * SMD / max(mu_g, 1e-30)
    Sc    = mu_g / max(rho_g * D_AB, 1e-30)
    Sh    = 2.0 + 0.6*(max(Re_d, 1e-12)**0.5)*(max(Sc, 1e-12)**(1.0/3.0))
    
    B_M = 0.5
    K_base = 8.0 * D_AB * (rho_g / max(rho_f, 1e-30)) * np.log(1.0 + B_M)
    K_evp  = K_base * (Sh/2.0)
    tau_evp   = (SMD**2) / max(K_evp, 1e-30)
    tau_mixer = chi_mixer * tau_res_PZ
    
    f_vap_base = float(np.clip(1.0 - np.exp(-tau_mixer / max(tau_evp, 1e-30)), 0.0, 1.0))
    f_liq_base = 1.0 - f_vap_base
    print(f"[EVAP MODEL SABOOHI] SMD={SMD*1e6:.1f} µm  Re_d={Re_d:.1f}  Sc={Sc:.3f}  Sh={Sh:.2f}")
    
    FAR_i_target = phi_i_vap * FAR_st
    mdot_fuel_i_vap_req = FAR_i_target * air_i_vap
    mdot_fuel_vap_req   = float(np.sum(mdot_fuel_i_vap_req))
    mdot_fuel_vap = f_vap_base * mdot_fuel
    scale = 0.0 if mdot_fuel_vap <= 0.0 else min(1.0, mdot_fuel_vap / max(mdot_fuel_vap_req, 1e-30))
    mdot_fuel_i_vap = mdot_fuel_i_vap_req * scale
    mdot_fuel_liq   = mdot_fuel - float(np.sum(mdot_fuel_i_vap))
    
    mdot_fuel_gas_injected = np.zeros(N_PZ)
    mdot_fuel_gas_injected[vap_indices] = mdot_fuel_i_vap
    mdot_fuel_gas_injected[idx_liquid_branch] = 0.0
    
    mdot_pz_nom_i = mdot_air_PZ_i + mdot_fuel_gas_injected

    # =========================================================
    # NUOVA PARTE: CALCOLO DEI VOLUMI PESATI
    # =========================================================
    mdot_totale_per_ramo = mdot_pz_nom_i.copy()
    mdot_totale_per_ramo[idx_liquid_branch] += mdot_fuel_liq
    
    # Volume pesato: frazione della massa totale * Volume totale
    V1_i_array = V1_total * (mdot_totale_per_ramo / np.sum(mdot_totale_per_ramo))
    V_9_pesato = V1_i_array[idx_liquid_branch]
    
    print(f"Volume Reattore 9 pesato sulla portata: {V_9_pesato*1e6:.2f} cm3")

    # =========================================================
    # FUNZIONE CALCOLO TEMPO NETTO SOOT (AGGIORNATA)
    # =========================================================
########def calcola_tau_netto_soot(T_in, p_in, mdot_local, V_9_rct):
########    import numpy as np  # <-- Risolve l'errore NameError per np.log
########    
########    V_9 = V_9_rct       # Usa il volume passato in ingresso
########    R_air = 287.05      
########    rho_l = 804.0       
########    h_fg = 250000.0     
########    T_boil = 540.0      
########    T_post = T_i[4] * factor_T
########    cp_g = 1000 + 0.2 * T_in          
########    k_g = 0.026 * (T_in / 300)**0.8   
########    D0 = 55e-6 * (p_in / 1e5)**-0.15 
########    
########    B = cp_g * (max(T_in - T_boil, 10.0)) / h_fg
########    lam = (8 * k_g * np.log(1 + B)) / (rho_l * cp_g)
########    t_evap = (D0**2) / lam
########
########    rho_evap = p_in / (R_air * T_in)
########    rho_post = p_in / (R_air * T_post)
########
########    V_dot_evap = mdot_local / rho_evap
########    V_dot_post = mdot_local / rho_post
########
########    Vol_evap = V_dot_evap * t_evap 
########    Vol_gas_rimanente = V_9 - Vol_evap
########
########    if Vol_gas_rimanente <= 0:
########        tau_netto = 0.0001 
########        t_gas = 0.0
########    else:
########        t_gas = Vol_gas_rimanente / V_dot_post
########        tau_netto = t_gas
########    
########    tau_finale = max(tau_netto, 0.0001)
########
########    print("-" * 55)
########    print(f"--- DEBUG CALCOLO TEMPO REATTORE (Vol: {V_9*1e6:.2f} cm3) ---")
########    print(f"Portata massica local            : {mdot_local:.5f} kg/s")
########    print(f"Tempo di evaporazione (t_evap)   : {t_evap:.6f} s")
########    print(f"Volume occupato da evaporazione  : {Vol_evap*1e6:.2f} cm3")
########    print(f"Volume rimanente per gas pirolisi: {Vol_gas_rimanente*1e6:.2f} cm3")
########    
########    if Vol_gas_rimanente <= 0:
########        print(f"[WARN] L'evaporazione satura il volume del reattore!")
########    else:
########        print(f"Portata volumetrica gas espanso  : {V_dot_post*1e6:.2f} cm3/s")
########        print(f"Tempo di residenza gas (t_gas)   : {t_gas:.6f} s")
########        
########    print(f"Tempo netto restituito al solver : {tau_finale:.6f} s")
########    print("-" * 55)
########
########    return tau_finale, t_evap, Vol_evap, Vol_gas_rimanente

    # =========================================================
    # CALCOLO TEMPI DI RESIDENZA PER TUTTI I RAMI
    # =========================================================
    #tau_pirolisi = np.interp(T_in, [477, 795], [0.0005, 0.001])
    mdot_air_min = 8.32
    mdot_air_max = 47.47
    
    # Definizione dei limiti di tempo di residenza (in secondi)
    tau_max = taub_max  # 1.0 ms
    tau_min = 0.0005  # 0.5 ms
    aria_ingresso=mdot_air
    # Interpolazione lineare (all'aumentare di mdot_air, il tempo scende da tau_max a tau_min)
    T_ref_high = 795.0  # Take-off
    T_ref_low  = 477.0  # Idle
    factor_tau_T = np.interp(T_in, [T_ref_low, T_ref_high], [0.4, 1.0])
    f_idle = 1.0 - mdot_air / mdot_air_max
    f_approach = np.exp(-((f_idle - 0.6)**2) / 0.04)  # Picco vicino a f_idle=0.6 (approach)
    #f_approach = f_approach * (1.0 - f_idle)
    
    tau_base = np.interp(mdot_air, [mdot_air_min, mdot_air_max],
                     [tau_max, tau_min]) #* factor_tau_T

    tau_pirolisi = tau_base * (1.0 - K_corr* f_approach)
    print(f"Temperatura in ingresso: {T_in:.1f} K -> Tempo di pirolisi calcolato: {tau_pirolisi*1000:.2f} ms")
    m_9=mdot_air_PZ_i[idx_liquid_branch] + mdot_fuel_liq
    # ---------------------------------------------------------
    def simulate_liquid_branch_omnisoot(
        mdot_fuel_liq, mdot_air, V_total_9, 
        T_in, p_in, L_vap, mech, phase, fuel_comp_str,
        soot_params,
        T_spark=1500.0
    ):
        # ... RESTO DEL TUO CODICE DA QUI IN POI È INVARIATO ...
        """
        Simula il ramo liquido (Nono Reattore) dividendo il volume in due fasi:
        9A: Evaporazione progressiva dipendente dal tempo (assorbe calore latente).
        9B: Combustione PSR a stazionario della sola fase gassosa (forzando l'innesco).
        """
        # ==========================================
        # STADIO 1: REATTORE 9A (Evaporazione Cinetica)
        # ==========================================
        # Frazione di liquido che fa in tempo ad evaporare in tau_9A
       ###if tau_evap_char > 0:
       ###    alpha_evap = 1.0 - np.exp(-tau_9A / tau_evap_char)
       ###else:
       ###    alpha_evap = 1.0
       ###  
        # -------------------------------------------------------------------
        # EVAPORAZIONE VARIABILE: lineare con la portata in massa d'aria.
        # A portata minima (mdot_air_min) si assume evaporazione totale (1.0).
        # A portata massima (mdot_air_max) si usa frac_evap_min (calibrabile).
        # -------------------------------------------------------------------
        f_idle = 1.0 - aria_ingresso / mdot_air_max

        #morza effetto vicino a idle
        f_eff = f_idle * (1 - 0.3 * f_idle)

        alpha_base = np.interp(aria_ingresso, [mdot_air_min, mdot_air_max], [1.0, frac_evap_min])
        
        # riduzione SOLO in approach
        alpha_evap = alpha_base #* (1.0 - K_corr * f_approach)
        
        alpha_evap = float(np.clip(alpha_evap, 0.0, 1.0))
        print(f"[EVAP 9B] mdot_air={aria_ingresso:.3f} kg/s -> alpha_evap={alpha_evap*100:.1f}% "
              f"(frac_evap_min={frac_evap_min*100:.1f}%)")

        # Portate di massa
        mdot_fuel_gas = mdot_fuel_liq * alpha_evap
        mdot_fuel_unvap = mdot_fuel_liq * (1.0 - alpha_evap) # Rimane goccia/incombusto
        mdot_gas_tot = mdot_air + mdot_fuel_gas
        # Se non c'è gas combustibile, passa solo aria
        if mdot_fuel_gas <= 0.0:
            gas_out = ct.Solution(mech, phase)
            gas_out.TPX = T_in, p_in, "O2:0.21, N2:0.79"
            return gas_out, T_in, 0.0, None, mdot_fuel_unvap
        # Termodinamica dei reagenti
        air = ct.Solution(mech, phase)
        air.TPX = T_in, p_in, "O2:0.21, N2:0.79"
        fuel = ct.Solution(mech, phase)
        fuel.TPX = T_in, p_in, fuel_comp_str
        # Bilancio Entalpico (solo fase gas)
        h_air = air.enthalpy_mass
        h_fuel_gas = fuel.enthalpy_mass
        # Entalpia della miscela gas prima del prelievo del calore latente
        h_mix_gas = (mdot_air * h_air + mdot_fuel_gas * h_fuel_gas) / mdot_gas_tot
        # Sottraiamo il calore latente SOLO per la massa effettivamente evaporata
        Y_fuel_gas_global = mdot_fuel_gas / mdot_gas_tot
        h_mix_evap = h_mix_gas - Y_fuel_gas_global * L_vap
        # Composizione di massa della fase gassosa
        Y_mix = (mdot_air * air.Y + mdot_fuel_gas * fuel.Y) / mdot_gas_tot
        # Stato di uscita da 9A
        gas_9A_out = ct.Solution(mech, phase)
        #gas_9A_out.HPY = h_mix_evap, p_in, Y_mix
        # Calcola energia relativa del PSR rispetto al take-off
        
        gas_9A_out.TPY= T_i[4]*factor_T, p_in, Y_mix
        T_9A_out = gas_9A_out.T
        print(f"\n[DEBUG] 9A out: T={T_9A_out:.1f} K ")
        rho_9A = gas_9A_out.density
        print("\n--- REATTORE 9A (Mixer ed Evaporatore) ---")
        print(f"Frazione evaporata (alpha)  = {alpha_evap*100:.1f} %")
        print(f"Temperatura mix evaporata   = {T_9A_out:.1f} K")
        print(f"Equivalence Ratio (Phi) loc = {gas_9A_out.equivalence_ratio():.3f}")
        print(f"Fuel liquido incombusto     = {mdot_fuel_unvap*1e3:.2f} g/s")
        # ==========================================
        # STADIO 2: Calcolo Volumi
        # ==========================================
        # tau_9B globale (6 us) e' il tempo di residenza dell'intero combustore,
        # non del singolo PSR: usarlo direttamente dava V_9B = 0.
        # Usiamo il 50% del volume totale per il PSR di combustione.
            
        
        V_9B= tau_pirolisi * m_9 / rho_9A
        V_9A = V_total_9 - V_9B
        tau_9B_cold = (rho_9A * V_9B) / max(mdot_gas_tot, 1e-30)
        print(f"Volume totale disponibile V_total_9 = {V_total_9*1e6:.1f} cm^3")
        print(f"Volume occupato da evaporazione V_9A = {V_9A*1e6:.1f} cm^3")
        print(f"Volume utile rimanente V_9B          = {V_9B*1e6:.1f} cm^3")
        print(f"tau_9B stima fredda                  = {tau_9B_cold*1e3:.3f} ms")
        #if V_9B <= 0:
        #    V_9B= 0.0001*m_9/rho_9A
        #    print(f"V_9B non positivo: {V_9B:.2e} m^3")
        # ==========================================
        # STADIO 3: REATTORE 9B (Combustione PSR)
        # ==========================================
        # 1. Creiamo l'oggetto SootGas dalla miscela calcolata in 9A
        soot_gas = SootGas(gas_9A_out)
        # 2. Inizializziamo il PerfectlyStirredReactor di Omnisoot
        psr = PerfectlyStirredReactor(soot_gas)
        psr.temperature_solver_type = soot_params.get("Temperature solver", "isothermal")
        psr.reactor_volume = V_9B
        psr.mdot_in = mdot_gas_tot
        psr.P_outlet = p_in
        # Disabilitiamo l'equilibratura automatica: con phi >> 1 Cantera produce
        # uno stato con densita' negativa che fa crashare il solver al step ~66.
        # Impostiamo T_spark manualmente come stato iniziale del gas nel reattore.
        psr.start_from_equilibrium = False
        #soot_gas.TP = T_spark, p_in
        # 3. Configurazione dei parametri di soot (ispirata a simulate_PSR_PFR.py)
        soot = psr.soot
        soot.particle_dynamics_model_type = soot_params.get("particle_dynamics_model_type", "Sectional")
        if soot.particle_dynamics_model_type == "Sectional":
            soot.particle_dynamics_model.number_of_sections = soot_params.get("number_of_sections", 60)
        soot.particle_dynamics_model.eta_coag_type = "repulsion_d_based"
        soot.PAH_growth_model_type = soot_params.get("PAH_growth_model_type", "DimerCoalescence")
        soot.set_precursor_names(soot_params.get("precursors", ["A4"])) ############### INSERIRE I PRECURSORI CRECK ################
        soot.PAH_growth_model.inception_prefactor = soot_params.get("inception_prefactor", 1.0)
        soot.PAH_growth_model.adsorption_prefactor = soot_params.get("adsorption_prefactor", 1.0)
        soot.surface_reactions_model.alpha_model = "composition"
        if soot.PAH_growth_model_type == "DimerCoalescence":
            soot.PAH_growth_model.stick_eff = soot_params.get("dimcoal_effs", [0.002, 0.015, 0.025, 0.004])
        
       # 4. Avvio simulazione
        # BDF è più robusto di LSODA per sistemi rigidi (chimismo + soot)
        psr.solver_type = "BDF"
        psr.max_step = 1e-3
        psr.rtol = 1e-5
        psr.atol = 1e-10
        psr._default_high_initial_temperature = soot_gas.T
        psr.start()
        
        target_sim_time = 0.008  # Assicuriamo un tempo minimo
        # Limite di step assoluto: evita loop infiniti se il solver si inceppa
        MAX_STEPS = 80000
        # Parametri di convergenza anticipata
        CONV_WINDOW   = 5000          # step da verificare
        CONV_TOL_T    = 0.5          # K - variazione max di T su CONV_WINDOW step
        CONV_TOL_VF   = 1e-5
        CONV_TOL_SOOT_MASS = 1e-7
            # variazione relativa max di volume_fraction
        print(f"-> Inizio integrazione 9B... tau_9B={tau_pirolisi*1e3:.3f} ms  "
              f"target={target_sim_time*1e3:.2f} ms  max_steps={MAX_STEPS}")
        step = 0
        t_prev_check = 0.0
        T_prev_check = soot_gas.T
        vf_prev_check = psr.soot.volume_fraction
        converged = False
        stalled   = False
        # --- Raccolta storico PSR per plot ---
        psr_time_hist   = []
        psr_mdot_soot_hist = []
        m_before=0.0
        while psr.restime < target_sim_time and step < MAX_STEPS:
            t_before = psr.restime
            m_before = psr.soot.total_mass * mdot_gas_tot
            try:
                psr.step()
            except Exception as e:
                print(f"[WARN] psr.step() sollevato un'eccezione al step {step}: {e}")
                stalled = True
                break
            step += 1
            dt = psr.restime - t_before
            d_soot_mass = psr.soot.total_mass * mdot_gas_tot - m_before
            soot_massa = psr.soot.total_mass * mdot_gas_tot
            # Raccolta dati per il plot
            psr_time_hist.append(psr.restime)
            psr_mdot_soot_hist.append(psr.soot.total_mass * mdot_gas_tot)
            # Guardia contro passi zero/negativi (solver bloccato)
            if dt < 1e-20:
                print(f"[WARN] Passo dt={dt:.2e} s al step {step} — solver bloccato. Esco.")
                stalled = True
                break
            # Diagnostica ogni CONV_WINDOW step
            if step % CONV_WINDOW == 0:
                T_now  = soot_gas.T
                vf_now = psr.soot.volume_fraction
                dT  = abs(T_now - T_prev_check)
                dvf = abs(vf_now - vf_prev_check) / max(abs(vf_prev_check), 1e-30)
                print(f"   Step {step:>7d} | t={psr.restime*1e3:8.4f} ms | "
                      f"T={T_now:.1f} K (ΔT={dT:.2f}) | "
                      f"fv={vf_now:.3e} (Δrel={dvf:.3e}) | "
                      f"soot_mass={soot_massa:.3e} kg/s")
                # Controllo convergenza: stazionario se T e vf variano poco
                if psr.restime > 0.002 and d_soot_mass < CONV_TOL_SOOT_MASS :
                    print("-> CONVERGENZA ANTICIPATA raggiunta. Interrompo.")
                    converged = True
                    break
                T_prev_check  = T_now
                vf_prev_check = vf_now
        if step >= MAX_STEPS and not converged:
            print(f"[WARN] Raggiunto limite massimo di {MAX_STEPS} step senza convergenza. "
                  f"t_finale={psr.restime*1e3:.4f} ms")
        if stalled:
            print("[WARN] Integrazione interrotta per stallo del solver. "
                  "Risultati parziali potrebbero essere inaccurati.")
                
        # ==========================================
        # STADIO 4: Estrazione Risultati
        # ==========================================
        # Lo stato termodinamico a stazionario è ora salvato in soot_gas
        rho_final = soot_gas.density
        # Il VERO tempo di residenza del fluido nel reattore a regime (densità a gas caldi)
        tau_9B_fluid_actual = (rho_final * V_9B) / psr.mdot_out
        print("\n--- REATTORE 9B (Combustore OMNISOOT) ---")
        print(f"Volume utile rimanente V_9B  = {V_9B*1e6:.1f} cm^3")
        print(f"Tempo di residenza fluido    = {tau_9B_fluid_actual*1e3:.2f} ms")
        print(f"Temperatura a stazionario    = {soot_gas.T:.1f} K")
        print(f"Frazione Volumetrica Soot    = {psr.soot.volume_fraction:.3e}")
        # Restituiamo soot_gas (che si comporta come ct.Solution), la temperatura, 
        # il tempo di residenza, l'intero oggetto psr (per estrarre altri dati soot se serve) e gli incombusti.
        return soot_gas, soot_gas.T, tau_9B_fluid_actual, psr, mdot_fuel_unvap, np.array(psr_time_hist), np.array(psr_mdot_soot_hist)
    ##################################################################################################################
    ##################################################################################################################
    # =========================================================
    #            COSTRUZIONE & INTEGRAZIONE dei 9 sub-PZ
    #   1) Integro PRIMA i 8 rami vap -> T finali
    #   2) Integro il ramo liquido con callback (ogni N step)
    # =========================================================
    pz_reactors = []; pz_sims = []; pz_out_res = []; pz_time_hist = []; pz_K_list = []
    def make_branch(i):
        gas_inerte = ct.Solution(mech, phase); gas_inerte.TPX = T_ign, p_in, "N2:1.0"
        rPZ_i = ct.IdealGasReactor(gas_inerte, name=f'PZ_{i}', volume=V1_i_array[i])
        rPZ_i.energy_enabled = True; rPZ_i.chemistry_enabled = True
        m_air_i = ct.MassFlowController(
            air_tank, rPZ_i,
            mdot=ct.Func1(lambda t, mdot_air_branch=mdot_air_PZ_i[i]: mdot_air_branch * scale_in(t))
        )
        m_fuel_i = ct.MassFlowController(
            fuel_tank, rPZ_i,
            mdot=ct.Func1(lambda t, mdot_fuel_branch=mdot_fuel_gas_injected[i]: mdot_fuel_branch * scale_in(t))
        )
        res_out_i = ct.Reservoir(ct.Solution(mech, phase))
        res_out_i.thermo.TPX = T_in, p_in, "O2:0.21, N2:0.79"; res_out_i.syncState()
        K_i = (mdot_air_PZ_i[i] + mdot_fuel_gas_injected[i]) / (eps_dp * p_in + 1e-30)
        v_i = ct.PressureController(rPZ_i, res_out_i, primary=m_air_i, K=K_i)
        sim_i = ct.ReactorNet([rPZ_i])
        return rPZ_i, sim_i, res_out_i, K_i
    # --- Integro PRIMA i rami vap (0..7)
    for i in range(N_PZ-1):
        rPZ_i, sim_i, res_out_i, K_i = make_branch(i)
        t_i, T_i, P_i, _ = integrate_stage_stepwise(sim_i, rPZ_i, t0=0.0,
                                                    tol_T_rel=1e-7, tol_P_rel=1e-7,
                                                    n_consec_ok=80, t_cap=0.8)
        pz_reactors.append(rPZ_i); pz_sims.append(sim_i); pz_out_res.append(res_out_i)
        pz_time_hist.append((t_i, T_i, P_i)); pz_K_list.append(K_i)
    print(f"pesi gaussiana:{w_i_all}")
    
    ####################################### PARTE NUOVA #############################################
    #################################################################################################
    # =============================================================================
    # CALCOLO RAMO LIIQUIDO (NONO REATTORE - 9B) CON OMNISOOT
    # =============================================================================
    i = idx_liquid_branch
    print(f"\n--- Avvio simulazione ramo {i+1} (Ramo Liquido / Core) ---")
    # 1. Configurazione Omnisoot ispirata a launcher.py
    soot_params = {
        "particle_dynamics_model_type": "Monodisperse",
        "number_of_sections": 60,
        "PAH_growth_model_type": "DimerCoalescence", 
        "precursors": ["A2", "A3", "A4", "A2R5"], # Assicurati che il mecc Luche li contenga!
        "dimcoal_effs": [0.002, 0.015, 0.025, 0.004],
        # Pre-fattori specifici per DimerCoalescence estratti da launcher.py
        "inception_prefactor": inc_coeff,  
        "adsorption_prefactor": ads_coeff,
        "Temperature solver": "isothermal"  # Puoi sperimentare anche con "Adiabatic" o "Energy"
    }
    # 2. Scelta del tempo dedicato all'evaporazione (es. 2 ms)
    # Puoi far dipendere questo valore dalla velocità del flusso o da un parametro del tuo modello
    tau_mixer_9A = Tempo_residenza_liquido
    # 3. Chiamata alla funzione del Ramo Liquido
    L_vap_approx = 250e3  # J/kg, mantenuto dal tuo script
    print(f"-> Simulazione ramo liquido con Omnisoot: mdot_fuel_liq={mdot_fuel_liq:.2f} kg/s, ")
    mdot_9=mdot_air_PZ_i[idx_liquid_branch] + mdot_fuel_liq
    #tau_reale_soot, t_evap, Vol_evap, Vol_gas_rimanente = calcola_tau_netto_soot(T_in, p_in, mdot_9, V1_i_array[idx_liquid_branch])
    gas_9B_out, T_9B, tau_9B_actual, psr_obj, mdot_fuel_unvap, psr_time_arr, psr_mdot_soot_arr = simulate_liquid_branch_omnisoot(
        mdot_fuel_liq=mdot_fuel_liq,
        mdot_air=mdot_air_PZ_i[idx_liquid_branch],
        V_total_9=V1_i_array[idx_liquid_branch],
        T_in=T_in,
        p_in=p_in,
        L_vap=L_vap_approx,
        mech=mech,
        phase=phase,
        fuel_comp_str=fuel_comp_str,
        soot_params=soot_params,
        
        T_spark=1500.0  # Temperatura fittizia per innescare numericamente la reazione in 9B (puoi tararla se serve
    )
    print(dir(psr_obj))
    print(dir(gas_9B_out))
    print(f"portata in massa di soot: {psr_obj.soot.total_mass*(mdot_fuel_liq):.6e} kg/s")
    # 4. Interfacciamento con il resto dello script (Mixing per la Zona Secondaria)
    # Siccome il codice successivo si aspetta dei ct.Reservoir in pz_out_res per fare il mixing,
    # copiamo lo stato termodinamico di Omnisoot in un gas puro di Cantera per il reservoir di scarico.
    gas_for_reservoir = ct.Solution(mech, phase)
    gas_for_reservoir.TPY = gas_9B_out.T, gas_9B_out.P, gas_9B_out.Y
    # 1. Estraiamo i nomi delle specie e le frazioni di massa
    nomi_specie = gas_for_reservoir.species_names
    frazioni_massa = gas_for_reservoir.Y
    
    # 2. Creiamo un DataFrame Pandas
    df_composizione = pd.DataFrame({
        'Specie': nomi_specie,
        'Frazione_di_Massa_Y': frazioni_massa
    })
    
    # 3. Ordiniamo i dati in ordine decrescente (dalla specie più abbondante alla meno abbondante)
    df_composizione = df_composizione.sort_values(by='Frazione_di_Massa_Y', ascending=False)
    
    # 4. Salviamo il file CSV
    nome_file_csv = 'composizione_ramo_9B_etilene.csv'
    df_composizione.to_csv(nome_file_csv, index=False)
    
    # 5. Stampiamo a terminale un'anteprima (le prime 15 specie) per comodità
    print(f"\n--- Composizione del gas salvata in '{nome_file_csv}' ---")
    print("Ecco le 15 specie più abbondanti:")
    print(df_composizione.head(15).to_string(index=False))
    print("-" * 50 + "\n")
    res_out_9 = ct.Reservoir(gas_for_reservoir)
    # --- FIX 1: Creiamo un reattore "dummy" di Cantera affinché il mixer non vada in errore ---
    dummy_r9 = ct.IdealGasReactor(gas_for_reservoir)
    # --- FIX 2: Trasformiamo i float in array per non far fallire l'indicizzazione [-1] dei plot ---
    t_arr_9 = np.array([0.0, tau_9B_actual])
    T_arr_9 = np.array([T_9B, T_9B])
    P_arr_9 = np.array([gas_for_reservoir.P, gas_for_reservoir.P])
    # Aggiungiamo i risultati alle liste globali
    pz_reactors.append(dummy_r9)  # Appende il reattore compatibile con Cantera
    pz_sims.append(None)          
    pz_out_res.append(res_out_9)  
    pz_time_hist.append((t_arr_9, T_arr_9, P_arr_9)) # Passa array invece che singoli float
    pz_K_list.append(0.0)
    print(f"-> Fine calcolo Ramo 9. Incombusto rimanente: {mdot_fuel_unvap*1e3:.3f} g/s")
    # =============================================================================
    #################################################################################################
    #################################################################################################
    # --- Ramo liquido (indice 8) con callback
    ####i = idx_liquid_branch
    ####rPZ_i, sim_i, res_out_i, K_i = make_branch(i)
    ####def phi_eff_proxy_from_state(rct, FAR_st):
    ####    # stima φ dal contenuto di specie "fuel-like" (idrocarburi puri) rispetto all'aria; proxy semplificato
    ####    gas = ct.Solution(mech, phase); gas.TPX = rct.T, rct.thermo.P, rct.thermo.X
    ####    # massa "fuel-like"
    ####    Y = gas.Y; names = gas.species_names
    ####    def is_hc(s):
    ####        try:
    ####            nC = gas.n_atoms(s, 'C'); nH = gas.n_atoms(s, 'H')
    ####            nO = gas.n_atoms(s, 'O') if 'O' in gas.element_names else 0
    ####            nN = gas.n_atoms(s, 'N') if 'N' in gas.element_names else 0
    ####            return (nC>0 and nH>0 and nO==0 and nN==0)
    ####        except Exception:
    ####            return False
    ####    Y_fuel_like = 0.0
    ####    for idx, s in enumerate(names):
    ####        if Y[idx] > 0 and is_hc(s):
    ####            Y_fuel_like += Y[idx]
    ####    # stima FAR_eff proxy (assumi il resto come aria): molto grezza, usare solo come indicatore qualitativo
    ####    FAR_eff = Y_fuel_like / max(1.0 - Y_fuel_like, 1e-30)
    ####    return FAR_eff / FAR_st
    ####
    ##### callback: ogni N step valuta T̄_vap e, se > T_decomp_start, decompone inventario liquido; logga info
    ####def liquid_callback(sim, rct, tnow):
    ####    temps = []; weights = []
    ####    for j in range(N_PZ-1):
    ####        temps.append(pz_reactors[j].T)
    ####        weights.append(mdot_pz_nom_i[j])
    ####    temps = np.array(temps); weights = np.array(weights)
    ####    Tbar = np.sum(temps * weights) / max(np.sum(weights), 1e-30)
    ####    trigger = (Tbar >= T_decomp_start)
    ####    vap_mass, soot_mass, uhc_mass = (0.0, 0.0, 0.0)
    ####    if trigger:
    ####        vap_mass, soot_mass, uhc_mass = apply_liquid_decomposition_to_reactor_conservative(
    ####            rct=rct,
    ####            branch_idx=i,
    ####            liquid_inventory=liquid_inventory,
    ####            T_trigger_ok=True
    ####        )
    ####    # φ proxy istantaneo
    ####    phi_eff_proxy = phi_eff_proxy_from_state(rct, FAR_st)
    ####    print(f"[CALLBACK-9] t={tnow:.4f} s | T9={rct.T:.1f} K | Tbar_vap={Tbar:.1f} K | "
    ####          f"trigger={trigger} | phi_eff_proxy≈{phi_eff_proxy:.3f} | "
    ####          f"added: vap={vap_mass:.6e} kg, soot={soot_mass:.6e} kg, UHC={uhc_mass:.6e} kg")
    ####
    ####t_i, T_i, P_i, _ = integrate_stage_stepwise(sim_i, rPZ_i, t0=0.0,
    ####                                            tol_T_rel=1e-7, tol_P_rel=1e-7,
    ####                                            n_consec_ok=80, t_cap=0.8,
    ####                                            callback=liquid_callback, callback_interval=5)
    ####
    ####pz_reactors.append(rPZ_i); pz_sims.append(sim_i); pz_out_res.append(res_out_i)
    ####pz_time_hist.append((t_i, T_i, P_i)); pz_K_list.append(K_i)
    ####
    # ---- Mixer PZ -> SZ (pesato sulle portate) ----
    def build_mixed_reservoir_from_branches(reactors, mdot_branches, p_target):
        gmix = ct.Solution(mech, phase)
        w = np.array(mdot_branches); w /= max(w.sum(), 1e-30)
        Y_mix = np.zeros(gmix.n_species); h_mix = 0.0
        for k, rloc in enumerate(reactors):
            # Ora rloc è un ct.IdealGasReactor per tutti e 9 i rami! Funzionerà perfettamente.
            gk = ct.Solution(mech, phase); gk.TPX = rloc.T, rloc.thermo.P, rloc.thermo.X
            Y_mix += w[k] * gk.Y; h_mix += w[k] * gk.enthalpy_mass
        gmix.HPY = h_mix, p_target, Y_mix
        return gmix
    mdot_pz_nom_i = mdot_air_PZ_i + mdot_fuel_gas_injected

    # ----------------------------------------------------------------
    # SPLIT BYPASS 9B
    #   - (1-fraz_bypass_9B) di 9B entra nel mixing PZ normale
    #   - fraz_bypass_9B di 9B bypasserà la SZ normale → PFR dedicato
    # ----------------------------------------------------------------
    mdot_9B_actual  = mdot_pz_nom_i[idx_liquid_branch]
    mdot_9B_bypass  = fraz_bypass_9B * mdot_9B_actual
    mdot_9B_in_mix  = (1.0 - fraz_bypass_9B) * mdot_9B_actual
    mdot_pz_mixed   = mdot_pz_nom - mdot_9B_bypass   # portata PZ che va nel mixing

    print(f"[BYPASS 9B] mdot_9B_totale={mdot_9B_actual:.4f} kg/s | "
          f"in_mix={mdot_9B_in_mix:.4f} kg/s ({(1-fraz_bypass_9B)*100:.1f}%) | "
          f"bypass={mdot_9B_bypass:.4f} kg/s ({fraz_bypass_9B*100:.1f}%)")

    # Costruiamo il gas misto PZ con quota ridotta di 9B
    mdot_pz_nom_i_for_mix = mdot_pz_nom_i.copy()
    mdot_pz_nom_i_for_mix[idx_liquid_branch] *= (1.0 - fraz_bypass_9B)
    gas_out_PZ_mixed = build_mixed_reservoir_from_branches(pz_reactors, mdot_pz_nom_i_for_mix, p_in)

    # Diluizione soot per il gas misto PZ (solo la quota (1-bypass) di 9B)
    rho_PZ_mixed = gas_out_PZ_mixed.density
    dilution_factor_PZ_mix = (
        (mdot_9B_in_mix / max(gas_9B_out.density, 1e-30)) /
        (max(mdot_pz_mixed, 1e-30) / max(rho_PZ_mixed, 1e-30))
    )
    soot_array_PZ_mixed = psr_obj.soot_array * dilution_factor_PZ_mix

    # Soot del bypass 9B: stessa densità → nessuna diluizione volumetrica
    soot_array_9B_bypass = psr_obj.soot_array.copy()

    print(f"Temperatura gas misto PZ (senza quota bypass): {gas_out_PZ_mixed.T:.1f} K")
    
    
    
    
    
    # Per plotting PZ "globale"
    t1, T1_raw, P1_raw = pz_time_hist[0]
    T1_end = np.sum([(mdot_pz_nom_i[i]/mdot_pz_nom)*pz_time_hist[i][1][-1] for i in range(N_PZ)])
    P1_end = np.sum([(mdot_pz_nom_i[i]/mdot_pz_nom)*pz_time_hist[i][2][-1] for i in range(N_PZ)])
    T1 = T1_raw.copy(); P1 = P1_raw.copy(); T1[-1] = T1_end; P1[-1] = P1_end
    #############################################################################
    ###############################################################################
    def setup_omnisoot_reactor(psr_obj, soot_params):
        """Applica la configurazione di Omnisoot a un reattore."""
        soot = psr_obj.soot
        soot.particle_dynamics_model_type = soot_params.get("particle_dynamics_model_type", "Sectional")
        if soot.particle_dynamics_model_type == "Sectional":
            soot.particle_dynamics_model.number_of_sections = soot_params.get("number_of_sections", 60)
        soot.particle_dynamics_model.eta_coag_type = "repulsion_d_based"
        soot.PAH_growth_model_type = soot_params.get("PAH_growth_model_type", "DimerCoalescence")
        soot.set_precursor_names(soot_params.get("precursors", ["A4"]))
        soot.PAH_growth_model.inception_prefactor = soot_params.get("inception_prefactor", 1.0)
        soot.PAH_growth_model.adsorption_prefactor = soot_params.get("adsorption_prefactor", 1.0)
        soot.surface_reactions_model.alpha_model = "composition"
        if soot.PAH_growth_model_type == "DimerCoalescence":
            soot.PAH_growth_model.stick_eff = soot_params.get("dimcoal_effs", [0.002, 0.015, 0.025, 0.004])
    ##############################################################################################################
    ###############################################################################################################
    
    def run_pfr_zone(soot_gas, T_in, P_in, X_in, mdot_in, soot_array_in, area, length, soot_params, zone_name="PFR"):
        """Inizializza e risolve un Plug Flow Reactor per SZ e DZ."""
        pfr = PlugFlowReactor(soot_gas)
        
        # 1. Configurazione modelli Soot
        soot = pfr.soot
        soot.particle_dynamics_model_type = soot_params.get("particle_dynamics_model_type", "Sectional")
        if soot.particle_dynamics_model_type == "Sectional":
            soot.particle_dynamics_model.number_of_sections = soot_params.get("number_of_sections", 60)
        soot.particle_dynamics_model.eta_coag_type = "repulsion_d_based"
        soot.PAH_growth_model_type = "IrreversibleDimerization"
        soot.set_precursor_names(soot_params.get("precursors", ["A4"])) ############### INSERIRE I PRECURSORI CRECK ################
        soot.PAH_growth_model.inception_prefactor = soot_params.get("inception_prefactor", 1.0)
        soot.PAH_growth_model.adsorption_prefactor = soot_params.get("adsorption_prefactor", 1.0)
        soot.surface_reactions_model.alpha_model = "composition"
        if soot.PAH_growth_model_type == "DimerCoalescence":
            soot.PAH_growth_model.stick_eff = soot_params.get("dimcoal_effs", [0.002, 0.015, 0.025, 0.004])
        # 2. Configurazione INLET (Il "ponte" per il soot)
        pfr.inlet.TPX = T_in, P_in, X_in
        pfr.inlet.mdot = mdot_in
        pfr.inlet.soot_inlet_type = "custom"
        pfr.inlet.soot_array = soot_array_in
        
        # 3. Geometria e Solutore
        pfr.inlet_area = area
        pfr.temperature_solver_type = "energy_equation"
        pfr.solver_type = "BDF" 
        pfr.max_step = 1e-5
         
        pfr.rtol = 1e-7
        pfr.atol = 1e-10
        # 4. Avvio e Integrazione
        pfr.start()
        print(f"\n{'='*50}\n AVVIO {zone_name} (PFR | Lunghezza: {length:.3f} m)\n{'='*50}")
        print(f"Ingresso -> T: {T_in:.1f} K | mdot: {mdot_in:.4f} kg/s | fv_soot_in: {pfr.inlet.soot_array[0]:.3e}")
        
        step = 0
        # --- Raccolta profili spaziali per il plot ---
        pfr_z_hist       = []
        pfr_T_hist       = []
        pfr_fv_hist      = []
        pfr_Ym_hist      = []
        pfr_mdot_s_hist  = []
        pfr_co2_hist     = []
        rho_soot_local   = 1800.0  # kg/m^3
    
        while pfr.z < length:
            pfr.step()
            step += 1
            if step % 10 == 0: # Stampa ogni 100 step
                print(f"[{zone_name}] z={pfr.z:.4f} m | T={soot_gas.T:.1f} K | fv_soot={pfr.soot.volume_fraction:.3e} | portata in massa soot={pfr.soot.total_mass*mdot_in:.6e} kg/s")
            # Raccolta dati ad ogni step
            fv_now = pfr.soot.volume_fraction
            Ym_now = (fv_now * rho_soot_local) / max(soot_gas.density, 1e-30)
            mdot_s_now = Ym_now * mdot_in
            try:
                idx_co2 = soot_gas.species_index("CO2")
                co2_now = soot_gas.X[idx_co2]
            except Exception:
                co2_now = 0.0
            pfr_z_hist.append(pfr.z)
            pfr_T_hist.append(soot_gas.T)
            pfr_fv_hist.append(fv_now)
            pfr_Ym_hist.append(Ym_now)
            pfr_mdot_s_hist.append(mdot_s_now)
            pfr_co2_hist.append(co2_now)
                
        print(f"{'-'*50}\nCOMPLETATO {zone_name} -> T_out: {soot_gas.T:.1f} K | fv_soot_out: {pfr.soot.volume_fraction:.3e}\n{'='*50}\n")
        # Aggiungiamo gli array raccolti come attributi dell'oggetto pfr per il post-processing
        pfr.plot_z    = np.array(pfr_z_hist)
        pfr.plot_T    = np.array(pfr_T_hist)
        pfr.plot_fv   = np.array(pfr_fv_hist)
        pfr.plot_Ym   = np.array(pfr_Ym_hist)
        pfr.plot_mdot = np.array(pfr_mdot_s_hist)
        pfr.plot_co2  = np.array(pfr_co2_hist)
        return pfr
    
    ##########################################################################################################################
    ##########################################################################################################################
    # =====================================================================
    # HELPER: PFR risolto solo con Cantera (senza soot)
    # =====================================================================
    def run_pfr_cantera_only(gas_in, mdot_in, area, length, soot_array_ref, zone_name="PFR_cantera"):
        """
        Simula un Plug Flow Reactor usando solo Cantera (nessun modello soot).
        Restituisce un oggetto compatibile con il post-processing (plot_* e soot_array zero)
        e il gas di uscita come ct.Solution.
        """
        gas = ct.Solution(mech, phase)
        gas.TPX = gas_in.T, gas_in.P, gas_in.X

        r   = ct.IdealGasConstPressureReactor(gas)
        sim = ct.ReactorNet([r])

        pfr_z_hist      = []
        pfr_T_hist      = []
        pfr_fv_hist     = []
        pfr_Ym_hist     = []
        pfr_mdot_s_hist = []
        pfr_co2_hist    = []

        idx_co2_sp = gas.species_index("CO2") if "CO2" in gas.species_names else -1

        n_steps = 500
        dz = length / n_steps
        z  = 0.0
        t  = 0.0

        print(f"\n{'='*50}\n AVVIO {zone_name} (PFR Cantera-only | L: {length:.3f} m)\n{'='*50}")
        print(f"Ingresso -> T: {gas.T:.1f} K | mdot: {mdot_in:.4f} kg/s | (soot=0 by definition)")

        for _ in range(n_steps):
            u  = mdot_in / max(gas.density * area, 1e-30)
            dt = dz / max(u, 1e-30)
            t += dt
            try:
                sim.advance(t)
            except Exception as e:
                print(f"[WARN] {zone_name} sim.advance() errore: {e}")
                break
            z += dz
            co2_now = gas.X[idx_co2_sp] if idx_co2_sp >= 0 else 0.0
            pfr_z_hist.append(z)
            pfr_T_hist.append(gas.T)
            pfr_fv_hist.append(0.0)
            pfr_Ym_hist.append(0.0)
            pfr_mdot_s_hist.append(0.0)
            pfr_co2_hist.append(co2_now)

        print(f"{'-'*50}\nCOMPLETATO {zone_name} -> T_out: {gas.T:.1f} K | fv_soot_out: 0.000e+00\n{'='*50}\n")

        class _PFRResult:
            pass
        res = _PFRResult()
        res.plot_z    = np.array(pfr_z_hist)
        res.plot_T    = np.array(pfr_T_hist)
        res.plot_fv   = np.array(pfr_fv_hist)
        res.plot_Ym   = np.array(pfr_Ym_hist)
        res.plot_mdot = np.array(pfr_mdot_s_hist)
        res.plot_co2  = np.array(pfr_co2_hist)
        res.soot_array = np.zeros_like(soot_array_ref)

        class _FakeSoot:
            volume_fraction = 0.0
        res.soot = _FakeSoot()

        # Restituiamo anche il gas Cantera aggiornato
        gas_out = ct.Solution(mech, phase)
        gas_out.TPX = gas.T, gas.P, gas.X
        return res, gas_out

    ##########################################################################################################################
    ##########################################################################################################################
    # =====================================================================
    # 5. SECONDARY ZONE (SZ) - 2 PFR IN PARALLELO
    #    Ramo 0: Cantera only (no soot) - riceve TUTTO il gas misto PZ + TUTTA l'aria SZ
    #    Ramo 1: omnisoot (bypass 9B)   - riceve l'intera quota bypass di 9B, no aria aggiuntiva
    # =====================================================================
    print("\n=== CALCOLO SECONDARY ZONE (SZ - 2 PFR PARALLELI) ===")

    N_SZ = 2

    sz_gases_out       = []
    sz_soot_arrays_out = []
    sz_mdots           = []
    sz_pfr_objects     = []

    Lunghezza_SZ  = LRSZ
    Area_SZ_tot   = V2 / Lunghezza_SZ

    for k in range(N_SZ):
        print(f"\n--- Avvio SZ Ramo {k+1}/{N_SZ} ---")

        if k == 0:
            # ---- Ramo 0: tutto gas PZ mixed + tutta aria SZ (Cantera only) ----
            mdot_pz_k  = mdot_pz_mixed          # intero flusso PZ (escluso bypass 9B)
            mdot_air_k = mdot_air_SZa            # tutta l'aria SZ
            mdot_sz_k  = mdot_pz_k + mdot_air_k
            gas_in_k   = mix_streams_mass(gas_out_PZ_mixed, mdot_pz_k, air_stream, mdot_air_k, p_in, T_in)
            rho_in_k   = gas_in_k.density
            dilution_factor_k = (mdot_pz_k / max(mdot_sz_k, 1e-30)) * (rho_in_k / max(gas_out_PZ_mixed.density, 1e-30))
            soot_array_in_k   = soot_array_PZ_mixed * dilution_factor_k
        else:
            # ---- Ramo 1: bypass 9B completo (omnisoot, nessuna aria aggiuntiva) ----
            # Includiamo anche il fuel NON evaporato in 9B, che viene ora iniettato
            # in fase vapore all'ingresso di questo PFR (mescolamento entalpico).
            mdot_9B_gas    = mdot_9B_bypass
            mdot_unvap_sz  = mdot_fuel_unvap  # fuel rimasto non evaporato da 9B

            if mdot_unvap_sz > 1e-12:
                # Mescoliamo entalpicamente gas_for_reservoir + fuel puro in vapore
                gas_unvap = ct.Solution(mech, phase)
                gas_unvap.TPX = T_in, p_in, fuel_comp_str   # fuel a T_in (vapore freddo)
                mdot_sz_k  = mdot_9B_gas + mdot_unvap_sz
                # Bilancio massa
                Y_9B  = gas_for_reservoir.Y
                Y_fv  = gas_unvap.Y
                Y_mix_sz1 = (mdot_9B_gas * Y_9B + mdot_unvap_sz * Y_fv) / mdot_sz_k
                # Bilancio entalpico
                h_9B  = gas_for_reservoir.enthalpy_mass
                h_fv  = gas_unvap.enthalpy_mass
                h_mix_sz1 = (mdot_9B_gas * h_9B + mdot_unvap_sz * h_fv) / mdot_sz_k
                gas_in_k = ct.Solution(mech, phase)
                gas_in_k.HPY = h_mix_sz1, p_in, Y_mix_sz1
                print(f"[SZ Ramo 1] Fuel non evaporato iniettato come vapore: "
                      f"mdot_unvap={mdot_unvap_sz*1e3:.3f} g/s | "
                      f"mdot_tot_SZ1={mdot_sz_k:.5f} kg/s | "
                      f"T_mix={gas_in_k.T:.1f} K")
            else:
                mdot_sz_k  = mdot_9B_gas
                gas_in_k   = gas_for_reservoir
                print(f"[SZ Ramo 1] Nessun fuel non evaporato (mdot_unvap≈0).")

            rho_in_k        = gas_in_k.density
            soot_array_in_k = soot_array_9B_bypass.copy()

        sz_mdots.append(mdot_sz_k)
        Area_k = Area_SZ_tot * (mdot_sz_k / max(mdot_sz_nom, 1e-30))

        if k == 0:
            # ---- RAMO 0: Cantera only ----
            pfr_k, gas_out_k = run_pfr_cantera_only(
                gas_in        = gas_in_k,
                mdot_in       = mdot_sz_k,
                area          = Area_k,
                length        = Lunghezza_SZ,
                soot_array_ref= psr_obj.soot_array,
                zone_name     = "SZ RAMO 1 (Cantera - PZ+aria)"
            )
            sz_gases_out.append(gas_out_k)
            sz_soot_arrays_out.append(pfr_k.soot_array)
            sz_pfr_objects.append(pfr_k)
        else:
            # ---- RAMO 1: omnisoot bypass 9B ----
            soot_gas_k = SootGas(gas_in_k)
            pfr_k = run_pfr_zone(
                soot_gas      = soot_gas_k,
                T_in          = gas_in_k.T,
                P_in          = gas_in_k.P,
                X_in          = gas_in_k.X,
                mdot_in       = mdot_sz_k,
                soot_array_in = soot_array_in_k,
                area          = Area_k,
                length        = Lunghezza_SZ,
                soot_params   = soot_params,
                zone_name     = "SZ RAMO 2 (omnisoot - bypass 9B)"
            )
            gas_out_k = ct.Solution(mech, phase)
            gas_out_k.TPX = soot_gas_k.T, soot_gas_k.P, soot_gas_k.X
            sz_gases_out.append(gas_out_k)
            sz_soot_arrays_out.append(pfr_k.soot_array)
            sz_pfr_objects.append(pfr_k)

    # =====================================================================
    # SPLIT BYPASS SZ1
    #   L'uscita del Ramo 1 omnisoot SZ viene divisa:
    #   - (1-fraz_bypass_SZ1) entra nel mixing SZ → DZ Ramo 0 (Cantera)
    #   - fraz_bypass_SZ1     bypassa il mixing SZ → DZ Ramo 1 (omnisoot)
    # =====================================================================
    mdot_SZ1_total  = sz_mdots[1]
    mdot_SZ1_in_mix = (1.0 - fraz_bypass_SZ1) * mdot_SZ1_total   # quota → mixing SZ
    mdot_SZ1_bypass = fraz_bypass_SZ1          * mdot_SZ1_total   # quota → DZ Ramo 1

    print(f"[BYPASS SZ1] mdot_SZ1_totale={mdot_SZ1_total:.4f} kg/s | "
          f"in_mix={mdot_SZ1_in_mix:.4f} kg/s ({(1-fraz_bypass_SZ1)*100:.1f}%) | "
          f"bypass_DZ={mdot_SZ1_bypass:.4f} kg/s ({fraz_bypass_SZ1*100:.1f}%)")

    # Gas e soot del ramo bypass SZ1 → DZ Ramo 1
    gas_SZ_bypass_out        = sz_gases_out[1]
    soot_array_SZ_bypass_out = sz_soot_arrays_out[1].copy()
    mdot_SZ_bypass_out       = mdot_SZ1_bypass

    # =====================================================================
    # MIXING SZ → ingresso DZ Ramo 0
    # Contribuiscono: Ramo 0 SZ (Cantera, portata intera) +
    #                 quota (1-fraz_bypass_SZ1) del Ramo 1 SZ (omnisoot)
    # =====================================================================
    print("\n--- Mixing SZ: Ramo 0 Cantera + quota Ramo 1 omnisoot ---")
    rho_soot = 1800.0

    mdot_sz_to_mix = sz_mdots[0] + mdot_SZ1_in_mix

    # Portata soot verso il mixing
    fv_sz0 = sz_pfr_objects[0].soot.volume_fraction
    rho_sz0 = sz_gases_out[0].density
    fv_sz1 = sz_pfr_objects[1].soot.volume_fraction
    rho_sz1 = sz_gases_out[1].density
    mdot_soot_sz_out = (
        (fv_sz0 * rho_soot / max(rho_sz0, 1e-10)) * sz_mdots[0]
      + (fv_sz1 * rho_soot / max(rho_sz1, 1e-10)) * mdot_SZ1_in_mix
    )
    print(f"Portata in massa soot verso mixing SZ: {mdot_soot_sz_out:.6e} kg/s")

    # Mixing termodinamico (media pesata su entalpie e composizioni)
    h_mix_sz = (sz_mdots[0]     * sz_gases_out[0].enthalpy_mass
              + mdot_SZ1_in_mix * sz_gases_out[1].enthalpy_mass) / max(mdot_sz_to_mix, 1e-30)
    Y_mix_sz = (sz_mdots[0]     * sz_gases_out[0].Y
              + mdot_SZ1_in_mix * sz_gases_out[1].Y) / max(mdot_sz_to_mix, 1e-30)

    gas_out_SZ_mixed = ct.Solution(mech, phase)
    gas_out_SZ_mixed.HPY = h_mix_sz, p_in, Y_mix_sz
    rho_out_SZ_mixed = gas_out_SZ_mixed.density

    # Mixing soot array (conservazione flusso particelle #/s)
    Vdot_SZ_mixed = mdot_sz_to_mix / max(rho_out_SZ_mixed, 1e-30)
    Vdot_sz0  = sz_mdots[0]     / max(rho_sz0,              1e-30)
    Vdot_sz1m = mdot_SZ1_in_mix / max(rho_sz1,              1e-30)
    soot_array_SZ_mixed = (
        sz_soot_arrays_out[0] * (Vdot_sz0  / max(Vdot_SZ_mixed, 1e-30))
      + sz_soot_arrays_out[1] * (Vdot_sz1m / max(Vdot_SZ_mixed, 1e-30))
    )

    print(f"Temperatura mixing uscita SZ: {gas_out_SZ_mixed.T:.1f} K")
    
    
    # =====================================================================
    # 6. DILUTION ZONE (DZ) - 2 PFR IN PARALLELO
    #    Ramo 0: Cantera only (no soot) - riceve TUTTO il gas SZ mixed + TUTTA l'aria DZ
    #    Ramo 1: omnisoot (bypass 9B)   - riceve l'uscita del Ramo 1 SZ (bypass 9B), no aria
    # =====================================================================
    print("\n=== CALCOLO DILUTION ZONE (DZ - 2 PFR PARALLELI) ===")

    N_DZ = 2

    mdot_dz_nom = mdot_sz_nom + mdot_air_DZa   # conservazione massa globale invariata
    rho_out_SZ_mixed = gas_out_SZ_mixed.density

    dz_gases_out       = []
    dz_soot_arrays_out = []
    dz_fv_out          = []
    dz_mdots           = []
    dz_pfr_objects     = []

    Lunghezza_DZ = LRDZ
    Area_DZ_tot  = V3 / Lunghezza_DZ

    for k in range(N_DZ):
        print(f"\n--- Avvio DZ Ramo {k+1}/{N_DZ} ---")

        if k == 0:
            # ---- Ramo 0: tutto gas SZ mixed + tutta aria DZ (Cantera only) ----
            mdot_sz_in_k = mdot_sz_to_mix       # intero flusso SZ Ramo 0
            mdot_air_k   = mdot_air_DZa          # tutta l'aria DZ
            mdot_dz_k    = mdot_sz_in_k + mdot_air_k
            dz_mdots.append(mdot_dz_k)

            gas_in_k = mix_streams_mass(gas_out_SZ_mixed, mdot_sz_in_k, air_stream, mdot_air_k, p_in, T_in)
            rho_in_k = gas_in_k.density

            dilution_factor_k = (mdot_sz_in_k / max(mdot_dz_k, 1e-30)) * (rho_in_k / max(rho_out_SZ_mixed, 1e-30))
            soot_array_in_k   = soot_array_SZ_mixed * dilution_factor_k

            Area_k = Area_DZ_tot * (mdot_dz_k / max(mdot_dz_nom, 1e-30))

            pfr_k, gas_out_k = run_pfr_cantera_only(
                gas_in         = gas_in_k,
                mdot_in        = mdot_dz_k,
                area           = Area_k,
                length         = Lunghezza_DZ,
                soot_array_ref = psr_obj.soot_array,
                zone_name      = "DZ RAMO 1 (Cantera - SZ+aria)"
            )
            dz_gases_out.append(gas_out_k)
            dz_soot_arrays_out.append(pfr_k.soot_array)
            dz_fv_out.append(0.0)
            dz_pfr_objects.append(pfr_k)

        else:
            # ---- Ramo 1: uscita Ramo 1 SZ (bypass 9B) - omnisoot, nessuna aria aggiuntiva ----
            mdot_dz_k = mdot_SZ_bypass_out
            dz_mdots.append(mdot_dz_k)

            soot_array_in_k = soot_array_SZ_bypass_out.copy()
            Area_k = Area_DZ_tot * (mdot_dz_k / max(mdot_dz_nom, 1e-30))

            soot_gas_k = SootGas(gas_SZ_bypass_out)
            pfr_k = run_pfr_zone(
                soot_gas      = soot_gas_k,
                T_in          = gas_SZ_bypass_out.T,
                P_in          = gas_SZ_bypass_out.P,
                X_in          = gas_SZ_bypass_out.X,
                mdot_in       = mdot_dz_k,
                soot_array_in = soot_array_in_k,
                area          = Area_k,
                length        = Lunghezza_DZ,
                soot_params   = soot_params,
                zone_name     = "DZ RAMO 2 (omnisoot - bypass 9B da SZ)"
            )
            gas_out_k = ct.Solution(mech, phase)
            gas_out_k.TPX = soot_gas_k.T, soot_gas_k.P, soot_gas_k.X
            dz_gases_out.append(gas_out_k)
            dz_soot_arrays_out.append(pfr_k.soot_array)
            dz_fv_out.append(pfr_k.soot.volume_fraction)
            dz_pfr_objects.append(pfr_k)
    
    # =====================================================================
    # 7. POST-PROCESSING: MIXING FINALE E RISULTATI
    # =====================================================================
    print("\n--- Rimescolamento dei rami della DZ per lo scarico ---")

    # Portata totale effettiva DZ: ramo 0 (SZ mixed + aria DZ) + ramo 1 (bypass 9B da SZ)
    mdot_dz_nom_eff = sum(dz_mdots)

    # A. Mixing Termodinamico (Media pesata delle entalpie e composizioni)
    h_mix_dz = 0.0
    Y_mix_dz = np.zeros(gas_out_SZ_mixed.n_species)
    
    for k in range(N_DZ):
        h_mix_dz += dz_mdots[k] * dz_gases_out[k].enthalpy_mass
        Y_mix_dz += dz_mdots[k] * dz_gases_out[k].Y
    
    h_mix_dz /= max(mdot_dz_nom_eff, 1e-30)
    Y_mix_dz /= max(mdot_dz_nom_eff, 1e-30)
    
    gas_out_DZ_mixed = ct.Solution(mech, phase)
    gas_out_DZ_mixed.HPY = h_mix_dz, p_in, Y_mix_dz
    rho_out_DZ_mixed = gas_out_DZ_mixed.density
    
    # B. Mixing del Soot (Media pesata sui flussi volumetrici)
    fv_soot_out = 0.0
    Vdot_DZ_mixed = mdot_dz_nom_eff / rho_out_DZ_mixed
    
    for k in range(N_DZ):
        Vdot_k = dz_mdots[k] / dz_gases_out[k].density
        # Calcolo della frazione volumetrica combinata
        fv_soot_out += dz_fv_out[k] * (Vdot_k / Vdot_DZ_mixed)
    
    print("\n=== RISULTATI FINALI MOTORE ED EMISSIONI ===")
    
   ####rho_gas_out = rho_out_DZ_mixed
   ####rho_soot = 1800.0  # kg/m^3
   ####
   ####Y_soot_out = (fv_soot_out * rho_soot) / rho_gas_out
   ####mdot_soot_out = Y_soot_out * mdot_dz_nom
    rho_soot = 1800.0
    mdot_soot_out = 0.0
    for k in range(N_DZ):
        fv_k = dz_fv_out[k]
        rho_k = dz_gases_out[k].density
        Y_soot_k = (fv_k * rho_soot) / max(rho_k, 1e-10)
        mdot_soot_out += Y_soot_k * dz_mdots[k]
    mdot_fuel = mdot_air * FAR  
    EI_Soot = (mdot_soot_out / mdot_fuel) * 1000.0  # g_soot / kg_fuel
    
    print(f"Temperatura allo scarico motore : {gas_out_DZ_mixed.T:.1f} K")
    print(f"Frazione volumetrica soot (fv)  : {fv_soot_out:.3e}")
    #print(f"Frazione massica soot (Y_soot)  : {Y_soot_out:.3e}")
    print(f"Portata massica soot emessa     : {mdot_soot_out:.3e} kg/s")
    print(f"--------------------------------------------------")
    print(f" EI_Soot FINALE                 : {EI_Soot:.4f} g/kg_fuel")
    print(f"--------------------------------------------------\n")
    
    # =====================================================================
   # # 8. PLOTTING: PSR (tempo) + PFR SZ e DZ (spazio)
   # # =====================================================================
   # import matplotlib.gridspec as gridspec
   # 
   # # ---- Colori e stile ----
   # colors_sz = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
   # colors_dz = ['#9467bd', '#8c564b', '#e377c2', '#7f7f7f']
   # 
   # # =====================================================================
   # # FIGURA 1: PSR Ramo Liquido 9B — portata in massa di soot nel tempo
   # # =====================================================================
   # fig1, ax1 = plt.subplots(figsize=(8, 4))
   # if len(psr_time_arr) > 0:
   #     ax1.plot(psr_time_arr * 1e3, psr_mdot_soot_arr * 1e6,
   #              color='#d62728', linewidth=2, label='Ramo liquido 9B (PSR)')
   #     ax1.set_xlabel('Tempo di residenza [ms]', fontsize=12)
   #     ax1.set_ylabel('Portata in massa soot [µg/s]', fontsize=12)
   #     ax1.set_title('PSR Zona Primaria — Portata in massa soot vs tempo', fontsize=13, fontweight='bold')
   #     ax1.legend(fontsize=10)
   #     ax1.grid(True, linestyle='--', alpha=0.5)
   #     ax1.set_xlim(left=0)
   # else:
   #     ax1.text(0.5, 0.5, 'Nessun dato PSR disponibile', ha='center', va='center',
   #              transform=ax1.transAxes, fontsize=14, color='gray')
   # fig1.tight_layout()
   # fig1.savefig('plot_PSR_mdot_soot.png', dpi=150)
   # print("Salvato: plot_PSR_mdot_soot.png")
   # 
   # # =====================================================================
   # # FIGURA 2: PFR Secondary Zone — profili spaziali (tutti i rami)
   # # =====================================================================
   # fig2, axes2 = plt.subplots(2, 3, figsize=(16, 9))
   # fig2.suptitle('Secondary Zone (SZ) — Profili lungo la coordinata assiale x\n'
   #               '(Ramo 1: Cantera-only, PZ+aria | Ramo 2: omnisoot, bypass 9B → split verso DZ)',
   #               fontsize=13, fontweight='bold')
   # 
   # ax_mdot_sz, ax_Ym_sz, ax_fv_sz = axes2[0]
   # ax_T_sz, ax_co2_sz, ax_empty_sz = axes2[1]
   # 
   # sz_labels = ['SZ Ramo 1 (Cantera - PZ+aria)', 'SZ Ramo 2 (omnisoot - bypass 9B)']
   # for k, pfr_k in enumerate(sz_pfr_objects):
   #     lbl = sz_labels[k] if k < len(sz_labels) else f'SZ Ramo {k+1}'
   #     c   = colors_sz[k % len(colors_sz)]
   #     if len(pfr_k.plot_z) == 0:
   #         continue
   #     z = pfr_k.plot_z
   #     ax_mdot_sz.plot(z, pfr_k.plot_mdot * 1e6, color=c, linewidth=1.8, label=lbl)
   #     ax_Ym_sz.plot(z,   pfr_k.plot_Ym,          color=c, linewidth=1.8, label=lbl)
   #     ax_fv_sz.plot(z,   pfr_k.plot_fv,           color=c, linewidth=1.8, label=lbl)
   #     ax_T_sz.plot(z,    pfr_k.plot_T,            color=c, linewidth=1.8, label=lbl)
   #     ax_co2_sz.plot(z,  pfr_k.plot_co2,          color=c, linewidth=1.8, label=lbl)
   # 
   # for ax, ylabel, title in [
   #     (ax_mdot_sz, 'Portata in massa soot [µg/s]',   'Portata in massa soot'),
   #     (ax_Ym_sz,   'Frazione in massa soot [-]',       'Frazione in massa soot'),
   #     (ax_fv_sz,   'Frazione volumetrica soot [-]',    'Frazione volumetrica soot'),
   #     (ax_T_sz,    'Temperatura [K]',                  'Temperatura'),
   #     (ax_co2_sz,  'X$_{CO_2}$ [mol/mol]',             'Concentrazione CO\u2082 (fraz. molare)'),
   # ]:
   #     ax.set_xlabel('Posizione assiale x [m]', fontsize=10)
   #     ax.set_ylabel(ylabel, fontsize=10)
   #     ax.set_title(title, fontsize=11, fontweight='bold')
   #     ax.legend(fontsize=8)
   #     ax.grid(True, linestyle='--', alpha=0.5)
   # 
   # ax_empty_sz.axis('off')
   # fig2.tight_layout()
   # fig2.savefig('plot_SZ_PFR_profiles.png', dpi=150)
   # print("Salvato: plot_SZ_PFR_profiles.png")
   # 
   # # =====================================================================
   # # FIGURA 3: PFR Dilution Zone — profili spaziali (tutti i rami)
   # # =====================================================================
   # fig3, axes3 = plt.subplots(2, 3, figsize=(16, 9))
   # fig3.suptitle('Dilution Zone (DZ) — Profili lungo la coordinata assiale x\n'
   #               '(Ramo 1: Cantera-only, SZ mixed+aria | Ramo 2: omnisoot, bypass SZ1)',
   #               fontsize=13, fontweight='bold')
   # 
   # ax_mdot_dz, ax_Ym_dz, ax_fv_dz = axes3[0]
   # ax_T_dz, ax_co2_dz, ax_empty_dz = axes3[1]
   # 
   # dz_labels = ['DZ Ramo 1 (Cantera - SZ mixed+aria)', 'DZ Ramo 2 (omnisoot - bypass SZ1)']
   # for k, pfr_k in enumerate(dz_pfr_objects):
   #     lbl = dz_labels[k] if k < len(dz_labels) else f'DZ Ramo {k+1}'
   #     c   = colors_dz[k % len(colors_dz)]
   #     if len(pfr_k.plot_z) == 0:
   #         continue
   #     z = pfr_k.plot_z
   #     ax_mdot_dz.plot(z, pfr_k.plot_mdot * 1e6, color=c, linewidth=1.8, label=lbl)
   #     ax_Ym_dz.plot(z,   pfr_k.plot_Ym,          color=c, linewidth=1.8, label=lbl)
   #     ax_fv_dz.plot(z,   pfr_k.plot_fv,           color=c, linewidth=1.8, label=lbl)
   #     ax_T_dz.plot(z,    pfr_k.plot_T,            color=c, linewidth=1.8, label=lbl)
   #     ax_co2_dz.plot(z,  pfr_k.plot_co2,          color=c, linewidth=1.8, label=lbl)
   # 
   # for ax, ylabel, title in [
   #     (ax_mdot_dz, 'Portata in massa soot [µg/s]',   'Portata in massa soot'),
   #     (ax_Ym_dz,   'Frazione in massa soot [-]',       'Frazione in massa soot'),
   #     (ax_fv_dz,   'Frazione volumetrica soot [-]',    'Frazione volumetrica soot'),
   #     (ax_T_dz,    'Temperatura [K]',                  'Temperatura'),
   #     (ax_co2_dz,  'X$_{CO_2}$ [mol/mol]',             'Concentrazione CO\u2082 (fraz. molare)'),
   # ]:
   #     ax.set_xlabel('Posizione assiale x [m]', fontsize=10)
   #     ax.set_ylabel(ylabel, fontsize=10)
   #     ax.set_title(title, fontsize=11, fontweight='bold')
   #     ax.legend(fontsize=8)
   #     ax.grid(True, linestyle='--', alpha=0.5)
   # 
   # ax_empty_dz.axis('off')
   # fig3.tight_layout()
   # fig3.savefig('plot_DZ_PFR_profiles.png', dpi=150)
   # print("Salvato: plot_DZ_PFR_profiles.png")
   # 
   # plt.show()
   # print("\n=== PLOTTING COMPLETATO ===")
   # # Estrai le liste degli array dell'asse Z
   # z_arrays_sz = [pfr_k.plot_z for pfr_k in sz_pfr_objects if len(pfr_k.plot_z) > 0]
   # z_arrays_dz = [pfr_k.plot_z for pfr_k in dz_pfr_objects if len(pfr_k.plot_z) > 0]
   # 
   # # OPZIONALE: se vuoi plottare a posteriori, ti serviranno anche le variabili Y!
   # # Ad esempio per la frazione volumetrica (fv):
    fv_arrays_sz = [pfr_k.plot_fv for pfr_k in sz_pfr_objects if len(pfr_k.plot_z) > 0]
    fv_arrays_dz = [pfr_k.plot_fv for pfr_k in dz_pfr_objects if len(pfr_k.plot_z) > 0]
    soot_mdot_arrays_sz = [pfr_k.plot_mdot for pfr_k in sz_pfr_objects if len(pfr_k.plot_z) > 0]
    soot_mdot_arrays_dz = [pfr_k.plot_mdot for pfr_k in dz_pfr_objects if len(pfr_k.plot_z) > 0]
    co2_arrays_sz = [pfr_k.plot_co2 for pfr_k in sz_pfr_objects if len(pfr_k.plot_z) > 0]
    co2_arrays_dz = [pfr_k.plot_co2 for pfr_k in dz_pfr_objects if len(pfr_k.plot_z) > 0]
    temperature_arrays_sz = [pfr_k.plot_T for pfr_k in sz_pfr_objects if len(pfr_k.plot_z) > 0]
    temperature_arrays_dz = [pfr_k.plot_T for pfr_k in dz_pfr_objects if len(pfr_k.plot_z) > 0]
    Y_soot_arrays_sz = [pfr_k.plot_Ym for pfr_k in sz_pfr_objects if len(pfr_k.plot_z) > 0]
    Y_soot_arrays_dz = [pfr_k.plot_Ym for pfr_k in dz_pfr_objects if len(pfr_k.plot_z) > 0]
    

    return {
        "EI_Soot": EI_Soot, 
        "fv_arrays_sz": fv_arrays_sz, 
        "fv_arrays_dz": fv_arrays_dz, 
        "soot_mdot_arrays_sz": soot_mdot_arrays_sz, 
        "soot_mdot_arrays_dz": soot_mdot_arrays_dz, 
        "co2_arrays_sz": co2_arrays_sz, 
        "co2_arrays_dz": co2_arrays_dz, 
        "temperature_arrays_sz": temperature_arrays_sz, 
        "temperature_arrays_dz": temperature_arrays_dz, 
        "Y_soot_arrays_sz": Y_soot_arrays_sz, 
        "Y_soot_arrays_dz": Y_soot_arrays_dz, 
        "psr_time_arr": psr_time_arr, 
        "psr_mdot_soot_arr": psr_mdot_soot_arr, 
        "sz_pfr_objects": sz_pfr_objects, 
        "dz_pfr_objects": dz_pfr_objects, 
        "gas_out_SZ_mixed": gas_out_SZ_mixed, 
        "gas_out_DZ_mixed": gas_out_DZ_mixed, 
        "fv_soot_out": fv_soot_out, 
        "sz_gases_out": sz_gases_out, 
        "dz_gases_out": dz_gases_out
    }