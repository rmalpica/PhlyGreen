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

	grid_n = 4  #set number of grid points
	phi_min = 0.0
	phi_max = 0.6

	parameters = []
	samples = []

	#e_bat = [500,600,700,800]
	e_bat = [600,800,1000]
	phi_start = np.linspace(phi_min, phi_max, num = grid_n)
	phi_end = np.linspace(phi_min, phi_max,num = grid_n)


	for e in e_bat:
		for phi1 in phi_start:
			for phi2 in phi_end:
				a = [e,phi1,phi2]
				parameters.append(a)


	#num_cores = int(os.getenv('SLURM_CPUS_PER_TASK'))
	num_cores = int(os.cpu_count())
	print('number of cores detected : ',num_cores)
	pool = mp.Pool(num_cores)

	# Parallel starting

	results = pool.map(model_solver, [parameter for parameter in parameters])

	# Parallel closing

	pool.close()

	
	print(results) 
	
	#dump results on file

	file = open('samples_'+datetime.now().strftime('%Y-%m-%d_%H-%M-%S')+'.xml','wb')
	pickle.dump(results,file)
	file.close()

	len_onegrid = int(len(results)/len(e_bat))
	for k in range(len(e_bat)):

		samples = results[k*len_onegrid : (k+1)*(len_onegrid)]

		WTO = []    
		SourceEnergy = []
		Psi = []
		Phi1 = []
		Phi2 = []
		WF = []
		WBat = []
		WPT = []
		WS = []
	

		for i in range(len(samples)):
			ebat = samples[0][0]
			Phi1 = np.append(Phi1,samples[i][1])
			Phi2 = np.append(Phi2,samples[i][2])
			WTO = np.append(WTO,samples[i][3])
			WF = np.append(WF,samples[i][8])
			WS = np.append(WS,samples[i][6])
			WBat = np.append(WBat,samples[i][7])
			WPT = np.append(WPT,samples[i][9])
			SourceEnergy = np.append(SourceEnergy,samples[i][4])
			Psi = np.append(Psi,samples[i][5])
	
		# plt.scatter(Phi2[:10000],WTO[:10000],c=SourceEnergy[:10000])
		# plt.colorbar()
		# plt.show()
	
		# xi = np.linspace(Phi1.min(), Phi1.max(), 1000)
		# yi = np.linspace(Phi2.min(), Phi2.max(), 1000)
		# zi = griddata((Phi1, Phi2), SourceEnergy, (xi[None,:], yi[:,None]), method='cubic')
	
		# CS = plt.contourf(xi, yi, zi, 150, cmap=plt.cm.rainbow)
		# plt.colorbar()  
		# plt.xlabel('Phi Start')
		# plt.ylabel('Phi End')
		# plt.show()
	
		# division = np.empty([100,100,3])
		i = np.linspace(phi_min, phi_max,num=grid_n)
		j = np.linspace(phi_min, phi_max,num=grid_n)
		EN = np.reshape(SourceEnergy,[grid_n,grid_n])
		P1 = np.reshape(Phi1, [grid_n,grid_n])
		W = np.reshape(WTO,[grid_n,grid_n])
		WF = np.reshape(WF,[grid_n,grid_n])
		WBat = np.reshape(WBat,[grid_n,grid_n])
		WPT = np.reshape(WPT,[grid_n,grid_n])
		WS = np.reshape(WS, [grid_n,grid_n])
		ri, ci = EN.argmin()//EN.shape[1], EN.argmin()%EN.shape[1]
		ro, co = W.argmin()//W.shape[1], W.argmin()%W.shape[1]
		ru, cu = WF.argmin()//WF.shape[1], WF.argmin()%WF.shape[1]
	
	
		print(i[ri],j[ci],P1[ri,ci],EN[ri,ci],W[ri,ci],WF[ri,ci],WBat[ri,ci],WPT[ri,ci],WS[ri,ci])
		print(i[ro],j[co],P1[ri,ci],EN[ro,co],W[ro,co],WF[ro,co],WBat[ro,co],WPT[ro,co],WS[ro,co])
		print(i[ru],j[cu],P1[ri,ci],EN[ru,cu],W[ru,cu],WF[ru,cu],WBat[ru,cu],WPT[ru,cu],WS[ru,cu])
	
	
	
	
		plt.figure(figsize=(5,4))
		plt.tight_layout()
		CS = plt.contourf(i, j, EN.T/1e9, 32, cmap=plt.cm.plasma)
		CR = plt.contour(i,j,W.T,[22000,30000,38000,46000,54000],colors='w')
		# CWS = plt.contour(i,j,WS.T,[80,90,110,130,150],colors='turquoise',labcex=12)
		# plt.clabel(CR,manual=[(0.03,0.08),(0.05,0.15),(0.09,0.2),(0.1,0.35),(0.28,0.28),(0.35,0.3)])
		plt.clabel(CR)
		# plt.clabel(CWS)
		plt.plot(i[ri],j[ci],marker='s', markersize = 12, markerfacecolor = 'red', markeredgecolor = 'black')
		plt.plot(i[ru],j[cu],marker='o', markersize = 9, markerfacecolor = 'green', markeredgecolor = 'black')
		plt.plot(i[ro],j[co],marker='v', markersize = 8, markerfacecolor = 'orange', markeredgecolor = 'black')
	
		bar = plt.colorbar(CS)
		bar.ax.yaxis.set_major_formatter(FormatStrFormatter('%0.1f'))
		# CS.set_clim(vmin=1.5e11, vmax=2.6e11)
		bar.set_label('Source Energy [GJ]')  
		ax = plt.gca()
		ax.set_xlabel(r'$\varphi_{cr,s}$ [-]', fontsize=12)
		ax.set_ylabel(r'$\varphi_{cr,e}$ [-]', fontsize=12)
		plt.title(r'$e_{bat}$' + ' = '+str(int(ebat))+' Wh/kg')
		plt.savefig('Source_e'+str(int(ebat))+'.png', dpi=600, format='png',bbox_inches="tight")
		#plt.show()
	
	
	
		# CS = plt.contourf(i, j, W.T, 32, cmap=plt.cm.rainbow)
		# # # CR = plt.contour(i,j,EN.T)
		# plt.clabel(CR)
		# bar = plt.colorbar(CS)
		# bar.set_label('Weight', rotation=270)  
		# plt.xlabel('Phi Start')
		# plt.ylabel('Phi End')
		# plt.show()
	
		# CS = plt.contourf(i, j, WBat.T, 15, cmap=plt.cm.rainbow)
		# # CR = plt.contour(i,j,EN.T)
		# plt.clabel(CR)
		# bar = plt.colorbar(CS)
		# bar.set_label('Battery Weight', rotation=270)  
		# plt.xlabel('Phi Start')
		# plt.ylabel('Phi End')
		# plt.show()
	
		# CS = plt.contourf(i, j, WPT.T, 15, cmap=plt.cm.rainbow)
		# # # CR = plt.contour(i,j,EN.T)
		# plt.clabel(CR)
		# bar = plt.colorbar(CS)
		# bar.set_label('Powertrain Weight', rotation=270)  
		# plt.xlabel('Phi Start')
		# plt.ylabel('Phi End')
		# plt.show()
	
		# CS = plt.contourf(i, j, WS.T, 15, cmap=plt.cm.rainbow)
		# CR = plt.contour(i,j,EN.T)
		# plt.clabel(CR)
		# bar = plt.colorbar(CS)
		# bar.set_label('Wing Surface', rotation=270)  
		# plt.xlabel('Phi Start')
		# plt.ylabel('Phi End')
		# plt.show()
	
	
	