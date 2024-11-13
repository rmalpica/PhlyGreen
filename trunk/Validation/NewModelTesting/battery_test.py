import math
import numbers
import numpy as np
from scipy.optimize import brentq
import scipy.integrate as integrate
import os
import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd

cellparameters={
                'Polarization Ctt': 0.0119,     #in Volts over amp hour
                'Exp Amplitude': 0.2711,        #in volts
                'Exp Time constant': 152.13,    #in Ah^-1 
                'Voltage Constant':3.21,        #in volts
                'Cell Capacity': 1.3,            #in Ah
                'Cell C rating': 4,             #dimensionless
                'Internal Resistance': 0.03,    #in ohms
                'Cell Voltage Min': 2.5,        #in volts
                'Cell Voltage Max': 4.2,        #in volts
                'Cell Voltage Nominal': 3.00,   #in volts
                'Cell Mass': 0.005,              #in kg
                'Cell Radius': 0.006,           #in m
                'Cell Height': 0.065,           #in m
            }

def plotData(data, X , Y, title, foldername):
    x_data = data[X]
    y_data = data[Y]
    # Create a plot using Seaborn
    sns.lineplot(x=x_data, y=y_data)

    # Add labels and title
    plt.xlabel(X)
    plt.ylabel(Y)
    plt.title(title)

    # Save the plot as a PDF
    filename = os.path.join(foldername, title+".pdf") #create file inside the output directory
    plt.savefig(filename)
    print('||>- Saved \'',title,'\' to',filename)
    plt.close()  # Close the plot

class Battery:
    def __init__(self):
        pass

# Set inputs from cell model chosen
    def SetInput(self):
        self.cell_model = cellparameters
        self.cell_capacity = self.cell_model['Cell Capacity']
        self.cell_rate = self.cell_model['Cell C rating']
        self.cell_resistance = self.cell_model['Internal Resistance']
        self.cell_current = self.cell_rate * self.cell_capacity
        self.cell_Vmax = self.cell_model['Cell Voltage Max']
        self.cell_Vmin = self.cell_model['Cell Voltage Min']
        self.cell_Vnom = self.cell_model['Cell Voltage Nominal']

        self.cell_polarization_constant = self.cell_model['Polarization Ctt']/3600
        self.cell_exponential_amplitude = self.cell_model['Exp Amplitude']
        self.cell_exponential_time_constant = self.cell_model['Exp Time constant']/3600
        self.cell_voltage_constant = self.cell_model['Voltage Constant']


        if not (self.cell_Vmax > self.cell_Vnom and self.cell_Vnom > self.cell_Vmin):
            raise ValueError("Illegal cell voltages: Vmax must be greater than Vnom which must be greater than Vmin")

        self.cell_Vmax = self.cell_exponential_amplitude + self.cell_voltage_constant
        self.cell_charge = 3600*self.cell_capacity #convert the capacity from Ah to Coulomb to keep everything SI
        self.cell_energy = self.cell_charge*self.cell_Vnom # cell capacity in joules

#determine battery configuration
    #must receive the number of cells in parallel
    def Configure(self, parallel_cells, series_cells):
        #print(parallel_cells)
        self.P_number=parallel_cells
        self.S_number=series_cells
        self.cells_total = self.P_number * self.S_number

        self.pack_charge = self.P_number * self.cell_charge
        self.pack_energy = self.cells_total * self.cell_energy
        self.pack_resistance = self.cell_resistance * self.S_number / self.P_number

        # empirical constants scaled for the whole pack:
        self.pack_polarization_constant     = self.cell_polarization_constant * self.S_number / self.P_number
        self.pack_exponential_amplitude     = self.cell_exponential_amplitude * self.S_number
        self.pack_exponential_time_constant = self.cell_exponential_time_constant * self.P_number
        self.pack_voltage_constant          = self.cell_voltage_constant * self.S_number

        # voltages:
        self.pack_Vmax = self.cell_Vmax * self.S_number
        self.pack_Vmin = self.cell_Vmin * self.S_number
        self.pack_Vnom = self.cell_Vnom * self.S_number

        # peak current that can be delivered safely from the pack
        self.pack_current = self.cell_current * self.P_number 

        #max power that can be delivered at 100% SOC and peak current:
        self.pack_power_max = self.pack_current * self.Nrg_n_Curr_2_Volt(0,self.pack_current)  

    def Nrg_n_Curr_2_Volt(self, it, i):
        '''Converts the current being drawn + the current
        spent so far into an output voltage'''
        E0 = self.pack_voltage_constant
        R  = self.pack_resistance
        A  = self.pack_exponential_amplitude
        B  = self.pack_exponential_time_constant
        K  = self.pack_polarization_constant
        Q  = self.pack_charge

        V = E0 -i*K*(Q/(Q-it)) -it*K*(Q/(Q-it)) +A*np.exp(-B * it) -i*R
        return V

    def Power_2_V_A(self, it, P):
        '''Receives: 
              it - charge spent from the battery over time, the integral of the current
              P  - power demanded from the battery
           Returns:
              U_out - voltage at the battery terminals
              I_out - current output from the battery
        '''

        if P == 0: #skips all the math if power is zero
            I_out = 0
            U_out = self.Nrg_n_Curr_2_Volt( it, I_out)

        else:
            ''' V = E0 - i*R - i*K*(Q/(Q-it)) - it*K*(Q/(Q-it)) + A*exp(-B * it)
                V = E0 - I*R - I*Qr - it*Qr + ee <- with substitutions to make shorter
                P = V*I = E0*I - I^2*R - I^2*Qr - I*it*Qr + I*ee 
                P = I^2 *(-R-Qr) + I *(E0+ee-it*Qr)
                quadratic solve: 
                a*I^2 + b*I - P = 0
            '''
            E0 = self.pack_voltage_constant
            R  = self.pack_resistance
            A  = self.pack_exponential_amplitude
            B  = self.pack_exponential_time_constant
            K  = self.pack_polarization_constant
            Q  = self.pack_charge
            Qr = K*Q/(Q-it)
            ee = A*np.exp(-B * it)
            a = (-R-Qr)
            b = (E0+ee-it*Qr)
            c = -P
            try:
                I_out = (-b+math.sqrt(b**2-4*a*c))/(2*a) # just the quadratic formula
                U_out = self.Nrg_n_Curr_2_Volt(it, I_out)
            except Exception as err:
                print(err)
                I_out = None
                U_out = None
        return U_out, I_out


