# -*- coding: utf-8 -*-
"""
crn_evap_emissions.py
=====================
CRN evaporativo CFM56 – funzione autonoma per il calcolo delle emissioni.

Interfaccia pubblica
--------------------
    EI_NOx, EI_CO = compute_emissions(
        T_in,           # temperatura ingresso combustore [K]
        p_in_bar,       # pressione ingresso combustore [bar]
        mdot_air,       # portata massica aria [kg/s]
        FAR,            # fuel-to-air ratio [-]
        dPqP,           # rapporto pressione uscita/ingresso (es. 0.9476) [-]
        chi_mixer_scale # parametro di scala mixer (calibrato sui 4 anchor) [-]
    )

Restituisce
-----------
    EI_NOx : float  – Emission Index NOx [g/kg_fuel]
    EI_CO  : float  – Emission Index CO  [g/kg_fuel]

Meccanismo Cantera
------------------
    mech  = "kerosene_surrogate_luche.yaml"
    phase = "gas"

Valori anchor calibrati (MODE_DATA nel vecchio script)
------------------------------------------------------
    ID  (Idle)     : chi_mixer_scale = 1.50
    AP  (Approach) : chi_mixer_scale = 1.271698
    CL  (Climb)    : chi_mixer_scale = 1.071202
    TO  (Take-Off) : chi_mixer_scale = 1.0
"""

import cantera as ct
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# Configurazione meccanismo
# ─────────────────────────────────────────────────────────────────────────────
_MECH  = "kerosene_surrogate_luche.yaml"
_PHASE = "gas"

# ─────────────────────────────────────────────────────────────────────────────
# Geometria combustore (fissa)
# ─────────────────────────────────────────────────────────────────────────────
_Aref  = 0.160
_L     = 0.178
_ARPZ  = 30.82 / 100.0
_ARSZ  = 23.02 / 100.0
_ARDZ  = 46.15 / 100.0
_LRPZ  = 0.2029
_LRSZ  = 0.1979
_LRDZ  = 1.0 - _LRPZ - _LRSZ

_V1_total = _Aref * (_L * _LRPZ)
_V2       = _Aref * (_L * _LRSZ)
_V3       = _Aref * (_L * _LRDZ)
_N_PZ     = 9
_V1_i     = _V1_total / _N_PZ
_T_ign    = 1800.0   # K – temperatura iniziale reattori (gas inerte)

# Stechiometria cherosene surrogate
_FAR_ST   = 0.06768662509412701

# ─────────────────────────────────────────────────────────────────────────────
# Utility interne
# ─────────────────────────────────────────────────────────────────────────────

def _get_comp_string(gas):
    return ", ".join(
        f"{sp}:{gas.X[i]:.6g}"
        for i, sp in enumerate(gas.species_names)
        if gas.X[i] > 0
    )

def _ramp01_exp(t, tau):
    tau = max(tau, 1e-12)
    return 1.0 - np.exp(-max(0.0, t) / tau)

def _mu_air_sutherland(T):
    """Viscosità dinamica aria con formula di Sutherland [Pa·s]."""
    return 1.458e-6 * (T ** 1.5) / (T + 110.4)

def _gaussian_weights_phi(phi_mean, sigma, n_pts):
    deltas = np.linspace(-2.0 * sigma, 2.0 * sigma, n_pts)
    phi_i  = phi_mean + deltas
    w_raw  = np.exp(-(deltas ** 2) / (sigma ** 2 + 1e-30))
    w_i    = w_raw / np.sum(w_raw)
    return phi_i, w_i

def _integrate_stage_stepwise(sim, reactor, t0,
                               tol_T_rel=1e-7, tol_P_rel=1e-7,
                               n_consec_ok=60, t_cap=0.5):
    t_list, T_list, P_list = [], [], []
    t_final = t0
    consec  = 0
    EPS     = 1e-15
    T_prev, P_prev = reactor.T, reactor.thermo.P
    while (t_final < t0 + t_cap - EPS) and (consec < n_consec_ok):
        t_final = sim.step()
        T_now, P_now = reactor.T, reactor.thermo.P
        t_list.append(t_final)
        T_list.append(T_now)
        P_list.append(P_now)
        ok_T   = abs(T_now - T_prev) <= tol_T_rel * max(1.0, T_now)
        ok_P   = abs(P_now - P_prev) <= tol_P_rel * max(1.0, P_now)
        consec = consec + 1 if (ok_T and ok_P) else 0
        T_prev, P_prev = T_now, P_now
    return np.array(t_list), np.array(T_list), np.array(P_list), t_final

