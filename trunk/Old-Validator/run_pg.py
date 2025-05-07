"""
Module containing all the code of a pre configured PhlyGreen setup in
a single class that has the functions that may be used to validate
a flight configuration and export its data to be plotted
"""

from datetime import datetime
import sys
import numpy as np
import FlightProfiles
sys.path.insert(0, "../")
import PhlyGreen as pg
from FLOPS_input import FLOPS_input


class FlightRun:
    """
    class that contains the data
    related to the current flight run
    """

    def __init__(self, flightargs):
        """
        Prints to console data about the flight and
        creates some metadata for the logs
        """
        arg_range, arg_payload, arg_arch, arg_cell, arg_s_energy, arg_s_power, arg_pack_v, arg_phi, arg_mission = flightargs
        self.arg_str = f"{arg_range}-{arg_payload}-{arg_arch}-{arg_s_energy}-{arg_s_power}-{arg_phi}-{arg_mission}"
        
        if arg_s_energy is None:
            arg_s_energy=6000

        if arg_s_power is None:
            arg_s_power = arg_s_energy * 8/1.5
            

        # load the flight profile
        flight_profile = FlightProfiles.MissionParameters(
            arg_range, arg_payload, arg_arch, arg_phi, arg_mission
        )
        # write all inputs to a dictionary for posteriority right away
        self.inputs = {
            "Powerplant": arg_arch,
            "Mission Name": arg_mission,
            "Range": arg_range,
            "Payload": arg_payload,
            "Cell Specific Energy": arg_s_energy,
            "Cell Specific Power": arg_s_power,
            "Base Phi": arg_phi,
            "Mission Profile": flight_profile,
        }
        self.outputs = {}
        self.outputs_max = {}
        self.outputs_min = {}
        self.aircraft_parameters = {}
        # self.perf_profiling={}

        # Prettify the cell parameters so they dont all 
        # come out as "None" if the defaults are used
        profile_energy = "default energy" if arg_s_energy is None else f"{arg_s_energy}Wh/kg"
        profile_power  = "default power" if arg_s_power is None else f"{arg_s_power}W/kg"

        # Print the inputs to the console
        print(
            f"--------------------------------------------------<||\n"
            f"{datetime.now().isoformat()}\n"
            f"Starting with configuration:\n"
            f"{arg_arch} Powerplant\n"
            f"Mission Profile: {arg_mission}\n"
            f"Cell @ {profile_energy} & {profile_power} \n"
            f"Phi = {arg_phi}\n"
            f"Range = {arg_range}km\n"
            f"Payload = {arg_payload}kg\n"
            f"Flight Name: {self.arg_str}\n"
            f"- - - - - - - - - - - - - - - - - - - - - - - - - -\n"
        )

        # setup just to initialize everything
        powertrain      = pg.Systems.Powertrain.Powertrain(None)
        structures      = pg.Systems.Structures.Structures(None)
        aerodynamics    = pg.Systems.Aerodynamics.Aerodynamics(None)
        performance     = pg.Performance.Performance(None)
        mission         = pg.Mission.Mission(None)
        weight          = pg.Weight.Weight(None)
        constraint      = pg.Constraint.Constraint(None)
        welltowake      = pg.WellToWake.WellToWake(None)
        battery         = pg.Systems.Battery.Battery(None)
        climateimpact   = pg.ClimateImpact.ClimateImpact(None)

        self.myaircraft = pg.Aircraft(
            powertrain,
            structures,
            aerodynamics,
            performance,
            mission,
            weight,
            constraint,
            welltowake,
            battery,
            climateimpact,
        )

        powertrain.aircraft     = self.myaircraft
        structures.aircraft     = self.myaircraft
        aerodynamics.aircraft   = self.myaircraft
        mission.aircraft        = self.myaircraft
        performance.aircraft    = self.myaircraft
        weight.aircraft         = self.myaircraft
        constraint.aircraft     = self.myaircraft
        welltowake.aircraft     = self.myaircraft
        battery.aircraft        = self.myaircraft
        climateimpact.aircraft  = self.myaircraft

        self.myaircraft.ConstraintsInput    = flight_profile["ConstraintsInput"]
        self.myaircraft.AerodynamicsInput   = flight_profile["AerodynamicsInput"]
        self.myaircraft.MissionInput        = flight_profile["MissionInput"]
        self.myaircraft.MissionStages       = flight_profile["MissionStages"]
        self.myaircraft.DiversionStages     = flight_profile["DiversionStages"]
        self.myaircraft.EnergyInput         = flight_profile["EnergyInput"]

        self.myaircraft.BatteryInput = {
            "Model": arg_cell,
            "SpecificPower": arg_s_power,
            "SpecificEnergy": arg_s_energy,
            "Minimum SOC": 0.2,
            "Pack Voltage": arg_pack_v,
            "Class":"I"
        }

        self.myaircraft.Configuration = arg_arch
        self.myaircraft.HybridType    = "Parallel"
        self.myaircraft.AircraftType  = "ATR"

        self.myaircraft.constraint.SetInput()
        self.myaircraft.mission.InitializeProfile()
        self.myaircraft.mission.SetInput()
        self.myaircraft.aerodynamics.SetInput()
        self.myaircraft.powertrain.SetInput()

        # Initialize Weight Estimator
        self.myaircraft.weight.Class = 'I'
        self.myaircraft.FLOPSInput = FLOPS_input

        self.myaircraft.weight.SetInput()
        self.myaircraft.battery.SetInput()


    def run_and_validate(self):
        """activates the aircraft sizing loop.
        Returns true or false depending on if the
        brent algorithm can find a solution
        """
        self.myaircraft.constraint.FindDesignPoint()
        try:
            self.myaircraft.weight.WeightEstimation()
            return True
        except Exception as err:
            errmsg = "f(a) and f(b) must have different signs"
            if errmsg == str(err):
                return False
            print(f"UNEXPECTED EXCEPTION OCCURRED IN FLIGHT {self.arg_str}")
            raise

    def process_fuel_data(self):
        """Data processing for fuel only aircraft"""
        self.myaircraft.WingSurface = (
            self.myaircraft.weight.WTO / self.myaircraft.DesignWTOoS * 9.81
        )
        times = np.array([])
        e_f = np.array([])
        beta = np.array([])
        for array in self.myaircraft.mission.integral_solution:
            times = np.concatenate([times, array.t])
            e_f = np.concatenate([e_f, array.y[0]])
            beta = np.concatenate([beta, array.y[1]])

        power_propulsive = [
            (self.myaircraft.weight.WTO / 1000)
            * self.myaircraft.performance.PoWTO(
                self.myaircraft.DesignWTOoS,
                beta[t],
                self.myaircraft.mission.profile.PowerExcess(times[t]),
                1,
                self.myaircraft.mission.profile.Altitude(times[t]),
                self.myaircraft.mission.DISA,
                self.myaircraft.mission.profile.Velocity(times[t]),
                "TAS",
            )
            for t in range(len(times))
        ]

        self.outputs = {
                "Time": times.tolist(),
                "Fuel Energy": e_f.tolist(),
                "Beta": beta.tolist(),
                "Total Power": power_propulsive,
                "Altitude": self.myaircraft.mission.profile.Altitude(times).tolist(),
            }

    def process_hybrid_data(self):
        """Data processing for hybrid aircraft"""
        self.myaircraft.WingSurface = (
            self.myaircraft.weight.WTO / self.myaircraft.DesignWTOoS * 9.81
        )
        times = np.array([])
        e_f   = np.array([])
        e_bat = np.array([])
        beta  = np.array([])
        for array in self.myaircraft.mission.integral_solution:
            times = np.concatenate([times, array.t])
            e_f   = np.concatenate([e_f  , array.y[0]])
            e_bat = np.concatenate([e_bat, array.y[1]])
            beta  = np.concatenate([beta , array.y[2]])

        phi = [self.myaircraft.mission.profile.SuppliedPowerRatio(t) for t in times]

        # toplot = np.array(self.myaircraft.mission.plottingVars)
        # arrtime = toplot[:, 0]  # must be equal to 'times'
        # if not all(arrtime == times):
        #     raise ValueError(
        #         f"something broke badly and the two time vectors are not equal:{arrtime} vs {times}"
        #     )
        # soc   = toplot[:, 1]
        # v_oc  = toplot[:, 2]
        # v_out = toplot[:, 3]
        # curr  = toplot[:, 4]
        # temp  = toplot[:, 5]
        # atemp = toplot[:, 6]
        # alt   = toplot[:, 7]
        # mdot   = toplot[:, 8]
        # spent_pwr = v_oc * curr
        # delivered_pwr = v_out * curr
        # batt_efficiency = v_out / v_oc

        power_propulsive = [
            (self.myaircraft.weight.WTO / 1000)
            * self.myaircraft.performance.PoWTO(
                self.myaircraft.DesignWTOoS,
                beta[t],
                self.myaircraft.mission.profile.PowerExcess(times[t]),
                1,
                self.myaircraft.mission.profile.Altitude(times[t]),
                self.myaircraft.mission.DISA,
                self.myaircraft.mission.profile.Velocity(times[t]),
                "TAS",
            )
            for t in range(len(times))
        ]

        self.outputs = {
                "Phi": phi,
                # "SOC": soc.tolist(),
                "Beta": beta.tolist(),
                "Time": times.tolist(),
                # "Altitude": alt.tolist(),
                "Fuel Energy": e_f.tolist(),
                "Total Power": power_propulsive,
                "Battery Energy": e_bat.tolist(),
                # "Battery current": curr.tolist(),
                # "Air Temperature": atemp.tolist(),
                # "Battery Voltage": v_out.tolist(),
                # "Cooling Flow Rate": mdot.tolist(),
                # "Battery OC Voltage": v_oc.tolist(),
                # "Battery Temperature": temp.tolist(),
                # "Battery Spent Power": spent_pwr.tolist(),
                # "Battery Efficiency": batt_efficiency.tolist(),
                # "Battery Delivered Power": delivered_pwr.tolist(),
            }
        for k, v in self.outputs.items():
            self.outputs_max[f"Max {k}"] = max(v)
            self.outputs_min[f"Min {k}"] = min(v)

    def get_fuel_parameters(self):
        """
        conveniently pack together all the parameters 
        of interest for the conventional aircarft
        """
        dic_outputs = {
            "Fuel Mass": self.myaircraft.weight.Wf,
            "Block Fuel Mass": self.myaircraft.weight.Wf + self.myaircraft.weight.final_reserve,
            "Structure Mass": self.myaircraft.weight.WStructure,
            "Powertrain Mass": self.myaircraft.weight.WPT,
            "Empty Weight": self.myaircraft.weight.WPT
            + self.myaircraft.weight.WStructure
            + self.myaircraft.weight.WCrew,
            "Zero Fuel Weight": self.myaircraft.weight.WPT
            + self.myaircraft.weight.WStructure
            + self.myaircraft.weight.WCrew
            + self.myaircraft.weight.WPayload,
            "Takeoff Weight": self.myaircraft.weight.WTO,
            "Wing Surface": self.myaircraft.WingSurface,
            "TakeOff Engine Shaft PP": self.myaircraft.mission.TO_PP / 1000,  # PP = Peak Power
            "Climb Cruise Engine Shaft PP": self.myaircraft.mission.Max_PEng
            / 1000,  # PP = Peak Power
            "Battery Mass": 0,
            "TakeOff Battery PP": 0,  # PP = Peak Power
            "Climb Cruise Battery PP": 0,  # PP = Peak Power
            "Total Iterations": 0, # needed to be compatible with the old phlygreen code
        }

        self.aircraft_parameters.update(dic_outputs)

    def get_hybrid_parameters(self):
        """
        conveniently pack together all the parameters
        of interest for the hybrid aircarft
        """
        dic_outputs = {
            "Fuel Mass": self.myaircraft.weight.Wf,
            "Block Fuel Mass": self.myaircraft.weight.Wf + self.myaircraft.weight.final_reserve,
            "Structure Mass": self.myaircraft.weight.WStructure,
            "Powertrain Mass": self.myaircraft.weight.WPT,
            "Empty Weight": self.myaircraft.weight.WPT
            + self.myaircraft.weight.WStructure
            + self.myaircraft.weight.WCrew,
            "Zero Fuel Weight": self.myaircraft.weight.WPT
            + self.myaircraft.weight.WStructure
            + self.myaircraft.weight.WCrew
            + self.myaircraft.weight.WPayload,
            "Takeoff Weight": self.myaircraft.weight.WTO,
            "Wing Surface": self.myaircraft.WingSurface,
            "TakeOff Engine Shaft PP": self.myaircraft.mission.TO_PP / 1000,  # PP = Peak Power
            "Climb Cruise Engine Shaft PP": self.myaircraft.mission.Max_PEng
            / 1000,  # PP = Peak Power
            "Battery Mass": self.myaircraft.weight.WBat,
            "TakeOff Battery PP": self.myaircraft.mission.TO_PBat / 1000,  # PP = Peak Power
            "Climb Cruise Battery PP": self.myaircraft.mission.Max_PBat / 1000,  # PP = Peak Power
            "Total Iterations": 0, # needed to be compatible with the old phlygreen code
        }

        self.aircraft_parameters.update(dic_outputs)

    def _process_profiling(self):
        ppn = self.myaircraft.mission.Past_P_n
        iterations = len(ppn)
        evaluations = list(map(len, ppn))
        self.perf_profiling = {
            "Total Iterations": iterations,
            "P_n Evaluations per iteration": evaluations,
            "Past_P_n": ppn,
        }

    def process_data(self):
        """
        Pick between hybrid and combustion data
        processing then write results to memory
        """
        if self.myaircraft.Configuration == "Hybrid":
            self.process_hybrid_data()
            self.get_hybrid_parameters()
        else:
            self.process_fuel_data()
            self.get_fuel_parameters()

        # Extras for performance profiling purposes, comment out if not needed
        # self._process_profiling()

    def results(self):
        """Neatly condenses the relevant information into a dictionary"""
        out = {
            "Inputs": self.inputs,
            "Outputs": self.outputs,
            "Parameters": self.aircraft_parameters,
        }
        return out

    def summary(self):
        """summarize the data that is interesting to plot across flights"""
        out = {}
        out.update(self.inputs)
        del out["Mission Profile"]  # not needed for plotting
        out.update(self.aircraft_parameters)
        out.update(self.outputs_max)
        out.update(self.outputs_min)
        # out["Total Iterations"] = self.perf_profiling["Total Iterations"]

        return out
