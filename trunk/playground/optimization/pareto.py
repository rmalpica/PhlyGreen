import PhlyGreen as pg
import sys
import os
import numpy as np
from pymoo.core.problem import ElementwiseProblem
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.algorithms.soo.nonconvex.nelder import NelderMead
from pymoo.algorithms.soo.nonconvex.pattern import PatternSearch
from pymoo.algorithms.soo.nonconvex.de import DE
from pymoo.algorithms.soo.nonconvex.ga import GA
from pymoo.algorithms.soo.nonconvex.isres import ISRES
from pymoo.operators.sampling.lhs import LHS
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.operators.sampling.rnd import FloatRandomSampling
from pymoo.termination import get_termination
from pymoo.optimize import minimize
from pymoo.termination.ftol import SingleObjectiveSpaceTermination
import multiprocessing
from pymoo.core.problem import StarmapParallelization
from multiprocessing.pool import ThreadPool
import random
from datetime import datetime

class MyProblem(ElementwiseProblem):

    def __init__(self, **kwargs):
        super().__init__(n_var=2,
                         n_obj=4,
                         n_ieq_constr=0,
                         xl=np.array([0.0,500]),
                         xu=np.array([0.6,1000]),
                         elementwise_evaluation=True)

    def _evaluate(self, x, out, *args, **kwargs):
        
        
        ConstraintsInput = {'speed': np.array([0.4, 140, 170, 210, 0.5, 0.35, 104.]) ,
                        'speedtype': ['Mach','KCAS','KCAS','KCAS','Mach','Mach','KCAS']   ,
                        'beta': np.array([0.95,0.985,0.97, 0.9, 0.8, 0.9, None])   ,
                        'altitude': np.array([8000., 100., 6000., 5000, 9500., 6000, 500.]),
                        'load factor': np.array([1., None, 1., 1.1, 1., 1., None]),
                        'DISA': 0, 
                        'kTO': 1.2,
                        'sTO': 950,
                        'OEI Climb Gradient': 0.021,
                        'Rate of Climb': 5,  #5m/s ~= 1000 ft/min, 7.6 ~= 1500 ft/min
                        'ht': 0.5,
                        'M1': 0.3,
                        'M2': 0.4,
                        'DTAcceleration': 180} 

        MissionInput = {'Range Mission': 750,  #nautical miles
                'Range Diversion': 220,  #nautical miles
                'Beta start': 0.985,
                'Payload Weight': 4560,  #Kg
                'Crew Weight': 500}  #Kg

        AerodynamicsInput = {'NumericalPolar': {'type': 'ATR42'}} 

        MissionStages = {'Takeoff': {'Supplied Power Ratio':{'phi': 0.0}},
                     'Climb1': {'type': 'ConstantRateClimb', 'input': {'CB': 0.12, 'Speed': 77, 'StartAltitude': 100, 'EndAltitude': 1500}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }},
                     'Climb2': {'type': 'ConstantRateClimb', 'input': {'CB': 0.06, 'Speed': 110, 'StartAltitude': 1500, 'EndAltitude': 4500}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }},
                     'Climb3': {'type': 'ConstantRateClimb', 'input': {'CB': 0.05, 'Speed': 110, 'StartAltitude': 4500, 'EndAltitude': 8000}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }},
                     'Cruise': {'type': 'ConstantMachCruise', 'input':{ 'Mach': 0.45, 'Altitude': 8000}, 'Supplied Power Ratio':{'phi_start': x[0], 'phi_end': x[0] }},
                     'Descent1': {'type': 'ConstantRateDescent', 'input':{'CB': -0.04, 'Speed': 90, 'StartAltitude': 8000, 'EndAltitude': 200}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }}}
		
        DiversionStages = {'Climb1': {'type': 'ConstantRateClimb', 'input': {'CB': 0.06, 'Speed': 110, 'StartAltitude': 200, 'EndAltitude': 3100}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }},
                     'Cruise': {'type': 'ConstantMachCruise', 'input':{ 'Mach': 0.2, 'Altitude': 3100}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0}},
                     'Descent1': {'type': 'ConstantRateDescent', 'input':{'CB': -0.04, 'Speed': 90, 'StartAltitude': 3100, 'EndAltitude': 200}, 'Supplied Power Ratio':{'phi_start': 0.0, 'phi_end':0.0 }}}
        
        EnergyInput = {'Ef': 43.5*10**6,
                   'Ebat': x[1] * 3600,
                   'pbat': 1000,
                   'Eta Gas Turbine Model': 'constant',
                   'Eta Gas Turbine': 0.22,
                   'Eta Gearbox': 0.96,
                   'Eta Propulsive Model': 'constant',
                   'Eta Propulsive': 0.75,
                   'Eta Electric Motor 1': 0.96,    #for serial config
                   'Eta Electric Motor 2': 0.96,    #for serial config
                   'Eta Electric Motor': 0.98,      #for parallel config
                   'Eta PMAD': 0.99,
                   'Specific Power Powertrain': [3900,7700],
                   'Specific Power PMAD': [2200,2200,2200],
                   'PowertoWeight Battery': 35, 
                   'PowertoWeight Powertrain': [150,33],
                   'PowertoWeight PMAD': 0
                   }
                   
        WellToTankInput = {'Eta Charge': 1.,
                           'Eta Grid': 0.95,
                           'Eta Extraction': 1.,
                           'Eta Production': 1.,
                           'Eta Transportation': 0.25}

        # print('-----------------------------------------')
        # print('Phi Cruise: ',x[0])  
        # print('ebat: ',x[1])       


        myaircraft.Configuration = 'Hybrid'
        myaircraft.HybridType = 'Parallel'
        myaircraft.DesignAircraft(AerodynamicsInput,ConstraintsInput,MissionInput,EnergyInput,MissionStages,DiversionStages,WellToTankInput=WellToTankInput,PrintOutput=False)
        
        # print('MTOM: ', myaircraft.weight.WTO)
        #print('Source Energy: ', myaircraft.welltowake.SourceEnergy/1.e6, ' MJ')
        
        f1 = myaircraft.weight.WTO
        f2 = myaircraft.weight.Wf
        f3 = myaircraft.welltowake.SourceEnergy * 1e-6  # MJ
        f4 = (-6e-2*43.5*myaircraft.weight.Wf) + myaircraft.weight.Wf*3.14  #WtW CO2

        
        #g1 = myaircraft.WingSurface - 80

        out["F"] = [f1,f2,f3,f4]
        #out["G"] = [g1]
        