def _mix_streams_mass(gas_prev_out, mdot_prev, gas_add_like_air, mdot_add,
                      p_target, T_air_for_h):
    """Miscela due portate (entalpia + composizione) e restituisce un ct.Solution."""
    gmix  = ct.Solution(_MECH, _PHASE)
    Y_prev = np.zeros(gmix.n_species)
    Y_add  = np.zeros(gmix.n_species)
    smap_prev = {s: i for i, s in enumerate(gas_prev_out.species_names)}
    smap_add  = {s: i for i, s in enumerate(gas_add_like_air.species_names)}
    for j, s in enumerate(gmix.species_names):
        if s in smap_prev:
            Y_prev[j] = gas_prev_out.Y[smap_prev[s]]
        if s in smap_add:
            Y_add[j]  = gas_add_like_air.Y[smap_add[s]]
    mdot_tot = mdot_prev + mdot_add
    Y_mix    = (mdot_prev * Y_prev + mdot_add * Y_add) / max(mdot_tot, 1e-30)

    h_prev = gas_prev_out.enthalpy_mass
    g_air  = ct.Solution(_MECH, _PHASE)
    g_air.TPX = T_air_for_h, p_target, "O2:0.21, N2:0.79"
    h_add  = g_air.enthalpy_mass
    h_mix  = (mdot_prev * h_prev + mdot_add * h_add) / max(mdot_tot, 1e-30)

    gmix.HPY = h_mix, p_target, Y_mix
    return gmix

def _compute_LHV(fuel_comp_str,
                 T_ref=298.15, T_prod=423.15,
                 P_ref=ct.one_atm, oxidizer="O2:1"):
    gas_R = ct.Solution(_MECH, _PHASE)
    gas_R.TP = T_ref, P_ref
    gas_R.set_equivalence_ratio(phi=1.0, fuel=fuel_comp_str, oxidizer=oxidizer)
    h_R = gas_R.enthalpy_mass
    fuel_species = [sp.split(':')[0].strip() for sp in fuel_comp_str.split(',')]
    Y_fuel = sum(gas_R[sp].Y[0] for sp in fuel_species
                 if sp in gas_R.species_names)
    gas_P = ct.Solution(_MECH, _PHASE)
    gas_P.TPX = T_prod, P_ref, gas_R.X
    gas_P.equilibrate("TP")
    h_P = gas_P.enthalpy_mass
    return (h_R - h_P) / Y_fuel  # J/kg_fuel

def _EI_from_mass_fraction(Yk, FAR):
    """Emission Index [g/kg_fuel] dalla frazione massica."""
    return ((1.0 + FAR) / FAR) * Yk * 1e3

def _vap_after_decomp_from_T(T_in):
    """
    Frazione di vapore dopo decomposizione in funzione della T ingresso.
    Calibrata sui 4 anchor (Idle/Approach/Climb/Take-Off).
    """
    if T_in <= 540.0:
        return 0.99108
    elif T_in <= 700.0:
        return 0.99638
    else:
        return 0.99900


# ─────────────────────────────────────────────────────────────────────────────
# Funzione pubblica
# ─────────────────────────────────────────────────────────────────────────────

