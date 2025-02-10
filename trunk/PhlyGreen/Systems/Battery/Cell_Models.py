"""
Python file to hold the parameters of the different cells.
"""

Cell_Models = {
    'ThermalModel-Cell':{ 
        # the reference 120 cell pack used in https://doi.org/10.1109%2FTIE.2016.2618363
        # values with * are not in the original paper,
        # and were taken from the Molicel INR-21700-P50B datasheet
        'Reference Temperature': 275.15+23,     # in kelvin
        'Exp Amplitude': 0.7,                   # in volts
        'Exp Time constant': 1.5213,            # in Ah^-1 
        'Internal Resistance': 0.0126,          # in ohms
        'Resistance Arrhenius Constant': 2836,  # dimensionless
        'Polarization Constant': 0.0033,        # in Volts over amp hour
        'Polarization Arrhenius Constant': 1225,# dimensionless
        'Cell Capacity': 42.82,                 # in Ah
        'Capacity Thermal Slope': 0.1766,       # in UNCLEAR per kelvin
        'Voltage Constant':13.338,              # in volts
        'Voltage Thermal Slope': 0.00004918,    # in volts per kelvin
        'Cell Voltage Min': 2.5,                # in volts
        'Cell C rating': 4,                     # dimensionless
        'Cell Nominal Energy': 42.82*12,        # in Wh, for display purposes
        'Cell Mass': 0.071*120,                 # in kg *
        'Cell Radius': 0.02155/2,               # in m  *
        'Cell Height': 0.07015,                 # in m  *
    },
        'ThermalModel-Cell-Super':{
        'Reference Temperature': 275.15+23,     # in kelvin
        'Exp Amplitude': 0.3,                   # in volts
        'Exp Time constant': 2.5213,            # in Ah^-1 
        'Internal Resistance': 0.015,           # in ohms
        'Resistance Arrhenius Constant': 2836,  # dimensionless
        'Polarization Constant': 0.03,        # in Volts over amp hour
        'Polarization Arrhenius Constant': 1225,# dimensionless
        'Cell Capacity': 10,                     # in Ah
        'Capacity Thermal Slope': 0.1766,       # in UNCLEAR per kelvin
        'Voltage Constant':4.2-0.3,             # in volts
        'Voltage Thermal Slope': 0.00004918,    # in volts per kelvin
        'Cell Voltage Min': 2.5,                # in volts
        'Cell C rating': 4,                    # dimensionless
        'Cell Nominal Energy': 10*3.7,        # in Wh, for display purposes
        'Cell Mass': 0.071,                     # in kg
        'Cell Radius': 0.02155/2,               # in m
        'Cell Height': 0.07015,                 # in m
    },
    'ThermalModel-Cell-Mega':{
        'Reference Temperature': 275.15+23,     # in kelvin
        'Exp Amplitude': 0.3,                   # in volts
        'Exp Time constant': 2.5213,            # in Ah^-1 
        'Internal Resistance': 0.015,           # in ohms
        'Resistance Arrhenius Constant': 2836,  # dimensionless
        'Polarization Constant': 0.03,        # in Volts over amp hour
        'Polarization Arrhenius Constant': 1225,# dimensionless
        'Cell Capacity': 25,                     # in Ah
        'Capacity Thermal Slope': 0.1766,       # in UNCLEAR per kelvin
        'Voltage Constant':4.2-0.3,             # in volts
        'Voltage Thermal Slope': 0.00004918,    # in volts per kelvin
        'Cell Voltage Min': 2.5,                # in volts
        'Cell C rating': 4,                    # dimensionless
        'Cell Nominal Energy': 25*3.7,        # in Wh, for display purposes
        'Cell Mass': 0.071,                     # in kg
        'Cell Radius': 0.02155/2,               # in m
        'Cell Height': 0.07015,                 # in m
    },
        'ThermalModel-Cell-Ultra':{
        'Reference Temperature': 275.15+23,     # in kelvin
        'Exp Amplitude': 0.3,                   # in volts
        'Exp Time constant': 2.5213,            # in Ah^-1 
        'Internal Resistance': 0.015,           # in ohms
        'Resistance Arrhenius Constant': 2836,  # dimensionless
        'Polarization Constant': 0.03,        # in Volts over amp hour
        'Polarization Arrhenius Constant': 1225,# dimensionless
        'Cell Capacity': 55,                     # in Ah
        'Capacity Thermal Slope': 0.1766,       # in UNCLEAR per kelvin
        'Voltage Constant':4.2-0.3,             # in volts
        'Voltage Thermal Slope': 0.00004918,    # in volts per kelvin
        'Cell Voltage Min': 2.5,                # in volts
        'Cell C rating': 4,                    # dimensionless
        'Cell Nominal Energy': 55*3.7,        # in Wh, for display purposes
        'Cell Mass': 0.071,                     # in kg
        'Cell Radius': 0.02155/2,               # in m
        'Cell Height': 0.07015,                 # in m
    },
        'Finger-Cell-Thermal':{
        'Reference Temperature': 275.15+23,     # in kelvin
        'Exp Amplitude': 0.3,                   # in volts
        'Exp Time constant': 2.5213,            # in Ah^-1 
        'Internal Resistance': 0.015,           # in ohms
        'Resistance Arrhenius Constant': 2836,  # dimensionless
        'Polarization Constant': 0.03,          # in Volts over amp hour
        'Polarization Arrhenius Constant': 1225,# dimensionless
        'Cell Capacity': 29,                    # in Ah
        'Capacity Thermal Slope': 0.1766,       # in UNCLEAR per kelvin
        'Voltage Constant':4.2-0.3,             # in volts
        'Voltage Thermal Slope': 0.00004918,    # in volts per kelvin
        'Cell Voltage Min': 2.5,                # in volts
        'Cell C rating': 4,                     # dimensionless
        'Cell Nominal Energy': 29*3.7,        # in Wh, for display purposes
        'Cell Mass': 0.071,                     # in kg
        'Cell Radius': 0.02155/2,               # in m
        'Cell Height': 0.07015,                 # in m
    },
}
