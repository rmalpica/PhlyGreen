"""
Python file to hold the parameters of the different cells.
The cell models define the different parameters of their Shepherd/Tremblay
discharge curve. The program uses the thermal corrected model,
described in https://doi.org/10.1109%2FTIE.2016.2618363 
The parameters for the battery need to be derived in accordance
to the procedure of the paper, in the same units listed by them.
This means using Wh for energy and Ah for charge.
The other parameters of the battery are obtained from the datasheet
in SI units.
When performing a parametric sweep of hypothetical batteries of
much greater energy and power densities than possible with
current tech, there is obviously no way to know what their discharge
curves will look like, and the best that can be done is scale the
parameters of a known battery to fit the requirements of the
new one.
Usually batteries come with a C rating that gives the peak continuous
current draw allowed as a multiple of the capacity. To make the code
simpler, and to make it easier to do arbitrary sweeps, here I use
a current limit in Amperes instead. Make sure that when setting up
a new battery model the current limit actually makes physical sense.
The code assumes that the peak delivered power happens at the
current limit. If the internal resistance is too high for the 
current, it all gets dissipated as heat and most of the power
is actually lost.
Nonsensical inputs will give nonsensical results:
Garbage in -> Garbage out.
To make sure all the values make sense when adjusting the power density
of a battery model, multiply the base values by a constant rather than
changing them one by one. Say, the current capacity should be double.
Multiply the current limit by two and divide the resistive terms by two as well.
The nominal voltage should be the "average voltage" that when multiplied by the
cell charge gives the rough energy capacity estimate of the cell. This is only
used for the purposes of displaying an energy density to the user without having
to integrate the battery discharge for a display value.
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
        'Cell Current Max': 4*42.82,            # dimensionless
        'Cell Voltage Nominal': 13,             # in V
        'Cell Mass': 0.071*120,                 # in kg *
        'Cell Radius': 0.02155/2,               # in m  *
        'Cell Height': 0.07015,                 # in m  *
    },
        'Finger-Cell-Thermal':{
        'Reference Temperature': 275.15+23,     # in kelvin
        'Exp Amplitude': 0.3,                   # in volts
        'Exp Time constant': 1.5213,            # in Ah^-1 
        'Internal Resistance': 0.015,           # in ohms
        'Resistance Arrhenius Constant': 2836,  # dimensionless
        'Polarization Constant': 0.03,          # in Volts over amp hour
        'Polarization Arrhenius Constant': 1225,# dimensionless
        'Cell Capacity': 6,                    # in Ah
        'Capacity Thermal Slope': 0.1766,       # in UNCLEAR per kelvin
        'Voltage Constant':4.2-0.3,             # in volts
        'Voltage Thermal Slope': 0.00004918,    # in volts per kelvin
        'Cell Voltage Min': 2.5,                # in volts
        'Cell Current Max': 12,               # dimensionless
        'Cell Voltage Nominal': 3.7,            # in V
        'Cell Mass': 0.071,                     # in kg
        'Cell Radius': 0.02155/2,               # in m
        'Cell Height': 0.07015,                 # in m
    },
}
