import sys
sys.path.insert(0,'../')
import PhlyGreen.Utilities.Units as Units
# ALL THE INPUT SHOULD BE GIVEN USING IMPERIAL UNITS..... PLEASE BE FREE TO USE THE UNIT CONVERTER

FLOPS_input = {

    'WING': 
        {'N_ENGINES': 2., 
         'STRUT_BRACING_FACTOR':0., 
         'SPAN':Units.mToft(24.5), 
         'TAPER_RATIO': 0.54,  
         'THICKNESS_TO_CHORD': 0.15, 
         'AEROELASTIC_TAILORING_FACTOR': 0., 
         'SWEEP': 0,
         'COMPOSITE_FRACTION': 0.2, 
         'ULTIMATE_LOAD_FACTOR': 3.75, 
         'VAR_SWEEP_MASS_PENALTY': 0., 
         'LOAD_FRACTION': 1.0,
         'SCALER': 1.23
        },

    'VERTICAL_TAIL':
        {'AREA': Units.m2toft2(12.7),
         'TAPER_RATIO': 0.33,
         'N_VERTICAL_TAILS': 1., 
         'SCALER': 1.0
        },

    'HORIZONTAL_TAIL': 
        {'AREA': Units.m2toft2(11.5),
         'TAPER_RATIO': 0.54,
         'SCALER': 1.2                        
        },

    'FUSELAGE': 
        {'LENGTH': Units.mToft(22.7), 
         'MAX_HEIGHT': Units.mToft(2.7), 
         'MAX_WIDTH': Units.mToft(2.7),
         'NUM_FUSELAGES': 1.,
         'TOTAL_NUM_FUSELAGE_ENGINES': 0.,
         'MILITARY_CARGO_FLOOR': False,
         'SCALER': 1.05 
        },

    'LANDING_GEAR': 
        {'MAIN_GEAR_LENGTH': 102.,
         'NOSE_GEAR_LENGTH': 67,
         'MAIN_SCALER': 1.1,
         'NOSE_SCALER': 1.0 
        },


    'NACELLE': 
        {'AVG_DIAM': Units.mToft(0.8),
         'AVG_LENGTH': Units.mToft(2.1),
         'SCALER': 1.0
        },


    'SYSTEM_EQUIPMENT': 
        {'PLANFORM_AREA': Units.mToft(22.7)*Units.mToft(2.7), 
         'N_PAX': 48, 
         'N_CREW': 3, 
         'N_FIRST_CLASS': 6, 
         'N_BUSINESS_CLASS': 0., 
         'N_TOURIST_CLASS': 42, 
         'PASSENGER_COMPARTMENT_LENGTH': Units.mToft(22.7)*0.7, 
         'SYSTEM_PRESSURE': 3000, 
         'CONTROL_SURFACE_AREA_RATIO': 0.1, 
         'ANTIICING_SCALER': 1., 
         'APU_SCALER':1.1, 
         'AVIONICS_SCALER': 1.2, 
         'AC_SCALER': 1.0,
         'ELECTRICAL_SCALER': 1.25, 
         'FURNISHING_SCALER': 1.1, 
         'HYDRAULICS_SCALER': 1.0, 
         'SURFACE_CONTROLS_SCALER': 1.0
        },


    'PAINT': 
        {'MASS_PER_AREA': 0.037
        },
        
    
    'ENGINE':
        {'N_ENGINES': 2.,
         'MAX_SLS_THRUST': 26000,
         'MAX_SLS_POWER': 2500, #hp
         'N_WING_ENGINES': 2,
         'N_FUSELAGE_ENGINES': 0
        },

    'PROPELLER':
        {'N_BLADES': 6.,
         'DIAMETER': 13, # feet
         'SCALER': 1.}
}