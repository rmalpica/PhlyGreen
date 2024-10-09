def MissionParameters(argRange,argPayload,argProfile,argCell,argPhi,argMission):
    Profiles= {

        "Mission-FelixFinger" : {
            "ConstraintsInput" : {'DISA': 0.,
                                'Cruise': {'Speed': 0.34, 'Speed Type':'Mach', 'Beta': 0.95, 'Altitude': 3000.},
                                'AEO Climb': {'Speed': 130, 'Speed Type':'KCAS', 'Beta': 0.97, 'Altitude': 2000., 'ROC': 8},
                                'OEI Climb': {'Speed': 1.2*34.5, 'Speed Type': 'TAS', 'Beta': 1., 'Altitude': 0., 'Climb Gradient': 0.021},
                                'Take Off': {'Speed': 90, 'Speed Type': 'TAS', 'Beta': 1., 'Altitude': 100., 'kTO': 1.2, 'sTO': 950},
                                'Landing':{'Speed': 59., 'Speed Type': 'TAS', 'Altitude': 500.},
                                'Turn':{'Speed': 130, 'Speed Type': 'KCAS', 'Beta': 0.9, 'Altitude': 3000, 'Load Factor': 1.1},
                                'Ceiling':{'Speed': 0.5, 'Beta': 0.8, 'Altitude': 3500, 'HT': 0.5},
                                'Acceleration':{'Mach 1': 0.3, 'Mach 2':0.4, 'DT': 180, 'Altitude': 2800, 'Beta': 0.9}},

            "MissionInput" : {'Range Mission': argRange/1.852,  #nautical miles but the input comes in km #TODO
                            'Range Diversion': 145,  #nautical miles
                            'Beta start': 0.97,
                            'Minimum SOC': 0.2,
                            'Payload Weight': argPayload-500 ,  #Kg #TODO
                            'Crew Weight': 500} , #Kg,

            "MissionStages" : {
                            'Takeoff':
                                {'Supplied Power Ratio':{'phi': argPhi}},

                            'Climb1': {'type': 'ConstantRateClimb', 'input': 
                                {'CB': 0.16, 'Speed': 77, 'StartAltitude': 100, 'EndAltitude': 560}, 
                                'Supplied Power Ratio':{'phi_start': argPhi, 'phi_end':argPhi }},

                            'Climb2': {'type': 'ConstantRateClimb', 'input': 
                                {'CB': 0.08, 'Speed': 120, 'StartAltitude': 560, 'EndAltitude': 1690}, 
                                'Supplied Power Ratio':{'phi_start': argPhi, 'phi_end':argPhi }},

                            'Climb3': {'type': 'ConstantRateClimb', 'input': 
                                {'CB': 0.07, 'Speed': 125, 'StartAltitude': 1690, 'EndAltitude': 3000}, 
                                'Supplied Power Ratio':{'phi_start': argPhi, 'phi_end': argPhi }},

                            'Cruise': {'type': 'ConstantMachCruise', 'input': 
                                { 'Mach': 0.4, 'Altitude': 3000}, 
                            'Supplied Power Ratio':{'phi_start': argPhi, 'phi_end':argPhi }},

                            'Descent1': {'type': 'ConstantRateDescent', 'input':
                                {'CB': -0.04, 'Speed': 90, 'StartAltitude': 3000, 'EndAltitude': 200}, 
                                'Supplied Power Ratio':{'phi_start': argPhi, 'phi_end': argPhi  }}},


            "DiversionStages" : {
                            'Climb1': {'type': 'ConstantRateClimb', 'input': 
                                    {'CB': 0.08, 'Speed': 110, 'StartAltitude': 200, 'EndAltitude': 1000}, 
                                    'Supplied Power Ratio':{'phi_start': argPhi, 'phi_end':argPhi  }},

                            'Cruise': {'type': 'ConstantMachCruise', 'input':
                                    { 'Mach': 0.35, 'Altitude': 1000}, 
                                    'Supplied Power Ratio':{'phi_start': argPhi, 'phi_end':argPhi }},

                            'Descent1': {'type': 'ConstantRateDescent', 'input':
                                    {'CB': -0.04, 'Speed': 90, 'StartAltitude': 1000, 'EndAltitude': 200}, 
                                    'Supplied Power Ratio':{'phi_start': argPhi, 'phi_end':argPhi}}},

            "EnergyInput" : {'Ef': 43.5*10**6,
                            'Contingency Fuel': 130,
                            'Eta Gas Turbine': 0.22,
                            'Eta Gearbox': 0.96,
                            'Eta Propulsive': 0.9,
                            'Eta Electric Motor 1': 0.96,    #for serial config
                            'Eta Electric Motor 2': 0.96,    #for serial config
                            'Eta Electric Motor': 0.98,      #for parallel config
                            'Eta PMAD': 0.99,
                            'Specific Power Powertrain': [3900,7700],
                            'Specific Power PMAD': [2200,2200,2200],
                            'PowertoWeight Battery': 35, 
                            'PowertoWeight Powertrain': [150,33],
                            'PowertoWeight PMAD': 0
                            },
                            
            "AerodynamicsInput" : {'AnalyticPolar': {'type': 'Quadratic', 'input': {'AR': 11, 'e_osw': 0.8}},
                                'Take Off Cl': 1.9,
                                'Landing Cl': 1.9,
                                'Minimum Cl': 0.20,
                                'Cd0': 0.017}
            },

            #####################################################################
        "HybridCruiseOnly" : {
            "ConstraintsInput" : {'DISA': 0.,
                                'Cruise': {'Speed': 0.34, 'Speed Type':'Mach', 'Beta': 0.95, 'Altitude': 3000.},
                                'AEO Climb': {'Speed': 130, 'Speed Type':'KCAS', 'Beta': 0.97, 'Altitude': 2000., 'ROC': 8},
                                'OEI Climb': {'Speed': 1.2*34.5, 'Speed Type': 'TAS', 'Beta': 1., 'Altitude': 0., 'Climb Gradient': 0.021},
                                'Take Off': {'Speed': 90, 'Speed Type': 'TAS', 'Beta': 1., 'Altitude': 100., 'kTO': 1.2, 'sTO': 950},
                                'Landing':{'Speed': 59., 'Speed Type': 'TAS', 'Altitude': 500.},
                                'Turn':{'Speed': 130, 'Speed Type': 'KCAS', 'Beta': 0.9, 'Altitude': 3000, 'Load Factor': 1.1},
                                'Ceiling':{'Speed': 0.5, 'Beta': 0.8, 'Altitude': 3500, 'HT': 0.5},
                                'Acceleration':{'Mach 1': 0.3, 'Mach 2':0.4, 'DT': 180, 'Altitude': 2800, 'Beta': 0.9}},

            "MissionInput" : {'Range Mission': argRange/1.852,  #nautical miles but the input comes in km #TODO
                            'Range Diversion': 145,  #nautical miles
                            'Beta start': 0.97,
                            'Minimum SOC': 0.2,
                            'Payload Weight': argPayload-500 ,  #Kg
                            'Crew Weight': 500} , #Kg,

            "MissionStages" : {
                            'Takeoff':
                                {'Supplied Power Ratio':{'phi': 0}},

                            'Climb1': {'type': 'ConstantRateClimb', 'input': 
                                {'CB': 0.16, 'Speed': 77, 'StartAltitude': 100, 'EndAltitude': 560}, 
                                'Supplied Power Ratio':{'phi_start': 0, 'phi_end':0 }},

                            'Climb2': {'type': 'ConstantRateClimb', 'input': 
                                {'CB': 0.08, 'Speed': 120, 'StartAltitude': 560, 'EndAltitude': 1690}, 
                                'Supplied Power Ratio':{'phi_start': 0, 'phi_end':0 }},

                            'Climb3': {'type': 'ConstantRateClimb', 'input': 
                                {'CB': 0.07, 'Speed': 125, 'StartAltitude': 1690, 'EndAltitude': 3000}, 
                                'Supplied Power Ratio':{'phi_start': 0, 'phi_end': 0 }},

                            'Cruise': {'type': 'ConstantMachCruise', 'input': 
                                { 'Mach': 0.4, 'Altitude': 3000}, 
                            'Supplied Power Ratio':{'phi_start': argPhi, 'phi_end':argPhi }},

                            'Descent1': {'type': 'ConstantRateDescent', 'input':
                                {'CB': -0.04, 'Speed': 90, 'StartAltitude': 3000, 'EndAltitude': 200}, 
                                'Supplied Power Ratio':{'phi_start': argPhi, 'phi_end': argPhi  }}},


            "DiversionStages" : {
                            'Climb1': {'type': 'ConstantRateClimb', 'input': 
                                    {'CB': 0.08, 'Speed': 110, 'StartAltitude': 200, 'EndAltitude': 1000}, 
                                    'Supplied Power Ratio':{'phi_start': 0, 'phi_end':0  }},

                            'Cruise': {'type': 'ConstantMachCruise', 'input':
                                    { 'Mach': 0.35, 'Altitude': 1000}, 
                                    'Supplied Power Ratio':{'phi_start': argPhi, 'phi_end':argPhi }},

                            'Descent1': {'type': 'ConstantRateDescent', 'input':
                                    {'CB': -0.04, 'Speed': 90, 'StartAltitude': 1000, 'EndAltitude': 200}, 
                                    'Supplied Power Ratio':{'phi_start': argPhi, 'phi_end':argPhi}}},

            "EnergyInput" : {'Ef': 43.5*10**6,
                            'Contingency Fuel': 130,
                            'Eta Gas Turbine': 0.22,
                            'Eta Gearbox': 0.96,
                            'Eta Propulsive': 0.9,
                            'Eta Electric Motor 1': 0.96,    #for serial config
                            'Eta Electric Motor 2': 0.96,    #for serial config
                            'Eta Electric Motor': 0.98,      #for parallel config
                            'Eta PMAD': 0.99,
                            'Specific Power Powertrain': [3900,7700],
                            'Specific Power PMAD': [2200,2200,2200],
                            'PowertoWeight Battery': 35, 
                            'PowertoWeight Powertrain': [150,33],
                            'PowertoWeight PMAD': 0
                            },

            "AerodynamicsInput" : {'AnalyticPolar': {'type': 'Quadratic', 'input': {'AR': 11, 'e_osw': 0.8}},
                                'Take Off Cl': 1.9,
                                'Landing Cl': 1.9,
                                'Minimum Cl': 0.20,
                                'Cd0': 0.017}
            },
            #####################################################################
        "HybridTOClimbOnly" : {
            "ConstraintsInput" : {'DISA': 0.,
                                'Cruise': {'Speed': 0.34, 'Speed Type':'Mach', 'Beta': 0.95, 'Altitude': 3000.},
                                'AEO Climb': {'Speed': 130, 'Speed Type':'KCAS', 'Beta': 0.97, 'Altitude': 2000., 'ROC': 8},
                                'OEI Climb': {'Speed': 1.2*34.5, 'Speed Type': 'TAS', 'Beta': 1., 'Altitude': 0., 'Climb Gradient': 0.021},
                                'Take Off': {'Speed': 90, 'Speed Type': 'TAS', 'Beta': 1., 'Altitude': 100., 'kTO': 1.2, 'sTO': 950},
                                'Landing':{'Speed': 59., 'Speed Type': 'TAS', 'Altitude': 500.},
                                'Turn':{'Speed': 130, 'Speed Type': 'KCAS', 'Beta': 0.9, 'Altitude': 3000, 'Load Factor': 1.1},
                                'Ceiling':{'Speed': 0.5, 'Beta': 0.8, 'Altitude': 3500, 'HT': 0.5},
                                'Acceleration':{'Mach 1': 0.3, 'Mach 2':0.4, 'DT': 180, 'Altitude': 2800, 'Beta': 0.9}},

            "MissionInput" : {'Range Mission': argRange/1.852,  #nautical miles but the input comes in km #TODO
                            'Range Diversion': 145,  #nautical miles
                            'Beta start': 0.97,
                            'Minimum SOC': 0.2,
                            'Payload Weight': argPayload-500 ,  #Kg
                            'Crew Weight': 500} , #Kg,

            "MissionStages" : {
                            'Takeoff':
                                {'Supplied Power Ratio':{'phi': argPhi}},

                            'Climb1': {'type': 'ConstantRateClimb', 'input': 
                                {'CB': 0.16, 'Speed': 77, 'StartAltitude': 100, 'EndAltitude': 560}, 
                                'Supplied Power Ratio':{'phi_start': argPhi, 'phi_end':argPhi }},

                            'Climb2': {'type': 'ConstantRateClimb', 'input': 
                                {'CB': 0.08, 'Speed': 120, 'StartAltitude': 560, 'EndAltitude': 1690}, 
                                'Supplied Power Ratio':{'phi_start': argPhi, 'phi_end':argPhi }},

                            'Climb3': {'type': 'ConstantRateClimb', 'input': 
                                {'CB': 0.07, 'Speed': 125, 'StartAltitude': 1690, 'EndAltitude': 3000}, 
                                'Supplied Power Ratio':{'phi_start': argPhi, 'phi_end': argPhi }},

                            'Cruise': {'type': 'ConstantMachCruise', 'input': 
                                { 'Mach': 0.4, 'Altitude': 3000}, 
                            'Supplied Power Ratio':{'phi_start': 0, 'phi_end':0 }},

                            'Descent1': {'type': 'ConstantRateDescent', 'input':
                                {'CB': -0.04, 'Speed': 90, 'StartAltitude': 3000, 'EndAltitude': 200}, 
                                'Supplied Power Ratio':{'phi_start': 0, 'phi_end': 0  }}},


            "DiversionStages" : {
                            'Climb1': {'type': 'ConstantRateClimb', 'input': 
                                    {'CB': 0.08, 'Speed': 110, 'StartAltitude': 200, 'EndAltitude': 1000}, 
                                    'Supplied Power Ratio':{'phi_start': 0, 'phi_end':0  }},

                            'Cruise': {'type': 'ConstantMachCruise', 'input':
                                    { 'Mach': 0.35, 'Altitude': 1000}, 
                                    'Supplied Power Ratio':{'phi_start': 0, 'phi_end':0 }},

                            'Descent1': {'type': 'ConstantRateDescent', 'input':
                                    {'CB': -0.04, 'Speed': 90, 'StartAltitude': 1000, 'EndAltitude': 200}, 
                                    'Supplied Power Ratio':{'phi_start': 0, 'phi_end':0}}},

            "EnergyInput" : {'Ef': 43.5*10**6,
                            'Contingency Fuel': 130,
                            'Eta Gas Turbine': 0.22,
                            'Eta Gearbox': 0.96,
                            'Eta Propulsive': 0.9,
                            'Eta Electric Motor 1': 0.96,    #for serial config
                            'Eta Electric Motor 2': 0.96,    #for serial config
                            'Eta Electric Motor': 0.98,      #for parallel config
                            'Eta PMAD': 0.99,
                            'Specific Power Powertrain': [3900,7700],
                            'Specific Power PMAD': [2200,2200,2200],
                            'PowertoWeight Battery': 35, 
                            'PowertoWeight Powertrain': [150,33],
                            'PowertoWeight PMAD': 0
                            },

            "AerodynamicsInput" : {'AnalyticPolar': {'type': 'Quadratic', 'input': {'AR': 11, 'e_osw': 0.8}},
                                'Take Off Cl': 1.9,
                                'Landing Cl': 1.9,
                                'Minimum Cl': 0.20,
                                'Cd0': 0.017}
            },
            #####################################################################
        "HybridCruiseHighAltitude" : {
            "ConstraintsInput" : {'DISA': 0.,
                                  'Cruise': {'Speed': 0.5, 'Speed Type':'Mach', 'Beta': 0.95, 'Altitude': 8000.},
                                  'AEO Climb': {'Speed': 210, 'Speed Type':'KCAS', 'Beta': 0.97, 'Altitude': 6000., 'ROC': 5},
                                  'OEI Climb': {'Speed': 1.2*34.5, 'Speed Type': 'TAS', 'Beta': 1., 'Altitude': 0., 'Climb Gradient': 0.021},
                                  'Take Off': {'Speed': 90, 'Speed Type': 'TAS', 'Beta': 1., 'Altitude': 100., 'kTO': 1.2, 'sTO': 950},
                                  'Landing':{'Speed': 59., 'Speed Type': 'TAS', 'Altitude': 500.},
                                  'Turn':{'Speed': 210, 'Speed Type': 'KCAS', 'Beta': 0.9, 'Altitude': 5000, 'Load Factor': 1.1},
                                  'Ceiling':{'Speed': 0.5, 'Beta': 0.8, 'Altitude': 9500, 'HT': 0.5},
                                  'Acceleration':{'Mach 1': 0.3, 'Mach 2':0.4, 'DT': 180, 'Altitude': 6000, 'Beta': 0.9}},

            "MissionInput" : {'Range Mission': argRange/1.852,  #nautical miles but the input comes in km
                            'Range Diversion': 145,  #nautical miles
                            'Beta start': 0.97,
                            'Minimum SOC': 0.2,
                            'Payload Weight': argPayload-500 ,  #Kg
                            'Crew Weight': 500} , #Kg,

            "MissionStages" : {
                            'Takeoff':
                                {'Supplied Power Ratio':{'phi': argPhi}},

                            'Climb1': {'type': 'ConstantRateClimb', 'input': 
                                {'CB': 0.16, 'Speed': 77, 'StartAltitude': 100, 'EndAltitude': 1500}, 
                                'Supplied Power Ratio':{'phi_start': 0, 'phi_end':0 }},

                            'Climb2': {'type': 'ConstantRateClimb', 'input': 
                                {'CB': 0.08, 'Speed': 120, 'StartAltitude': 1500, 'EndAltitude': 4500}, 
                                'Supplied Power Ratio':{'phi_start': 0, 'phi_end':0 }},

                            'Climb3': {'type': 'ConstantRateClimb', 'input': 
                                {'CB': 0.07, 'Speed': 125, 'StartAltitude': 4500, 'EndAltitude': 8000}, 
                                'Supplied Power Ratio':{'phi_start': 0, 'phi_end': 0 }},

                            'Cruise': {'type': 'ConstantMachCruise', 'input': 
                                { 'Mach': 0.4, 'Altitude': 8000}, 
                            'Supplied Power Ratio':{'phi_start': argPhi, 'phi_end':argPhi }},

                            'Descent1': {'type': 'ConstantRateDescent', 'input':
                                {'CB': -0.04, 'Speed': 90, 'StartAltitude': 8000, 'EndAltitude': 200}, 
                                'Supplied Power Ratio':{'phi_start': argPhi, 'phi_end': argPhi }}},


            "DiversionStages" : {
                            'Climb1': {'type': 'ConstantRateClimb', 'input': 
                                    {'CB': 0.08, 'Speed': 110, 'StartAltitude': 200, 'EndAltitude': 3100}, 
                                    'Supplied Power Ratio':{'phi_start': 0, 'phi_end':0  }},

                            'Cruise': {'type': 'ConstantMachCruise', 'input':
                                    { 'Mach': 0.35, 'Altitude': 3100}, 
                                    'Supplied Power Ratio':{'phi_start': argPhi, 'phi_end':argPhi }},

                            'Descent1': {'type': 'ConstantRateDescent', 'input':
                                    {'CB': -0.04, 'Speed': 90, 'StartAltitude': 3100, 'EndAltitude': 200}, 
                                    'Supplied Power Ratio':{'phi_start': argPhi, 'phi_end':argPhi}}},

            "EnergyInput" : {'Ef': 43.5*10**6,
                            'Contingency Fuel': 130,
                            'Eta Gas Turbine': 0.22,
                            'Eta Gearbox': 0.96,
                            'Eta Propulsive': 0.9,
                            'Eta Electric Motor 1': 0.96,    #for serial config
                            'Eta Electric Motor 2': 0.96,    #for serial config
                            'Eta Electric Motor': 0.98,      #for parallel config
                            'Eta PMAD': 0.99,
                            'Specific Power Powertrain': [3900,7700],
                            'Specific Power PMAD': [2200,2200,2200],
                            'PowertoWeight Battery': 35, 
                            'PowertoWeight Powertrain': [150,33],
                            'PowertoWeight PMAD': 0
                            },

            "AerodynamicsInput" : {'AnalyticPolar': {'type': 'Quadratic', 'input': {'AR': 11, 'e_osw': 0.8}},
                                'Take Off Cl': 1.9,
                                'Landing Cl': 1.9,
                                'Minimum Cl': 0.20,
                                'Cd0': 0.017}
            },

            #####################################################################
        "HybridTOClimbHighAltitude" : {
            "ConstraintsInput" : {'DISA': 0.,
                                  'Cruise': {'Speed': 0.5, 'Speed Type':'Mach', 'Beta': 0.95, 'Altitude': 8000.},
                                  'AEO Climb': {'Speed': 210, 'Speed Type':'KCAS', 'Beta': 0.97, 'Altitude': 6000., 'ROC': 5},
                                  'OEI Climb': {'Speed': 1.2*34.5, 'Speed Type': 'TAS', 'Beta': 1., 'Altitude': 0., 'Climb Gradient': 0.021},
                                  'Take Off': {'Speed': 90, 'Speed Type': 'TAS', 'Beta': 1., 'Altitude': 100., 'kTO': 1.2, 'sTO': 950},
                                  'Landing':{'Speed': 59., 'Speed Type': 'TAS', 'Altitude': 500.},
                                  'Turn':{'Speed': 210, 'Speed Type': 'KCAS', 'Beta': 0.9, 'Altitude': 5000, 'Load Factor': 1.1},
                                  'Ceiling':{'Speed': 0.5, 'Beta': 0.8, 'Altitude': 9500, 'HT': 0.5},
                                  'Acceleration':{'Mach 1': 0.3, 'Mach 2':0.4, 'DT': 180, 'Altitude': 6000, 'Beta': 0.9}},

            "MissionInput" : {'Range Mission': argRange/1.852,  #nautical miles but the input comes in km
                            'Range Diversion': 145,  #nautical miles
                            'Beta start': 0.97,
                            'Minimum SOC': 0.2,
                            'Payload Weight': argPayload-500 ,  #Kg
                            'Crew Weight': 500} , #Kg,

            "MissionStages" : {
                            'Takeoff':
                                {'Supplied Power Ratio':{'phi': argPhi}},

                            'Climb1': {'type': 'ConstantRateClimb', 'input': 
                                {'CB': 0.16, 'Speed': 77, 'StartAltitude': 100, 'EndAltitude': 1500}, 
                                'Supplied Power Ratio':{'phi_start': argPhi, 'phi_end':argPhi }},

                            'Climb2': {'type': 'ConstantRateClimb', 'input': 
                                {'CB': 0.08, 'Speed': 120, 'StartAltitude': 1500, 'EndAltitude': 4500}, 
                                'Supplied Power Ratio':{'phi_start': argPhi, 'phi_end':argPhi }},

                            'Climb3': {'type': 'ConstantRateClimb', 'input': 
                                {'CB': 0.07, 'Speed': 125, 'StartAltitude': 4500, 'EndAltitude': 8000}, 
                                'Supplied Power Ratio':{'phi_start': argPhi, 'phi_end': argPhi }},

                            'Cruise': {'type': 'ConstantMachCruise', 'input': 
                                { 'Mach': 0.4, 'Altitude': 8000}, 
                            'Supplied Power Ratio':{'phi_start': 0, 'phi_end':0 }},

                            'Descent1': {'type': 'ConstantRateDescent', 'input':
                                {'CB': -0.04, 'Speed': 90, 'StartAltitude': 8000, 'EndAltitude': 200}, 
                                'Supplied Power Ratio':{'phi_start': 0, 'phi_end': 0  }}},


            "DiversionStages" : {
                            'Climb1': {'type': 'ConstantRateClimb', 'input': 
                                    {'CB': 0.08, 'Speed': 110, 'StartAltitude': 200, 'EndAltitude': 3100}, 
                                    'Supplied Power Ratio':{'phi_start': 0, 'phi_end':0  }},

                            'Cruise': {'type': 'ConstantMachCruise', 'input':
                                    { 'Mach': 0.35, 'Altitude': 3100}, 
                                    'Supplied Power Ratio':{'phi_start': 0, 'phi_end':0 }},

                            'Descent1': {'type': 'ConstantRateDescent', 'input':
                                    {'CB': -0.04, 'Speed': 90, 'StartAltitude': 3100, 'EndAltitude': 200}, 
                                    'Supplied Power Ratio':{'phi_start': 0, 'phi_end':0}}},

            "EnergyInput" : {'Ef': 43.5*10**6,
                            'Contingency Fuel': 130,
                            'Eta Gas Turbine': 0.22,
                            'Eta Gearbox': 0.96,
                            'Eta Propulsive': 0.9,
                            'Eta Electric Motor 1': 0.96,    #for serial config
                            'Eta Electric Motor 2': 0.96,    #for serial config
                            'Eta Electric Motor': 0.98,      #for parallel config
                            'Eta PMAD': 0.99,
                            'Specific Power Powertrain': [3900,7700],
                            'Specific Power PMAD': [2200,2200,2200],
                            'PowertoWeight Battery': 35, 
                            'PowertoWeight Powertrain': [150,33],
                            'PowertoWeight PMAD': 0
                            },

            "AerodynamicsInput" : {'AnalyticPolar': {'type': 'Quadratic', 'input': {'AR': 11, 'e_osw': 0.8}},
                                'Take Off Cl': 1.9,
                                'Landing Cl': 1.9,
                                'Minimum Cl': 0.20,
                                'Cd0': 0.017}
            }
    }
    return Profiles[argMission]