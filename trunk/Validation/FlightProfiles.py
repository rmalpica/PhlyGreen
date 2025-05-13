def MissionParameters(argRange, argPayload, argProfile, argPhi, argMission):
    Profiles = {
        "Mission-FelixFinger": {
            "ConstraintsInput": {
                "DISA": 0.0,
                "Cruise": {"Speed": 0.35, "Speed Type": "Mach", "Beta": 0.95, "Altitude": 3000.0},
                "AEO Climb": {
                    "Speed": 130,
                    "Speed Type": "KCAS",
                    "Beta": 0.97,
                    "Altitude": 2000.0,
                    "ROC": 8,
                },
                "OEI Climb": {
                    "Speed": 1.2 * 34.5,
                    "Speed Type": "TAS",
                    "Beta": 1.0,
                    "Altitude": 0.0,
                    "Climb Gradient": 0.021,
                },
                "Take Off": {
                    "Speed": 90,
                    "Speed Type": "TAS",
                    "Beta": 1.0,
                    "Altitude": 100.0,
                    "kTO": 1.2,
                    "sTO": 950,
                },
                "Landing": {"Speed": 59.0, "Speed Type": "TAS", "Altitude": 500.0},
                "Turn": {
                    "Speed": 110,
                    "Speed Type": "KCAS",
                    "Beta": 0.9,
                    "Altitude": 3000,
                    "Load Factor": 1.1,
                },
                "Ceiling": {"Speed": 0.5, "Beta": 0.8, "Altitude": 3500, "HT": 0.5},
                "Acceleration": {
                    "Mach 1": 0.3,
                    "Mach 2": 0.4,
                    "DT": 180,
                    "Altitude": 2800,
                    "Beta": 0.9,
                },
            },
            "MissionInput": {
                "Range Mission": argRange / 1.852,  # nautical miles but the input comes in km #TODO
                "Range Diversion": (270+95.4)/1.852,  # nautical miles
                "Beta start": 0.97,
                "Minimum SOC": 0.2,
                "Payload Weight": argPayload - 500,  # Kg #TODO
                "Crew Weight": 500,
            },  # Kg,
            "MissionStages": {
                "Takeoff": {"Supplied Power Ratio": {"phi": argPhi}},
                "Climb1": {
                    "type": "ConstantRateClimb",
                    "input": {"CB": 0.16, "Speed": 70, "StartAltitude": 100, "EndAltitude": 560},
                    "Supplied Power Ratio": {"phi_start": argPhi, "phi_end": argPhi},
                },
                "Climb2": {
                    "type": "ConstantRateClimb",
                    "input": {"CB": 0.08, "Speed": 90, "StartAltitude": 560, "EndAltitude": 1690},
                    "Supplied Power Ratio": {"phi_start": argPhi, "phi_end": argPhi},
                },
                "Climb3": {
                    "type": "ConstantRateClimb",
                    "input": {"CB": 0.07, "Speed": 100, "StartAltitude": 1690, "EndAltitude": 3000},
                    "Supplied Power Ratio": {"phi_start": argPhi, "phi_end": argPhi},
                },
                "Cruise": {
                    "type": "ConstantMachCruise",
                    "input": {"Mach": 0.35, "Altitude": 3000},
                    "Supplied Power Ratio": {"phi_start": argPhi, "phi_end": argPhi},
                },
                "Descent1": {
                    "type": "ConstantRateDescent",
                    "input": {"CB": -0.04, "Speed": 90, "StartAltitude": 3000, "EndAltitude": 200},
                    "Supplied Power Ratio": {"phi_start": argPhi, "phi_end": argPhi},
                },
            },
            "DiversionStages": {
                "Climb1": {
                    "type": "ConstantRateClimb",
                    "input": {"CB": 0.08, "Speed": 55, "StartAltitude": 200, "EndAltitude": 1000},
                    "Supplied Power Ratio": {"phi_start": argPhi, "phi_end": argPhi},
                },
                "Cruise": {
                    "type": "ConstantMachCruise",
                    "input": {"Mach": 0.244, "Altitude": 1000},
                    "Supplied Power Ratio": {"phi_start": argPhi, "phi_end": argPhi},
                },
                "Descent1": {
                    "type": "ConstantRateDescent",
                    "input": {"CB": -0.04, "Speed": 90, "StartAltitude": 1000, "EndAltitude": 200},
                    "Supplied Power Ratio": {"phi_start": argPhi, "phi_end": argPhi},
                },
            },
            "EnergyInput": {
                "Ef": 42.8 * 10**6,
                "Contingency Fuel": 0.1, # cant be zero otherwise the code sets it to 5% of total, just set it really low
                "Eta Gas Turbine": 0.211,
                "Eta Gearbox": 1,
                "Eta Propulsive": 0.9,
                "Eta Electric Motor 1": 0.96,  # for serial config
                "Eta Electric Motor 2": 0.96,  # for serial config
                "Eta Electric Motor": 0.98,  # for parallel config
                "Eta PMAD": 1,
                "Specific Power Powertrain": [3310, 5920],
                "Specific Power PMAD": [2200, 2200, 2200],
                # "PowertoWeight Battery": 35,
                # "PowertoWeight Powertrain": [150, 33],
                # "PowertoWeight PMAD": 0,
            },
            "AerodynamicsInput": {
                "AnalyticPolar": {"type": "quadratic", "input": {"AR": 9, "e_osw": 0.63}},
                "Take Off Cl": 1.9,
                "Landing Cl": 1.9,
                "Minimum Cl": 0.17,
                "Cd0": 0.025,
            },
        },
        #####################################################################
        "Mission-Dip-Electric": {
            "ConstraintsInput": {
                "DISA": 0.0,
                "Cruise": {"Speed": 0.35, "Speed Type": "Mach", "Beta": 0.95, "Altitude": 3000.0},
                "AEO Climb": {
                    "Speed": 130,
                    "Speed Type": "KCAS",
                    "Beta": 0.97,
                    "Altitude": 2000.0,
                    "ROC": 8,
                },
                "OEI Climb": {
                    "Speed": 1.2 * 34.5,
                    "Speed Type": "TAS",
                    "Beta": 1.0,
                    "Altitude": 0.0,
                    "Climb Gradient": 0.021,
                },
                "Take Off": {
                    "Speed": 90,
                    "Speed Type": "TAS",
                    "Beta": 1.0,
                    "Altitude": 100.0,
                    "kTO": 1.2,
                    "sTO": 950,
                },
                "Landing": {"Speed": 59.0, "Speed Type": "TAS", "Altitude": 500.0},
                "Turn": {
                    "Speed": 110,
                    "Speed Type": "KCAS",
                    "Beta": 0.9,
                    "Altitude": 3000,
                    "Load Factor": 1.1,
                },
                "Ceiling": {"Speed": 0.5, "Beta": 0.8, "Altitude": 3500, "HT": 0.5},
                "Acceleration": {
                    "Mach 1": 0.3,
                    "Mach 2": 0.4,
                    "DT": 180,
                    "Altitude": 2800,
                    "Beta": 0.9,
                },
            },
            "MissionInput": {
                "Range Mission": argRange / 1.852,  # nautical miles but the input comes in km #TODO
                "Range Diversion": (150)/1.852,  # nautical miles
                "Beta start": 0.97,
                "Minimum SOC": 0.2,
                "Payload Weight": argPayload - 500,  # Kg #TODO
                "Crew Weight": 500,
            },  # Kg,
            "MissionStages": {
                "Takeoff": {"Supplied Power Ratio": {"phi": argPhi}},
                "Climb1": {
                    "type": "ConstantRateClimb",
                    "input": {"CB": 0.16, "Speed": 70, "StartAltitude": 100, "EndAltitude": 560},
                    "Supplied Power Ratio": {"phi_start": argPhi, "phi_end": argPhi},
                },
                "Climb2": {
                    "type": "ConstantRateClimb",
                    "input": {"CB": 0.08, "Speed": 90, "StartAltitude": 560, "EndAltitude": 1690},
                    "Supplied Power Ratio": {"phi_start": argPhi, "phi_end": argPhi},
                },
                "Climb3": {
                    "type": "ConstantRateClimb",
                    "input": {"CB": 0.07, "Speed": 100, "StartAltitude": 1690, "EndAltitude": 3000},
                    "Supplied Power Ratio": {"phi_start": argPhi, "phi_end": argPhi},
                },
                "Cruise": {
                    "type": "ConstantMachCruise",
                    "input": {"Mach": 0.35, "Altitude": 3000},
                    "Supplied Power Ratio": {"phi_start": argPhi, "phi_end": argPhi},
                },
                "Descent1": {
                    "type": "ConstantRateDescent",
                    "input": {"CB": -0.04, "Speed": 90, "StartAltitude": 3000, "EndAltitude": 200},
                    "Supplied Power Ratio": {"phi_start": argPhi, "phi_end": argPhi},
                },
            },
            "DiversionStages": {
                "Climb1": {
                    "type": "ConstantRateClimb",
                    "input": {"CB": 0.08, "Speed": 100, "StartAltitude": 200, "EndAltitude": 3000},
                    "Supplied Power Ratio": {"phi_start": argPhi, "phi_end": argPhi},
                },
                "Cruise": {
                    "type": "ConstantMachCruise",
                    "input": {"Mach": 0.35, "Altitude": 3000},
                    "Supplied Power Ratio": {"phi_start": argPhi, "phi_end": argPhi},
                },
                "Descent1": {
                    "type": "ConstantRateDescent",
                    "input": {"CB": -0.04, "Speed": 90, "StartAltitude": 3000, "EndAltitude": 200},
                    "Supplied Power Ratio": {"phi_start": argPhi, "phi_end": argPhi},
                },
            },
            "EnergyInput": {
                "Ef": 42.8 * 10**6,
                "Contingency Fuel": 0.1, # cant be zero otherwise the code sets it to 5% of total, just set it really low
                "Eta Gas Turbine": 0.211,
                "Eta Gearbox": 1,
                "Eta Propulsive": 0.9,
                "Eta Electric Motor 1": 0.96,  # for serial config
                "Eta Electric Motor 2": 0.96,  # for serial config
                "Eta Electric Motor": 0.98,  # for parallel config
                "Eta PMAD": 1,
                "Specific Power Powertrain": [3310, 5920],
                "Specific Power PMAD": [2200, 2200, 2200],
                # "PowertoWeight Battery": 35,
                # "PowertoWeight Powertrain": [150, 33],
                # "PowertoWeight PMAD": 0,
            },
            "AerodynamicsInput": {
                "AnalyticPolar": {"type": "quadratic", "input": {"AR": 9, "e_osw": 0.63}},
                "Take Off Cl": 1.9,
                "Landing Cl": 1.9,
                "Minimum Cl": 0.17,
                "Cd0": 0.025,
            },
        },
        #####################################################################
        "Mission-Dip-Half": {
            "ConstraintsInput": {
                "DISA": 0.0,
                "Cruise": {"Speed": 0.35, "Speed Type": "Mach", "Beta": 0.95, "Altitude": 3000.0},
                "AEO Climb": {
                    "Speed": 130,
                    "Speed Type": "KCAS",
                    "Beta": 0.97,
                    "Altitude": 2000.0,
                    "ROC": 8,
                },
                "OEI Climb": {
                    "Speed": 1.2 * 34.5,
                    "Speed Type": "TAS",
                    "Beta": 1.0,
                    "Altitude": 0.0,
                    "Climb Gradient": 0.021,
                },
                "Take Off": {
                    "Speed": 90,
                    "Speed Type": "TAS",
                    "Beta": 1.0,
                    "Altitude": 100.0,
                    "kTO": 1.2,
                    "sTO": 950,
                },
                "Landing": {"Speed": 59.0, "Speed Type": "TAS", "Altitude": 500.0},
                "Turn": {
                    "Speed": 110,
                    "Speed Type": "KCAS",
                    "Beta": 0.9,
                    "Altitude": 3000,
                    "Load Factor": 1.1,
                },
                "Ceiling": {"Speed": 0.5, "Beta": 0.8, "Altitude": 3500, "HT": 0.5},
                "Acceleration": {
                    "Mach 1": 0.3,
                    "Mach 2": 0.4,
                    "DT": 180,
                    "Altitude": 2800,
                    "Beta": 0.9,
                },
            },
            "MissionInput": {
                "Range Mission": argRange / 1.852,  # nautical miles but the input comes in km #TODO
                "Range Diversion": (150)/1.852,  # nautical miles
                "Beta start": 0.97,
                "Minimum SOC": 0.2,
                "Payload Weight": argPayload - 500,  # Kg #TODO
                "Crew Weight": 500,
            },  # Kg,
            "MissionStages": {
                "Takeoff": {"Supplied Power Ratio": {"phi": argPhi}},
                "Climb1": {
                    "type": "ConstantRateClimb",
                    "input": {"CB": 0.16, "Speed": 70, "StartAltitude": 100, "EndAltitude": 560},
                    "Supplied Power Ratio": {"phi_start": argPhi, "phi_end": argPhi},
                },
                "Climb2": {
                    "type": "ConstantRateClimb",
                    "input": {"CB": 0.08, "Speed": 90, "StartAltitude": 560, "EndAltitude": 1690},
                    "Supplied Power Ratio": {"phi_start": argPhi, "phi_end": argPhi},
                },
                "Climb3": {
                    "type": "ConstantRateClimb",
                    "input": {"CB": 0.07, "Speed": 100, "StartAltitude": 1690, "EndAltitude": 3000},
                    "Supplied Power Ratio": {"phi_start": argPhi, "phi_end": argPhi},
                },
                "Cruise": {
                    "type": "ConstantMachCruise",
                    "input": {"Mach": 0.35, "Altitude": 3000},
                    "Supplied Power Ratio": {"phi_start": argPhi, "phi_end": argPhi},
                },
                "Descent1": {
                    "type": "ConstantRateDescent",
                    "input": {"CB": -0.04, "Speed": 90, "StartAltitude": 3000, "EndAltitude": 200},
                    "Supplied Power Ratio": {"phi_start": argPhi, "phi_end": 0*argPhi},
                },
            },
            "DiversionStages": {
                "Climb1": {
                    "type": "ConstantRateClimb",
                    "input": {"CB": 0.08, "Speed": 100, "StartAltitude": 200, "EndAltitude": 3000},
                    "Supplied Power Ratio": {"phi_start": 0*argPhi, "phi_end": 0*argPhi},
                },
                "Cruise": {
                    "type": "ConstantMachCruise",
                    "input": {"Mach": 0.35, "Altitude": 3000},
                    "Supplied Power Ratio": {"phi_start": 0*argPhi, "phi_end": 0*argPhi},
                },
                "Descent1": {
                    "type": "ConstantRateDescent",
                    "input": {"CB": -0.04, "Speed": 90, "StartAltitude": 3000, "EndAltitude": 200},
                    "Supplied Power Ratio": {"phi_start": 0*argPhi, "phi_end": 0*argPhi},
                },
            },
            "EnergyInput": {
                "Ef": 42.8 * 10**6,
                "Contingency Fuel": 0.1, # cant be zero otherwise the code sets it to 5% of total, just set it really low
                "Eta Gas Turbine": 0.211,
                "Eta Gearbox": 1,
                "Eta Propulsive": 0.9,
                "Eta Electric Motor 1": 0.96,  # for serial config
                "Eta Electric Motor 2": 0.96,  # for serial config
                "Eta Electric Motor": 0.98,  # for parallel config
                "Eta PMAD": 1,
                "Specific Power Powertrain": [3310, 5920],
                "Specific Power PMAD": [2200, 2200, 2200],
                # "PowertoWeight Battery": 35,
                # "PowertoWeight Powertrain": [150, 33],
                # "PowertoWeight PMAD": 0,
            },
            "AerodynamicsInput": {
                "AnalyticPolar": {"type": "quadratic", "input": {"AR": 9, "e_osw": 0.63}},
                "Take Off Cl": 1.9,
                "Landing Cl": 1.9,
                "Minimum Cl": 0.17,
                "Cd0": 0.025,
            },
        },

        "Mission-Temperature-Test": {
            "ConstraintsInput": {
                "DISA": 0.0,
                "Cruise": {"Speed": 0.35, "Speed Type": "Mach", "Beta": 0.95, "Altitude": 3000.0},
                "AEO Climb": {
                    "Speed": 130,
                    "Speed Type": "KCAS",
                    "Beta": 0.97,
                    "Altitude": 2000.0,
                    "ROC": 8,
                },
                "OEI Climb": {
                    "Speed": 1.2 * 34.5,
                    "Speed Type": "TAS",
                    "Beta": 1.0,
                    "Altitude": 0.0,
                    "Climb Gradient": 0.021,
                },
                "Take Off": {
                    "Speed": 90,
                    "Speed Type": "TAS",
                    "Beta": 1.0,
                    "Altitude": 100.0,
                    "kTO": 1.2,
                    "sTO": 950,
                },
                "Landing": {"Speed": 59.0, "Speed Type": "TAS", "Altitude": 500.0},
                "Turn": {
                    "Speed": 110,
                    "Speed Type": "KCAS",
                    "Beta": 0.9,
                    "Altitude": 3000,
                    "Load Factor": 1.1,
                },
                "Ceiling": {"Speed": 0.5, "Beta": 0.8, "Altitude": 3500, "HT": 0.5},
                "Acceleration": {
                    "Mach 1": 0.3,
                    "Mach 2": 0.4,
                    "DT": 180,
                    "Altitude": 2800,
                    "Beta": 0.9,
                },
            },
            "MissionInput": {
                "Range Mission": argRange / 1.852,  # nautical miles but the input comes in km #TODO
                "Range Diversion": (50)/1.852,  # nautical miles
                "Beta start": 0.97,
                "Minimum SOC": 0.2,
                "Payload Weight": argPayload - 500,  # Kg #TODO
                "Crew Weight": 500,
            },  # Kg,
            "MissionStages": {
                "Takeoff": {"Supplied Power Ratio": {"phi": argPhi}},
                "Climb1": {
                    "type": "ConstantRateClimb",
                    "input": {"CB": 0.16, "Speed": 70, "StartAltitude": 100, "EndAltitude": 560},
                    "Supplied Power Ratio": {"phi_start": 3*argPhi, "phi_end": 3*argPhi},
                },
                "Climb2": {
                    "type": "ConstantRateClimb",
                    "input": {"CB": 0.08, "Speed": 90, "StartAltitude": 560, "EndAltitude": 1690},
                    "Supplied Power Ratio": {"phi_start": 3*argPhi, "phi_end": 2*argPhi},
                },
                "Climb3": {
                    "type": "ConstantRateClimb",
                    "input": {"CB": 0.07, "Speed": 100, "StartAltitude": 1690, "EndAltitude": 3000},
                    "Supplied Power Ratio": {"phi_start": 2*argPhi, "phi_end": argPhi},
                },
                "Cruise": {
                    "type": "ConstantMachCruise",
                    "input": {"Mach": 0.35, "Altitude": 3000},
                    "Supplied Power Ratio": {"phi_start": argPhi, "phi_end": argPhi},
                },
                "Descent1": {
                    "type": "ConstantRateDescent",
                    "input": {"CB": -0.04, "Speed": 90, "StartAltitude": 3000, "EndAltitude": 200},
                    "Supplied Power Ratio": {"phi_start": argPhi, "phi_end": 0},
                },
            },
            "DiversionStages": {
                "Climb1": {
                    "type": "ConstantRateClimb",
                    "input": {"CB": 0.08, "Speed": 100, "StartAltitude": 200, "EndAltitude": 500},
                    "Supplied Power Ratio": {"phi_start": 0, "phi_end": 0},
                },
                "Cruise": {
                    "type": "ConstantMachCruise",
                    "input": {"Mach": 0.35, "Altitude": 500},
                    "Supplied Power Ratio": {"phi_start": 0, "phi_end": 0},
                },
                "Descent1": {
                    "type": "ConstantRateDescent",
                    "input": {"CB": -0.04, "Speed": 90, "StartAltitude": 500, "EndAltitude": 200},
                    "Supplied Power Ratio": {"phi_start": 0, "phi_end": 0},
                },
            },
            "EnergyInput": {
                "Ef": 42.8 * 10**6,
                "Contingency Fuel": 0.1, # cant be zero otherwise the code sets it to 5% of total, just set it really low
                "Eta Gas Turbine": 0.211,
                "Eta Gearbox": 1,
                "Eta Propulsive": 0.9,
                "Eta Electric Motor 1": 0.96,  # for serial config
                "Eta Electric Motor 2": 0.96,  # for serial config
                "Eta Electric Motor": 0.98,  # for parallel config
                "Eta PMAD": 1,
                "Specific Power Powertrain": [3310, 5920],
                "Specific Power PMAD": [2200, 2200, 2200],
                # "PowertoWeight Battery": 35,
                # "PowertoWeight Powertrain": [150, 33],
                # "PowertoWeight PMAD": 0,
            },
            "AerodynamicsInput": {
                "AnalyticPolar": {"type": "quadratic", "input": {"AR": 9, "e_osw": 0.63}},
                "Take Off Cl": 1.9,
                "Landing Cl": 1.9,
                "Minimum Cl": 0.17,
                "Cd0": 0.025,
            },
        },


    }
    return Profiles[argMission]
