import math
import numpy as np
import PhlyGreen.Utilities.Units as Units

class SystemEquipment:

    def __init__(self, aircraft, input):
        self.aircraft = aircraft
        self.input = input

    def AntiIcingMass(self):

        span = self.input['WING']['SPAN']
        sweep = self.input['WING']['SWEEP']
        diam_avg = self.input['NACELLE']['AVG_DIAM']
        total_num_eng = self.input['ENGINE']['N_ENGINES']
        max_width = self.input['FUSELAGE']['MAX_WIDTH']
        scaler = self.input['SYSTEM_EQUIPMENT']['ANTIICING_SCALER']

        f_nacelle = 0.5 * diam_avg * total_num_eng ** 0.5 if total_num_eng > 4 else diam_avg
        count_factor = 4.0 + 2.0 * math.atan((total_num_eng - 4.0) / 3.0) if total_num_eng > 4 else total_num_eng

        mass = (
                (span / np.cos(sweep * np.pi / 180))
                + 3.8 * f_nacelle * count_factor + 1.5 * max_width) * scaler 

        return mass

    def APUMass(self):

        planform = self.input['SYSTEM_EQUIPMENT']['PLANFORM_AREA']
        pax = self.input['SYSTEM_EQUIPMENT']['N_PAX']
        scaler = self.input['SYSTEM_EQUIPMENT']['APU_SCALER']

        mass = (54.0 * planform ** 0.3 + 5.4 * pax ** 0.9) * scaler

        return mass

    def AvionicsMass(self):

        des_range = self.aircraft.mission.profile.MissionRange
        crew = self.input['SYSTEM_EQUIPMENT']['N_CREW']
        planform = self.input['SYSTEM_EQUIPMENT']['PLANFORM_AREA']
        scaler = self.input['SYSTEM_EQUIPMENT']['AVIONICS_SCALER']

        mass = 15.8 * des_range**0.1 * crew**0.7 * planform**0.43 * scaler

        return mass

    def AirConditioningMass(self):

        planform = self.input['SYSTEM_EQUIPMENT']['PLANFORM_AREA']
        height = self.input['FUSELAGE']['MAX_HEIGHT']
        pax = self.input['SYSTEM_EQUIPMENT']['N_PAX']
        scaler = self.input['SYSTEM_EQUIPMENT']['AC_SCALER']
        max_mach = self.aircraft.constraint.CruiseConstraints['Speed']
        avionics_wt = self.AvionicsMass()

        mass = ((3.2 * (planform * height)**0.6 + 9 * pax**0.83) * max_mach + 0.075 * avionics_wt) * scaler

        return mass

    def ElectricalMass(self):

        length = self.input['FUSELAGE']['LENGTH']
        width = self.input['FUSELAGE']['MAX_WIDTH']
        nfuse = self.input['FUSELAGE']['NUM_FUSELAGES']
        num_engines = self.input['ENGINE']['N_ENGINES']
        ncrew = self.input['SYSTEM_EQUIPMENT']['N_CREW']
        npass = self.input['SYSTEM_EQUIPMENT']['N_PAX']
        mass_scaler = self.input['SYSTEM_EQUIPMENT']['ELECTRICAL_SCALER']
        num_engines_factor =  4.0 + 2.0 * math.atan((num_engines - 4.0) / 3.0) if num_engines > 4 else num_engines

        mass = 92.0 * length**0.4 * width**0.14 * nfuse**0.27 * num_engines_factor**0.69 * (1.0 + 0.044 * ncrew + 0.0015 * npass) * mass_scaler 

        return mass

    def FurnishingMass(self):

        flight_crew_count = self.input['SYSTEM_EQUIPMENT']['N_CREW']
        first_class_count = self.input['SYSTEM_EQUIPMENT']['N_FIRST_CLASS'] # can you believe I'm doing this?
        business_class_count = self.input['SYSTEM_EQUIPMENT']['N_BUSINESS_CLASS']
        tourist_class_count = self.input['SYSTEM_EQUIPMENT']['N_TOURIST_CLASS']
        pax_compart_length = self.input['SYSTEM_EQUIPMENT']['PASSENGER_COMPARTMENT_LENGTH']
        fuse_max_width = self.input['FUSELAGE']['MAX_WIDTH']
        fuse_max_height = self.input['FUSELAGE']['MAX_HEIGHT']
        fuse_count = self.input['FUSELAGE']['NUM_FUSELAGES']
        scaler = self.input['SYSTEM_EQUIPMENT']['FURNISHING_SCALER']


        mass = (
                127.0 * flight_crew_count + 112.0 * first_class_count
                + 78.0 * business_class_count + 44.0 * tourist_class_count
                + 2.6 * pax_compart_length * (fuse_max_width + fuse_max_height)
                * fuse_count
            ) * scaler

        return mass

    def HydraulicsMass(self):

        planform = self.input['SYSTEM_EQUIPMENT']['PLANFORM_AREA']
        area =  Units.m2toft2(self.input['GROSS_WEIGHT']/self.aircraft.DesignWTOoS) # ce l'abbiamo
        num_wing_eng = self.input['ENGINE']['N_WING_ENGINES']
        num_fuse_eng = self.input['ENGINE']['N_FUSELAGE_ENGINES']
        sys_press = self.input['SYSTEM_EQUIPMENT']['SYSTEM_PRESSURE']
        var_sweep = self.input['WING']['VAR_SWEEP_MASS_PENALTY']
        max_mach = self.aircraft.constraint.CruiseConstraints['Speed']
        scaler = self.input['SYSTEM_EQUIPMENT']['HYDRAULICS_SCALER'] 
        num_wing_eng_fact = 4.0 + 2.0 * math.atan((num_wing_eng - 4.0) / 3.0) if num_wing_eng > 4 else num_wing_eng
        num_fuse_eng_fact = 4.0 + 2.0 * math.atan((num_fuse_eng - 4.0) / 3.0) if num_fuse_eng > 4 else num_fuse_eng

        mass = (
                0.57 * (planform + 0.27 * area)
                * (1 + 0.03 * num_wing_eng_fact + 0.05 * num_fuse_eng_fact)
                * (3000 / sys_press)**0.35 * (1 + 0.04 * var_sweep) * max_mach**0.33
                * scaler)

        return mass

    def InstrumentsMass(self):

        fuse_area = self.input['SYSTEM_EQUIPMENT']['PLANFORM_AREA']
        max_mach = self.aircraft.constraint.CruiseConstraints['Speed']
        num_crew = self.input['SYSTEM_EQUIPMENT']['N_CREW']
        num_wing_eng = self.input['ENGINE']['N_WING_ENGINES']
        num_fuse_eng = self.input['ENGINE']['N_FUSELAGE_ENGINES']
        num_wing_eng_fact = 4.0 + 2.0 * math.atan((num_wing_eng - 4.0) / 3.0) if num_wing_eng > 4 else num_wing_eng
        num_fuse_eng_fact = 4.0 + 2.0 * math.atan((num_fuse_eng - 4.0) / 3.0) if num_fuse_eng > 4 else num_fuse_eng

        mass = (
                0.48 * fuse_area**0.57 * max_mach**0.5
                * (10.0 + 2.5 * num_crew + num_wing_eng_fact + 1.5 * num_fuse_eng_fact)
            )

        return mass

    def SurfaceControlsMass(self):

        flap_ratio = self.input['SYSTEM_EQUIPMENT']['CONTROL_SURFACE_AREA_RATIO']
        wing_area = Units.m2toft2(self.input['GROSS_WEIGHT']/self.aircraft.DesignWTOoS) 
        max_mach = self.aircraft.constraint.CruiseConstraints['Speed']
        gross_weight = Units.kgTolb(self.input['GROSS_WEIGHT']) 
        scaler = self.input['SYSTEM_EQUIPMENT']['SURFACE_CONTROLS_SCALER']


        surface_flap_area = flap_ratio*wing_area

        mass = 1.1*max_mach**.52 * surface_flap_area**.6 * gross_weight**.32 * scaler

        return mass

    def SystemEquipmentMass(self):

        self.system_equipment_mass = self.AirConditioningMass() + self.AntiIcingMass() + self.APUMass() + self.AvionicsMass() 
        + self.ElectricalMass() + self.FurnishingMass() + self.HydraulicsMass() + self.InstrumentsMass()
        + self.SurfaceControlsMass()

        return None