if __name__ == '__main__':

    powertrain = pg.Systems.Powertrain.Powertrain(None)
    structures = pg.Systems.Structures.Structures(None)
    aerodynamics = pg.Systems.Aerodynamics.Aerodynamics(None)
    performance = pg.Performance.Performance(None)
    mission = pg.Mission.Mission(None)
    weight = pg.Weight.Weight(None)
    constraint = pg.Constraint.Constraint(None)
    welltowake = pg.WellToWake.WellToWake(None)


    # # Creating mediator and associating with subsystems
    myaircraft = pg.Aircraft(powertrain, structures, aerodynamics, performance, mission, weight, constraint, welltowake)



    # # Associating subsystems with the mediator
    powertrain.aircraft = myaircraft
    structures.aircraft = myaircraft
    aerodynamics.aircraft = myaircraft
    mission.aircraft = myaircraft
    performance.aircraft = myaircraft
    weight.aircraft = myaircraft
    constraint.aircraft = myaircraft
    welltowake.aircraft = myaircraft


    num_cores = int(os.cpu_count())
    print('number of cores detected : ',num_cores)

    #num_cores = 2
    pool = multiprocessing.Pool(num_cores)
    runner = StarmapParallelization(pool.starmap)

    problem = MyProblem(elementwise_runner=runner)

    termination = get_termination("n_iter", 20)
    # termination = SingleObjectiveSpaceTermination(tol=1e6, n_skip=3)
    # algorithm = ISRES()


    # algorithm = DE(
    #     pop_size=50,
    #     sampling=LHS(),
    #     variant="DE/rand/1/bin",
    #     CR=0.9,
    #     dither="vector",
    #     jitter=False
    # )

    #algorithm = GA(
    #    pop_size=50,
    #    sampling=LHS(),
    #    eliminate_duplicates=True)
    
    algorithm = NSGA2(
        pop_size=40,
        n_offsprings=10,
        sampling=FloatRandomSampling(),
        crossover=SBX(prob=0.9, eta=15),
        mutation=PM(eta=20),
        eliminate_duplicates=True
    )

    res = minimize(problem,
                   algorithm,
                   termination,
                   seed= random.randint(1, 100),
                   verbose=True)

    # Get the design variables and objective values
    X = res.X
    F = res.F

    np.savetxt('pareto_front.txt', np.column_stack((X, F)), 
           header='Phi, eBat, TOW, FW, Source Energy, WtW_CO2', 
           fmt='%1.8e', delimiter=' ')




