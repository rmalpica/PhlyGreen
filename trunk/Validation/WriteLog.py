import sys
import json
def printLog(myaircraft,filename):
    pass
    return
    with open(filename, "w") as file:
        sys.stdout = file #redirecting stdout to file to avoid recreating the print function for files

        if myaircraft.Configuration == 'Traditional':

            print('Fuel mass (trip + altn) [Kg]: ', myaircraft.weight.Wf)
            print('Block Fuel mass [Kg]:         ', myaircraft.weight.Wf + myaircraft.weight.final_reserve)
            print('Structure [Kg]:               ', myaircraft.weight.WStructure)
            print('Powertrain mass [Kg]:         ',myaircraft.weight.WPT)
            print('Empty Weight [Kg]:            ', myaircraft.weight.WPT + myaircraft.weight.WStructure + myaircraft.weight.WCrew)
            print('Zero Fuel Weight [Kg]:        ', myaircraft.weight.WPT + myaircraft.weight.WStructure + myaircraft.weight.WCrew + myaircraft.weight.WPayload)
            print('----------------------------------------')
            print('Takeoff Weight: ', myaircraft.weight.WTO)
            if myaircraft.WellToTankInput is not None:
                print('Source Energy: ', myaircraft.welltowake.SourceEnergy/1.e6,' MJ')
                print('Psi: ', myaircraft.welltowake.Psi)
            print('Wing Surface: ', myaircraft.WingSurface, ' m^2')
            print('TakeOff engine shaft peak power [kW]:      ', myaircraft.mission.TO_PP/1000.)
            print('Climb/cruise engine shaft peak power [kW]: ', myaircraft.mission.Max_PEng/1000.)

            print('-------------Sizing Phase--------------')
            print('Sizing phase for thermal powertrain ', 'Climb/Cruise peak power' if myaircraft.mission.Max_PEng > myaircraft.mission.TO_PP else 'Takeoff peak power'  )

        else:
            print('Fuel mass (trip + altn) [Kg]: ', myaircraft.weight.Wf)
            print('Block Fuel mass [Kg]:         ', myaircraft.weight.Wf + myaircraft.weight.final_reserve)
            print('Battery mass [Kg]:            ', myaircraft.weight.WBat)
            print('Structure [Kg]:               ', myaircraft.weight.WStructure)
            print('Powertrain mass [Kg]:         ',myaircraft.weight.WPT)
            print('Empty Weight [Kg]:            ', myaircraft.weight.WPT + myaircraft.weight.WStructure + myaircraft.weight.WCrew + myaircraft.weight.WBat)
            print('Zero Fuel Weight [Kg]:        ', myaircraft.weight.WPT + myaircraft.weight.WStructure + myaircraft.weight.WCrew + myaircraft.weight.WBat + myaircraft.weight.WPayload)
            print('----------------------------------------')
            print('Takeoff Weight: ', myaircraft.weight.WTO)
            if myaircraft.WellToTankInput is not None:
                print('Source Energy: ', myaircraft.welltowake.SourceEnergy/1.e6,' MJ')
                print('Psi: ', myaircraft.welltowake.Psi)
            print('Wing Surface: ', myaircraft.WingSurface, ' m^2')
            print('TakeOff engine shaft peak power [kW]:      ', myaircraft.mission.TO_PP/1000.)
            print('Climb/cruise engine shaft peak power [kW]: ', myaircraft.mission.Max_PEng/1000.)
            print('TakeOff battery peak power [kW]:           ', myaircraft.mission.TO_PBat/1000.)
            print('Climb/cruise battery peak power [kW]:      ', myaircraft.mission.Max_PBat/1000.)
            print()
            print('-------------Battery Specs-------------')
            print('Battery Pack Energy [kWh]:           ', myaircraft.battery.pack_energy/3600000)
            print('Battery Pack Max Power [kW]:         ', myaircraft.battery.pack_power_max/1000)
            print('Battery Pack Specific Energy [Wh/kg]:',(myaircraft.battery.pack_energy/3600)/myaircraft.weight.WBat)
            print('Battery Pack Specific Power [kW/kg]: ',(myaircraft.battery.pack_power_max/1000)/myaircraft.weight.WBat)
            print()
            print('-------------Sizing Phase--------------')

            #print('Sizing phase for battery: ', 'Cruise energy' if myaircraft.battery.energy_or_power == 'energy' else 'Cruise peak power' if myaircraft.weight.TOPwr_or_CruisePwr == 'cruise' else 'Takeoff peak power'  ) #uncomment when i add a mechanism for seeing which constraint drove what thing in the battery sizing
            print('Sizing phase for thermal powertrain: ', 'Climb/Cruise peak power' if myaircraft.mission.Max_PEng > myaircraft.mission.TO_PP else 'Takeoff peak power'  )
            # print('Sizing phase for electric powertrain ', 'Climb/Cruise peak power' if myaircraft.mission.Max_PBat > myaircraft.mission.TO_PBat else 'Takeoff peak power'  )
        print()
        print("-------------------------------")
        print("Quick reference for comparison:")
        print()

        print('Mission Range  [km]: ', myaircraft.mission.profile.MissionRange/1000)
        print('Total Payload  [kg]: ', myaircraft.weight.WPayload + myaircraft.weight.WCrew)
        print('Takeoff Weight [kg]: ', myaircraft.weight.WTO)
        if not (myaircraft.Configuration == 'Traditional'):
            print()
            print('-------------Battery Pack Specs-------------')
            print('Specific Energy [Wh/kg]: ',(myaircraft.battery.pack_energy/3600)/myaircraft.weight.WBat)
            print('Specific Power  [kW/kg]: ',(myaircraft.battery.pack_power_max/1000)/myaircraft.weight.WBat)

    sys.stdout = sys.__stdout__

