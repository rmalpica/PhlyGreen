import PhlyGreen as pg
import sys
import numpy as np
import matplotlib.pyplot as plt
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

class MyProblem(ElementwiseProblem):

    def __init__(self, **kwargs):
        super().__init__(n_var=5,
                         n_obj=1,
                         n_ieq_constr=1,
                         xl=np.array([0,0,0,0,0.04]),
                         xu=np.array([1,1,0.4,0.4,0.08]),
                         elementwise_evaluation=True)

    def _evaluate(self, x, out, *args, **kwargs):
        
        
        ConstraintsInput = {'speed': np.array([280, 70, 59*1.4, 0.3, 0.41, 0.35, 59.]) ,
                            'speedtype': ['KTAS','TAS','TAS','Mach','Mach','Mach','TAS']   ,
                            'beta': np.array([0.97,1.,0.95, 0.9, 0.8, 0.9, None])   ,
                            'altitude': np.array([6000., 100., 2000., 5000, 7600., 6000, 500.]),
                            'load factor': np.array([1., None, 1., 1.1, 1., 1., None]),
                            'DISA': 0, 
                            'kTO': 1.2,
                            'sTO': 1200,
                            'Climb Gradient': 0.041,
                            'ht': 0.5,
                            'M1': 0.3,
                            'M2': 0.4,
                            'DTAcceleration': 180}

        MissionInput = {'Range Mission': 750,
                        'Range Diversion': 100,
                        'Beta start': 0.95,
                        'Payload Weight': (4560),
                        'Crew Weight': (95*3)}

        # MissionStages = {'ConstantRateClimb': {'CB': 0.021, 'Speed': 1.4*59, 'StartAltitude': 2000, 'EndAltitude': 5450},
        #                  'ConstantRateDescent': {'CB': -0.021, 'Speed': 1.4*59, 'StartAltitude': 5450, 'EndAltitude': 2000},
        #                  'ConstantMachCruise': {'Mach': 0.41, 'Altitude': 5450}}

        MissionStages = {'Climb1': {'type': 'ConstantRateClimb', 'input': {'CB': x[4], 'Speed': 1.4*59, 'StartAltitude': 2000, 'EndAltitude': 6000}},
                         'Descent1': {'type': 'ConstantRateDescent', 'input':{'CB': -0.041, 'Speed': 1.4*59, 'StartAltitude': 6000, 'EndAltitude': 2000}},
                         'Cruise': {'type': 'ConstantMachCruise', 'input':{ 'Mach': 0.41, 'Altitude': 6000}}}

        DiversionStages = {'Climb1': {'type': 'ConstantRateClimb', 'input': {'CB': 0.01, 'Speed': 1.4*59, 'StartAltitude': 2000, 'EndAltitude': 3100}},
                         'Descent1': {'type': 'ConstantRateDescent', 'input':{'CB': -0.026, 'Speed': 1.4*59, 'StartAltitude': 3100, 'EndAltitude': 2000}},
                         'Cruise': {'type': 'ConstantMachCruise', 'input':{ 'Mach': 0.3, 'Altitude': 3100}}}

        TechnologyInput = {'Ef': 43.5*10**6,
                           'Ebat': 550 * 3600,
                           'pbat': 1000,
                           'Eta Gas Turbine': 0.3,
                           'Eta Gearbox': 0.96,
                           'Eta Propulsive': 0.9,
                           'Eta Electric Motor 1': 0.96,
                           'Eta Electric Motor 2': 0.96,
                           'Eta Electric Motor': 0.98,
                           'Eta PMAD': 0.99,
                           'Specific Power Powertrain': [3600,7700],
                           'Specific Power PMAD': [2200,2200,2200],
                           'PowertoWeight Battery': 35, 
                           'PowertoWeight Powertrain': [150,33],
                           'PowertoWeight PMAD': 0,
                           # 'Supplied Power Ratio': [[0.4, 0.2],[0.1, 0.05],[0.2, 0.1],[0.4, 0.2],[0.1, 0.05],[0.2, 0.1]]
                            'Supplied Power Ratio': [[x[0], x[1]],[x[2], x[3]],[0., 0.],[x[0], x[1]],[x[2], x[3]],[0., 0.]]
                           }

        WellToTankInput = {'Eta Charge': 1.,
                           'Eta Grid': 0.95,
                           'Eta Extraction': 1.,
                           'Eta Production': 1.,
                           'Eta Transportation': 0.25}

        # print('-----------------------------------------')
        # print('Phi Climb 1: ',x[0])       
        # print('Phi Climb 2: ',x[1])  
        # print('Phi Cruise 1: ',x[2])       
        # print('Phi Cruise 2: ',x[3])   
        # print('Climb Rate: ',x[4])

        myaircraft.Configuration = 'Hybrid'
        myaircraft.HybridType = 'Parallel'
        myaircraft.DesignAircraft(ConstraintsInput,MissionInput,TechnologyInput,MissionStages,DiversionStages,WellToTankInput)
        
        # print('MTOM: ', myaircraft.weight.WTO)
        print('Source Energy: ', myaircraft.welltowake.SourceEnergy/1.e6, ' MJ')
        
        # f1 = weight.WTO[-1]
        # f2 = weight.Wf
        
        f1 = welltowake.SourceEnergy

        # g1 = 2*(x[0]-0.1) * (x[0]-0.9) / 0.18
        # g2 = - 20*(x[0]-0.4) * (x[0]-0.6) / 4.8
        g1 = myaircraft.WingSurface - 80

        out["F"] = f1
        out["G"] = [g1]
        # out["G"] = [g1, g2]




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

aerodynamics.set_quadratic_polar(11,0.8)


n_proccess = 2
pool = multiprocessing.Pool(n_proccess)
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

algorithm = GA(
    pop_size=50,
    sampling=LHS(),
    eliminate_duplicates=True)

res = minimize(problem,
               algorithm,
               termination,
               seed= random.randint(1, 100),
               verbose=True)

print("Best solution found: \nX = %s\nF = %s" % (res.X, res.F))


