Cell_Models = { 
            'SAMSUNG_LIR18650':{
                        'Cell Capacity': 2.5,        #in Ah
                        'Cell C rating': 8,          #dimensionless
                        'Cell Voltage Min': 2.5,     #in volts
                        'Cell Voltage Max': 4.2,     #in volts
                        'Cell Voltage Nominal': 3.6, #in volts
                        'Cell Mass': 0.0438,           #in kg
                        'Cell Volume': 0.0000003,         #in m^3
            },
            'LG_INR21700M50LT':{
                        'Cell Capacity': 4.8,        #in Ah
                        'Cell C rating': 3,          #dimensionless
                        'Cell Voltage Min': 2.5,     #in volts
                        'Cell Voltage Max': 4.2,     #in volts
                        'Cell Voltage Nominal': 3.6, #in volts
                        'Cell Mass': 0.0682,           #in kg
                        'Cell Volume': 0.0000003,         #in m^3
            },
}

#things to consider:
#   make volume vs dimensions
#   energy in Wh vs volts*Ah
#   current in C rating vs Amps
#   figure out how to get a more detailed model in that isnt just these parameters?