def parameters(myaircraft):
    outputs={ #organize all the outputs that are always common to all the aircraft
        'Fuel Mass':myaircraft.weight.Wf,
        'Block Fuel Mass':myaircraft.weight.Wf + myaircraft.weight.final_reserve,
        'Structure Mass': myaircraft.weight.WStructure,
        'Powertrain Mass': myaircraft.weight.WPT,
        'Empty Weight': myaircraft.weight.WPT + myaircraft.weight.WStructure + myaircraft.weight.WCrew,
        'Zero Fuel Weight': myaircraft.weight.WPT + myaircraft.weight.WStructure + myaircraft.weight.WCrew + myaircraft.weight.WPayload,
        'Takeoff Weight':myaircraft.weight.WTO,
        'Wing Surface':myaircraft.WingSurface,
        'TakeOff Engine Shaft PP': myaircraft.mission.TO_PP/1000, # PP = Peak Power
        'Climb Cruise Engine Shaft PP':myaircraft.mission.Max_PEng/1000} # PP = Peak Power

    if myaircraft.Configuration == 'Hybrid': #write outputs for when a battery is involved
        electricOutputs={
            'Battery Mass': myaircraft.weight.WBat,
            'Empty Weight':myaircraft.weight.WPT + myaircraft.weight.WStructure + myaircraft.weight.WCrew + myaircraft.weight.WBat,
            'Zero Fuel Weight':myaircraft.weight.WPT + myaircraft.weight.WStructure + myaircraft.weight.WCrew + myaircraft.weight.WBat + myaircraft.weight.WPayload,
            'Takeoff Weight':myaircraft.weight.WTO,
            'TakeOff Battery PP': myaircraft.mission.TO_PBat/1000, # PP = Peak Power
            'Climb Cruise Battery PP':myaircraft.mission.Max_PBat/1000, # PP = Peak Power
            'Battery Pack Energy': myaircraft.battery.pack_energy/3600000,
            'Battery Pack Max Power': myaircraft.battery.pack_power_max/1000,
            'Battery Pack Specific Energy':(myaircraft.battery.pack_energy/3600)/myaircraft.weight.WBat,
            'Battery Pack Specific Power':(myaircraft.battery.pack_power_max/1000)/myaircraft.weight.WBat,
            'Battery P number': myaircraft.battery.P_number,
            'Battery S number': myaircraft.battery.S_number,
            'Battery Pack Charge': myaircraft.battery.pack_charge,
            'Battery Pack Max Current': myaircraft.battery.pack_current,
            'Battery Pack Resistance': myaircraft.battery.pack_resistance}

        outputs.update(electricOutputs)

    if myaircraft.WellToTankInput is not None:
        welltotank={'Source Energy': myaircraft.welltowake.SourceEnergy/1.e6,
                    'Psi':myaircraft.welltowake.Psi}
        outputs.update(welltotank)
    return outputs

def failLog(filename):
    with open(filename, "w") as file:
        sys.stdout = file #redirecting stdout to file to avoid recreating the print function for files
        print('fail')
        sys.stdout = sys.__stdout__

def printJSON(dicts,jsonfn):
    with open(jsonfn, "w") as json_file:
        json.dump(dicts, json_file, indent=4)