def compute_emissions(T_in: float,
                      p_in_bar: float,
                      mdot_air: float,
                      FAR: float,
                      dPqP: float,
                      chi_mixer_scale: float,
                      verbose: bool = False) -> tuple[float, float]:
    """
    Esegue il CRN evaporativo a 3 stadi (PZ con 9 PSR, SZ, DZ) e restituisce
    gli Emission Index di NOx e CO all'uscita del combustore.

    Parametri
    ---------
    T_in            : temperatura all'ingresso del combustore [K]
    p_in_bar        : pressione all'ingresso del combustore [bar]
    mdot_air        : portata massica aria totale [kg/s]
    FAR             : fuel-to-air ratio globale [-]
    dPqP            : rapporto p_out / p_in (perdita di carico), es. 0.9476 [-]
    chi_mixer_scale : fattore di scala sul tempo caratteristico del mixer
                      (calibrato sui 4 anchor ICAO) [-]
    verbose         : se True, stampa lo stato intermedio a schermo

    Restituisce
    -----------
    EI_NOx : float  [g/kg_fuel]
    EI_CO  : float  [g/kg_fuel]
    """

    p_in = p_in_bar * 1e5  # Pa

    # ── portate ──────────────────────────────────────────────────────────────
    mdot_fuel    = mdot_air * FAR
    mdot_pz_nom  = mdot_air * _ARPZ + mdot_fuel
    mdot_air_PZ  = mdot_air * _ARPZ
    mdot_air_SZa = mdot_air * _ARSZ
    mdot_air_DZa = mdot_air * _ARDZ
    mdot_sz_nom  = mdot_pz_nom + mdot_air_SZa
    mdot_dz_nom  = mdot_sz_nom + mdot_air_DZa

    # ── stream di base ───────────────────────────────────────────────────────
    air_stream = ct.Solution(_MECH, _PHASE)
    air_stream.TPX = T_in, p_in, "O2:0.21, N2:0.79"

    fuel_stream = ct.Solution(_MECH, _PHASE)
    fuel_stream.TPX = T_in, p_in, "NC10H22:0.74, PHC3H7:0.15, CYC9H18:0.11"
    fuel_comp_str = _get_comp_string(fuel_stream)

    # ── back pressure ────────────────────────────────────────────────────────
    P_exhaust = dPqP * p_in
    exh = ct.Solution(_MECH, _PHASE)
    exh.TP = T_in, P_exhaust
    exhaust = ct.Reservoir(exh)

    # ── tempo caratteristico PZ e rampa ──────────────────────────────────────
    rho1_0 = ct.Solution(_MECH, _PHASE)
    rho1_0.TPX = _T_ign, p_in, "N2:1.0"
    tau_res_PZ = (rho1_0.density * _V1_total) / max(mdot_pz_nom, 1e-12)

    TRAMP_IN = np.clip(0.05 * tau_res_PZ, 1e-4, 1e-2)
    scale_in = lambda t: _ramp01_exp(t, TRAMP_IN)

    # controller pressione
    eps_dp = 0.01
    K_SZ   = mdot_sz_nom / (eps_dp * p_in)
    K_DZ   = mdot_dz_nom / (eps_dp * max(p_in - P_exhaust, 1e-3))

    # ── serbatoi a monte ─────────────────────────────────────────────────────
    air_tank  = ct.Reservoir(air_stream)
    fuel_tank = ct.Reservoir(fuel_stream)

    link_PZ_SZ_mix = ct.Reservoir(ct.Solution(_MECH, _PHASE))
    link_PZ_SZ_mix.thermo.TPX = T_in, p_in, "O2:0.21, N2:0.79"
    link_PZ_SZ_mix.syncState()

    link_SZ_DZ = ct.Reservoir(ct.Solution(_MECH, _PHASE))
    link_SZ_DZ.thermo.TPX = T_in, p_in, "O2:0.21, N2:0.79"
    link_SZ_DZ.syncState()

    # ── distribuzione φ_i in PZ (gaussiana) ──────────────────────────────────
    phi_PZ_target = FAR / (_FAR_ST * _ARPZ)
    sigma_phi     = 0.15 * phi_PZ_target
    phi_i_all, w_i_all = _gaussian_weights_phi(phi_PZ_target, sigma_phi, _N_PZ)
    idx_liquid_branch  = _N_PZ - 1
    mdot_air_PZ_i      = w_i_all * mdot_air_PZ

    vap_indices = [i for i in range(_N_PZ) if i != idx_liquid_branch]
    phi_i_vap   = phi_i_all[vap_indices]
    air_i_vap   = mdot_air_PZ_i[vap_indices]

    # ── modello evaporazione (Saboohi/Lefebvre) ───────────────────────────────
    gas_prop = ct.Solution(_MECH, _PHASE)
    gas_prop.TPX = T_in, p_in, "O2:0.21, N2:0.79"
    rho_g = gas_prop.density
    try:
        mu_g = gas_prop.viscosity
    except Exception:
        mu_g = _mu_air_sutherland(T_in)

    rho_f   = 800.0
    mu_f    = 1.6e-3
    sigma_f = 0.025
    dP_f    = 3.0e6
    C_smd   = 1.6

    chi_mixer_base = 0.60
    SMD = C_smd * (mu_f ** 0.25) * (sigma_f ** 0.25) * (mdot_fuel ** 0.25) / (
        (rho_g ** 0.25) * (dP_f ** 0.5)
    )
    SMD = max(SMD, 5e-6)

    T0, P0, D0 = 300.0, 101325.0, 2.0e-5
    D_AB = D0 * (T_in / T0) ** 1.75 * (P0 / p_in)

    U_rel = np.sqrt(max(2.0 * dP_f / rho_g, 0.0))
    Re_d  = rho_g * U_rel * SMD / max(mu_g, 1e-30)
    Sc    = mu_g / max(rho_g * D_AB, 1e-30)
    Sh    = 2.0 + 0.6 * (max(Re_d, 1e-12) ** 0.5) * (max(Sc, 1e-12) ** (1.0 / 3.0))

    B_M   = 0.5
    K_base = 8.0 * D_AB * (rho_g / max(rho_f, 1e-30)) * np.log(1.0 + B_M)
    K_evp  = K_base * (Sh / 2.0)

    tau_evp   = (SMD ** 2) / max(K_evp, 1e-30)
    tau_mixer = chi_mixer_base * chi_mixer_scale * tau_res_PZ

    f_vap_model = float(
        np.clip(1.0 - np.exp(-tau_mixer / max(tau_evp, 1e-30)), 0.0, 1.0)
    )
    f_liq = 1.0 - f_vap_model

    if verbose:
        print(f"[EVAP] SMD={SMD*1e6:.2f} µm  f_vap={f_vap_model:.5f}  f_liq={f_liq:.5f}")

    # ── decomposizione liquido ────────────────────────────────────────────────
    vap_after_decomp  = _vap_after_decomp_from_T(T_in)
    f_soot            = 0.05 * f_liq
    f_after_soot      = max(f_liq - f_soot, 0.0)
    f_vap_decomp      = vap_after_decomp * f_after_soot
    mdot_fuel_from_liq = f_vap_decomp * mdot_fuel

    # ── ripartizione fuel gas nei 9 PSR ──────────────────────────────────────
    FAR_i_target        = phi_i_vap * _FAR_ST
    mdot_fuel_i_vap_req = FAR_i_target * air_i_vap
    mdot_fuel_vap_req   = float(np.sum(mdot_fuel_i_vap_req))
    mdot_fuel_vap_base  = f_vap_model * mdot_fuel

    scale_fuel = 0.0 if mdot_fuel_vap_base <= 0.0 else min(
        1.0, mdot_fuel_vap_base / max(mdot_fuel_vap_req, 1e-30)
    )
    mdot_fuel_i_vap = mdot_fuel_i_vap_req * scale_fuel

    mdot_fuel_gas_injected = np.zeros(_N_PZ)
    mdot_fuel_gas_injected[vap_indices]      = mdot_fuel_i_vap
    mdot_fuel_gas_injected[idx_liquid_branch] = mdot_fuel_from_liq

    mdot_pz_nom_i = mdot_air_PZ_i + mdot_fuel_gas_injected

    # ══════════════════════════════════════════════════════════════════════════
    #  STADIO PZ: 9 sub-PSR in parallelo
    # ══════════════════════════════════════════════════════════════════════════
    def _make_branch(i):
        gas_inerte = ct.Solution(_MECH, _PHASE)
        gas_inerte.TPX = _T_ign, p_in, "N2:1.0"
        rPZ = ct.IdealGasReactor(gas_inerte, name=f"PZ_{i}", volume=_V1_i)
        rPZ.energy_enabled   = True
        rPZ.chemistry_enabled = True

        ct.MassFlowController(
            air_tank, rPZ,
            mdot=ct.Func1(lambda t, m=mdot_air_PZ_i[i]: m * scale_in(t))
        )
        ct.MassFlowController(
            fuel_tank, rPZ,
            mdot=ct.Func1(lambda t, m=mdot_fuel_gas_injected[i]: m * scale_in(t))
        )
        res_out = ct.Reservoir(ct.Solution(_MECH, _PHASE))
        res_out.thermo.TPX = T_in, p_in, "O2:0.21, N2:0.79"
        res_out.syncState()

        K_i = (mdot_air_PZ_i[i] + mdot_fuel_gas_injected[i]) / (eps_dp * p_in + 1e-30)
        ct.PressureController(rPZ, res_out, primary=ct.MassFlowController(
            air_tank, rPZ,
            mdot=ct.Func1(lambda t, m=mdot_air_PZ_i[i]: m * scale_in(t))
        ), K=K_i)
        return rPZ, ct.ReactorNet([rPZ])

    # ── costruzione corretta dei branch PZ ───────────────────────────────────
    pz_reactors  = []
    pz_time_hist = []

    for i in range(_N_PZ):
        gas_i = ct.Solution(_MECH, _PHASE)
        gas_i.TPX = _T_ign, p_in, "N2:1.0"
        rPZ_i = ct.IdealGasReactor(gas_i, name=f"PZ_{i}", volume=_V1_i)
        rPZ_i.energy_enabled    = True
        rPZ_i.chemistry_enabled = True

        m_air_i = ct.MassFlowController(
            air_tank, rPZ_i,
            mdot=ct.Func1(lambda t, m=mdot_air_PZ_i[i]: m * scale_in(t))
        )
        ct.MassFlowController(
            fuel_tank, rPZ_i,
            mdot=ct.Func1(lambda t, m=mdot_fuel_gas_injected[i]: m * scale_in(t))
        )
        res_out_i = ct.Reservoir(ct.Solution(_MECH, _PHASE))
        res_out_i.thermo.TPX = T_in, p_in, "O2:0.21, N2:0.79"
        res_out_i.syncState()

        K_i = (mdot_air_PZ_i[i] + mdot_fuel_gas_injected[i]) / (eps_dp * p_in + 1e-30)
        ct.PressureController(rPZ_i, res_out_i, primary=m_air_i, K=K_i)

        sim_i = ct.ReactorNet([rPZ_i])
        t_i, T_i, P_i, _ = _integrate_stage_stepwise(
            sim_i, rPZ_i, t0=0.0,
            tol_T_rel=1e-7, tol_P_rel=1e-7,
            n_consec_ok=80, t_cap=0.8
        )
        pz_reactors.append(rPZ_i)
        pz_time_hist.append((t_i, T_i, P_i))

    # ── mixer PZ → SZ ────────────────────────────────────────────────────────
    def _build_mixed_reservoir(reactors, mdot_branches, p_target):
        gmix = ct.Solution(_MECH, _PHASE)
        w    = np.array(mdot_branches, dtype=float)
        w   /= max(w.sum(), 1e-30)
        Y_mix = np.zeros(gmix.n_species)
        h_mix = 0.0
        for k, rloc in enumerate(reactors):
            gk = ct.Solution(_MECH, _PHASE)
            gk.TPX = rloc.T, rloc.thermo.P, rloc.thermo.X
            Y_mix += w[k] * gk.Y
            h_mix += w[k] * gk.enthalpy_mass
        gmix.HPY = h_mix, p_target, Y_mix
        return gmix

    gas_out_PZ_mixed = _build_mixed_reservoir(pz_reactors, mdot_pz_nom_i, p_in)
    link_PZ_SZ_mix.thermo.TPX = (
        gas_out_PZ_mixed.T,
        gas_out_PZ_mixed.P,
        gas_out_PZ_mixed.X,
    )
    link_PZ_SZ_mix.syncState()

    t1 = pz_time_hist[0][0]   # timeline del primo branch (solo per t0)

    # ══════════════════════════════════════════════════════════════════════════
    #  STADIO SZ
    # ══════════════════════════════════════════════════════════════════════════
    gas_up_SZ = _mix_streams_mass(
        gas_out_PZ_mixed, mdot_pz_nom,
        air_stream, mdot_air_SZa,
        p_in, T_in
    )
    r2 = ct.IdealGasReactor(gas_up_SZ, name="SZ", volume=_V2)
    r2.energy_enabled    = True
    r2.chemistry_enabled = True

    m_SZ_pz = ct.MassFlowController(
        link_PZ_SZ_mix, r2,
        mdot=ct.Func1(lambda t: mdot_pz_nom * scale_in(t))
    )
    ct.MassFlowController(
        air_tank, r2,
        mdot=ct.Func1(lambda t: mdot_air_SZa * scale_in(t))
    )
    ct.PressureController(r2, link_SZ_DZ, primary=m_SZ_pz, K=K_SZ)

    sim2 = ct.ReactorNet([r2])
    t2, T2, P2, _ = _integrate_stage_stepwise(
        sim2, r2, t0=t1[-1],
        tol_T_rel=1e-7, tol_P_rel=1e-7,
        n_consec_ok=60, t_cap=t1[-1] + 0.5
    )

    # ══════════════════════════════════════════════════════════════════════════
    #  STADIO DZ
    # ══════════════════════════════════════════════════════════════════════════
    gas_out_SZ = ct.Solution(_MECH, _PHASE)
    gas_out_SZ.TPX = r2.T, r2.thermo.P, r2.thermo.X

    gas_up_DZ = _mix_streams_mass(
        gas_out_SZ, mdot_sz_nom,
        air_stream, mdot_air_DZa,
        p_in, T_in
    )
    link_SZ_DZ.thermo.TPX = gas_out_SZ.T, gas_out_SZ.P, gas_out_SZ.X
    link_SZ_DZ.syncState()

    r3 = ct.IdealGasReactor(gas_up_DZ, name="DZ", volume=_V3)
    r3.energy_enabled    = True
    r3.chemistry_enabled = True

    m_DZ_core = ct.MassFlowController(
        link_SZ_DZ, r3,
        mdot=ct.Func1(lambda t: mdot_sz_nom * scale_in(t))
    )
    ct.MassFlowController(
        air_tank, r3,
        mdot=ct.Func1(lambda t: mdot_air_DZa * scale_in(t))
    )
    ct.PressureController(r3, exhaust, primary=m_DZ_core, K=K_DZ)

    sim3 = ct.ReactorNet([r3])
    t3, T3, P3, _ = _integrate_stage_stepwise(
        sim3, r3, t0=t2[-1],
        tol_T_rel=1e-7, tol_P_rel=1e-7,
        n_consec_ok=60, t_cap=t2[-1] + 0.5
    )

    if verbose:
        print(f"[CRN] T_end: PZ(medio)={T2[0]:.0f} K  SZ={T2[-1]:.0f} K  DZ={T3[-1]:.0f} K")

    # ══════════════════════════════════════════════════════════════════════════
    #  CALCOLO EI_NOx e EI_CO
    # ══════════════════════════════════════════════════════════════════════════
    gas_out = ct.Solution(_MECH, _PHASE)
    gas_out.TPX = r3.T, r3.thermo.P, r3.thermo.X
    Y_out = gas_out.Y
    smap  = {s: i for i, s in enumerate(gas_out.species_names)}

    Y_NO  = Y_out[smap["NO"]]  if "NO"  in smap else 0.0
    Y_NO2 = Y_out[smap["NO2"]] if "NO2" in smap else 0.0
    Y_CO  = Y_out[smap["CO"]]  if "CO"  in smap else 0.0

    EI_NOx = _EI_from_mass_fraction(Y_NO + Y_NO2, FAR)
    EI_CO  = _EI_from_mass_fraction(Y_CO, FAR)

    if verbose:
        print(f"[RESULT] EI_NOx = {EI_NOx:.3f} g/kg_fuel  |  EI_CO = {EI_CO:.3f} g/kg_fuel")

    return EI_NOx, EI_CO


