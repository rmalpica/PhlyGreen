import numpy as np
from model_solver import model_solver 
import pickle
import os
import multiprocessing as mp
import matplotlib.pyplot as plt
from scipy.interpolate import griddata
#import scienceplots
from matplotlib.ticker import FormatStrFormatter
from datetime import datetime

if __name__ == '__main__':

	case_name = ['conventional','fteu2021+pem+cc','ft eu2021+smr+cc','fteu2050+pem+cc', 'ftWindPower+pem+cc', 'ftNuclear+cc' ]
	etaFuel = [0.89, 0.17, 0.44, 0.37, 0.32, 0.46]
	wttCO2 = [8.20e-3, 2.0e-1, 5.31e-2, -3.62e-2, -6.83e-2, -6.72e-2]
	gridCO2 = [0, 9.36e-2, 9.36e-2, 1.08e-2, 0, 5.34e-4]

	grid_n = 16  #set number of grid points
	phi_min = 0.0
	phi_max = 0.6

	phi = np.linspace(phi_min, phi_max, num = grid_n)
	ebat = 1000

	allResults = []

	for i in range(len(case_name)):
		parameters = []
		print('case: '+case_name[i])
		for phiCRZ in phi:
				a = [phiCRZ, etaFuel[i], wttCO2[i], gridCO2[i]]
				parameters.append(a)


		#num_cores = int(os.getenv('SLURM_CPUS_PER_TASK'))
		num_cores = int(os.cpu_count())
		print('number of cores detected : ',num_cores)
		pool = mp.Pool(num_cores)

		# Parallel starting

		results = pool.map(model_solver, [parameter for parameter in parameters])

		# Parallel closing

		pool.close()
		pool.join()

	
		print(results) 
		allResults.append(results)
	
	#dump results on file
	for i in range(len(case_name)):
		np.savetxt('samples_'+case_name[i]+'.txt', allResults[i], 
          header='Phi, etaFuel, wttCO2, gridCO2, TOW, sourceE, Psi, Wingsurf, Wbat, Wfuel, Wpt, Wthermal, Welec, WtWCO2', 
          fmt='%1.8e', delimiter=' ')

	
	