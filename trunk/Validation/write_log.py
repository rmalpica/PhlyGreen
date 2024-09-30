import sys
import json
def printLog(myaircraft,filename):

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

def failLog(filename):
    with open(filename, "w") as file:
        sys.stdout = file #redirecting stdout to file to avoid recreating the print function for files
        print('fail')
        sys.stdout = sys.__stdout__

def printJSON(dicts,jsonfn):
    with open(jsonfn, "w") as json_file:
        json.dump(dicts, json_file, indent=4)

def failJSON(jsonfn):
    with open(jsonfn, "w") as json_file:
        json.dump(['fail'], json_file, indent=4)  # indent for readable formatting