# ─────────────────────────────────────────────────────────────────────────────
# Esempio d'uso: riproduce i 4 anchor ICAO del CFM56-7B27E
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":

    ANCHOR_POINTS = {
        "ID (Idle)":     dict(T_in=477.0, p_in_bar=3.78,  mdot_air=8.32,  FAR=0.014, dPqP=0.9476, chi_mixer_scale=1.50),
        "AP (Approach)": dict(T_in=619.0, p_in_bar=10.75, mdot_air=21.33, FAR=0.016, dPqP=0.9447, chi_mixer_scale=1.271698),
        "CL (Climb)":    dict(T_in=759.0, p_in_bar=24.80, mdot_air=42.80, FAR=0.024, dPqP=0.9486, chi_mixer_scale=1.071202),
        "TO (Take-Off)": dict(T_in=795.0, p_in_bar=28.80, mdot_air=47.47, FAR=0.026, dPqP=0.9499, chi_mixer_scale=1.0),
    }

    print(f"\n{'Mode':<16} {'EI_NOx [g/kg]':>16} {'EI_CO [g/kg]':>14}")
    print("-" * 50)
    for name, kwargs in ANCHOR_POINTS.items():
        ei_nox, ei_co = compute_emissions(**kwargs, verbose=False)
        print(f"{name:<16} {ei_nox:>16.3f} {ei_co:>14.3f}")
