"""
Tank_Models.py
Database dei parametri per i Serbatoi di Idrogeno Liquido (LH2).
Dati estratti dal paper: "Modelling Hydrogen Fuel Cell Aircraft in SUAVE" (Svensson et al.)
"""

TANK_Database = {
    'Cryogenic_Tank': {
        # --- Limiti Operativi ---
        'max_p_bar': 1.6,           # [bar] Pressione massima (Vent)
        'min_p_bar': 1.2,           # [bar] Pressione minima operativa
        
        # --- Parametri Materiale (Al 5083-O) ---
        'sigma_y': 228e6,           # [Pa] Snervamento 
        'rho_al': 2660.0,           # [kg/m^3] Densità
        'E_al': 71e9,               # [Pa] Modulo di Young
        'nu_al': 0.33,              # [-] Poisson ratio
        
        # --- Fattori di Sicurezza & Calibrazione ---
        'sf_inner': 2.0,            # [-] SF Burst Pressure
        'sf_outer': 2.5,            # [-] SF Buckling
        'ew': 0.80,                 # [-] Efficienza saldatura
        'buckling_knockdown': 0.36, # [-] Imperfezione geometrica 
        'accessory_mass_factor': 1.35, # [-] 15% massa aggiuntiva 
        
        # --- Isolamento (Tabella 4 - Configurazione VD-MLI) ---
        'n_layers_mli': 9,          # [-] Strati MLI
        't_foam': 0.0,              # [m] Niente schiuma per la fase di volo
        'rho_foam': 35.0,           # [kg/m^3] Densità schiuma
        'insulation_gap': 0.03,     # [m] Gap per isolamento totale 
        
        # --- Termico: Modified Lockheed Equation (Tabella 4) ---
        'C1': 4.43e-11,             # Conduzione solida
        'C2': 3.91,                 # Esponente densità strati
        'C3': 8.03e-10,             # Irraggiamento
        'Cg': 1.46e4,               # Conduzione gas
        'ng': 0.53,                 # Esponente T gas
        'p_mli': 1.0e-3,            # [Torr] MODIFICATO: Dedotto per ingegneria inversa. "1 mBar" nel paper è un refuso per "1 microBar"!
        'Nt': 20,                   # [layers/cm] Densità strati (Low density)
        'eps': 0.03                 # [-] Emissività
    }
}

# Alias: the Svensson et al. configuration is the default cryogenic tank model.
TANK_Database['Svensson_Default'] = TANK_Database['Cryogenic_Tank']