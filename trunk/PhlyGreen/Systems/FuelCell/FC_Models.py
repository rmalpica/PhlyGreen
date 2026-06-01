"""
FC_Models.py
Database dei parametri per le Fuel Cells.
Include il modello validato da Massaro et al. basato sulle equazioni di Kulikovsky,
con l'aggiunta dei parametri empirici calibrati per fittare il flooding ad alti carichi.
"""

FC_Database = {
    'PEMFC_GoodPerformance': {
        # --- Design Point & Generali ---
        'V_design': 0.7,                # [V] Voltaggio nominale di dimensionamento
        'T_op': 353.15,                 # [K] Temperatura operativa
        'Target_Press': 150000.0,       # [Pa] Pressione operativa catodica
        'Stack_Power_Density': 1600.0,  # [W/kg] System power density target (es. 2030)
        'BoP_Mass_Ratio': 1.0,          # [-] Peso Balance of Plant / Peso Stack
        
        # --- Parametri Modello Kulikovsky (Massaro et al. Tabella 7) + Fitting ---
        'Voc': 1.145,                   # [V] Open circuit voltage
        'b_tafel': 0.030,               # [V] Tafel slope
        'R_ohm': 0.0801,                # [Ohm*cm^2] Area specific resistance (Ro)
        'i_star': 2.00e-3,              # [A/cm^3] Volumetric exchange current density
        
        # Correzioni empiriche modificate per fittare la Figura 2 (V ~ 0.2 @ j=1.6)
        'j_lim': 1.65,                  # [A/cm^2] Asintoto spostato a 1.65 per non azzerare V prima di 1.6
        'B_conc': 0.075,                # [V] Ridotto per addolcire il "ginocchio" della curva
        
        # --- Proprietà Fisiche e Geometriche ---
        'c_h_ref': 7.36e-6,             # [mol/cm^3] Oxygen conc. in channel at p=1 bar
        'c_ref': 8.58e-6,               # [mol/cm^3] Reference oxygen conc.
        'sigma_t': 0.03,                # [S/cm] Proton conductivity in CCL
        'l_t': 0.0007,                  # [cm] CCL thickness
        'D_b': 0.0259,                  # [cm^2/s] Effective diffusion coeff GDL
        'l_b': 0.0312,                  # [cm] GDL thickness
        'D_ccl': 1.00e-4,               # [cm^2/s] CCL effective diffusion coeff
    },
    
    'PEMFC_HighPerformance': {
        # --- Design Point & Generali ---
        'V_design': 0.7,                # [V] Voltaggio nominale di dimensionamento
        'T_op': 443.15,                 # [K] Temperatura operativa
        'Target_Press': 150000.0,       # [Pa] Pressione operativa catodica
        'Stack_Power_Density': 1600.0,  # [W/kg] 
        'BoP_Mass_Ratio': 0.40,         # [-] Peso Balance of Plant / Peso Stack
        
        # --- Parametri Modello Kulikovsky (Massaro et al. Tabella 10) ---
        'Voc': 1.145,                   # [V] Open circuit voltage
        'b_tafel': 0.030,               # [V] Tafel slope
        'R_ohm': 0.0978,                # [Ohm*cm^2] Area specific resistance 
        'i_star': 1.75e-2,              # [A/cm^3] Volumetric exchange current density 
        
        # Le celle High Performance reggono benissimo correnti elevate senza flooding (vedi Fig 7).
        'j_lim': 3.0,                   # [A/cm^2] Limite empirico per trasporto di massa molto più ampio
        'B_conc': 0.05,                 # [V] Ginocchio molto più dolce
        
        # --- Proprietà Fisiche e Geometriche ---
        'c_h_ref': 7.36e-6,             # [mol/cm^3]
        'c_ref': 8.583e-6,              # [mol/cm^3]
        'sigma_t': 0.03,                # [S/cm] 
        'l_t': 0.0007,                  # [cm] 
        'D_b': 0.0259,                  # [cm^2/s] 
        'l_b': 0.0188,                  # [cm] GDL assottigliato per massimizzare la diffusione
        'D_ccl': 1.40e-4,               # [cm^2/s] CCL effective diffusion coeff migliorato
    },
    
    'PEM_Generic': {
        # --- Design Point & Generali ---
        'V_design': 0.7,
        'T_op': 353.15,
        'Target_Press': 150000.0,
        'Stack_Power_Density': 1500.0, 
        'BoP_Mass_Ratio': 0.20,
        
        # --- Parametri Modello Kulikovsky ---
        'Voc': 1.145, 
        'R_ohm': 0.15, 
        'b_tafel': 0.04, 
        'i_star': 0.005, 
        'j_lim': 2.5, 
        'B_conc': 0.1,
        
        # --- Proprietà Fisiche (Valori standard di completamento) ---
        'c_h_ref': 7.36e-6,
        'c_ref': 8.58e-6,
        'sigma_t': 0.03,
        'l_t': 0.0007,
        'D_b': 0.0259,
        'l_b': 0.0312,
        'D_ccl': 1.00e-4,
    }
}