#####################################################################
class Mission:
    def __init__(self, mybattery):
        self.battery = mybattery

    def modelP(self,t,y):
        '''constant power'''
        #battery state of charge
        SOC = 1-y[0]/self.battery.pack_charge

        PElectric = 6
        #current drawn to meet power demands
        BatVolt, BatCurr  = self.battery.Power_2_V_A(y[0], PElectric) #convert output power to volts and amps
        BatVolt = max(0,BatVolt)
        self.outBatVolt = BatVolt
        self.outBatCurr = BatCurr
        self.outBatPwr = PElectric
        self.outSOC = SOC
        return [BatCurr]

    def modelC(self,t,y):
        '''constant current'''
        #battery state of charge
        SOC = 1-y[0]/self.battery.pack_charge
        BatCurr = 0.3
        #current drawn to meet power demands
        
        BatVolt  = self.battery.Nrg_n_Curr_2_Volt(y[0], BatCurr) #convert output power to volts and amps
        PElectric = BatVolt * BatCurr
        #self.outBatVoltOC = BatVoltOC
        self.outBatVolt = BatVolt
        self.outBatCurr = BatCurr
        self.outBatPwr = PElectric
        self.outSOC = SOC

        return [BatCurr]

    def evaluate(self,P_n,S_n):

        self.battery.Configure(P_n,S_n)
        self.integral_solution = []
        minutes = 350
        times = range(0,minutes*60,minutes)

        
        self.plottingVarsC=[]
        rtol = 1e-5
        method= 'BDF'
        y0 = [0] #initial spent charge
        for i in range(len(times)-1):
            sol = integrate.solve_ivp(self.modelC,[times[i], times[i+1]], y0, method=method, rtol=rtol)
            self.integral_solution.append(sol)
            for k in range(len(sol.t)):
                yy0 = [sol.y[0][k]]
                self.modelC(sol.t[k],yy0)
                self.plottingVarsC.append([sol.t[k],
                                            self.outSOC,
                                            self.outBatVolt,
                                            self.outBatCurr,
                                            self.outBatPwr])
            y0 = [sol.y[0][-1]]
        
        #########
        self.plottingVarsP=[]
        rtol = 1e-5
        method= 'BDF'
        y0 = [0] #initial spent charge
        for i in range(len(times)-1):
            sol = integrate.solve_ivp(self.modelP,[times[i], times[i+1]], y0, method=method, rtol=rtol)
            self.integral_solution.append(sol)
            for k in range(len(sol.t)):
                yy0 = [sol.y[0][k]]
                self.modelP(sol.t[k],yy0)
                self.plottingVarsP.append([sol.t[k],
                                            self.outSOC,
                                            self.outBatVolt,
                                            self.outBatCurr,
                                            self.outBatPwr])
            y0 = [sol.y[0][-1]]


##############################################################

mybat = Battery()
mybat.SetInput()
mymiss = Mission(mybat)

mymiss.evaluate(1,3)
aC=mymiss.plottingVarsC
aP=mymiss.plottingVarsP
#for k in range(len(aC)):
    #print(f'{aC[k][0]}|{aC[k][1]}|{aC[k][2]}|{aC[k][3]}|{aC[k][4]}')

aC=np.array(aC)
aP=np.array(aP)
bC = {'time': aC[:,0],
     'soc':aC[:,1],
     'voltage':aC[:,2],
     'current': aC[:,3],
     'power': aC[:,4]
    }
bP = {'time': aP[:,0],
     'soc':aP[:,1],
     'voltage':aP[:,2],
     'current': aP[:,3],
     'power': aP[:,4]
    }

foldername = 'testingoutputs'
plotData(bC, 'time' , 'soc' , 'CC t v soc', foldername)
plotData(bC, 'time' , 'voltage' , 'CC t v volt', foldername)
plotData(bC, 'time' , 'current' , 'CC t v curr', foldername)
plotData(bC, 'time' , 'power' , 'CC t v pwr', foldername)

plotData(bP, 'time' , 'soc' , 'PP t v soc', foldername)
plotData(bP, 'time' , 'voltage' , 'PP t v volt', foldername)
plotData(bP, 'time' , 'current' , 'PP t v curr', foldername)
plotData(bP, 'time' , 'power' , 'PP t v pwr', foldername)

'''
data = {'time':[],
        'voltage':[],
        'it':[]}

for t in range(0,300*60):
    i=0.2*1.3
    data['time'].append(t)
    data['it'].append(i*t)
    v=mybat.Nrg_n_Curr_2_Volt(data['it'][-1],i)
    v = max(0,v)
    data['voltage'].append(v)
    print(data['voltage'][-1])

foldername = 'testingoutputs'
plotData(data, 'time' , 'voltage' , 'linear t v volt', foldername)
plotData(data, 'time' , 'it' , 'linear t v it', foldername)'''