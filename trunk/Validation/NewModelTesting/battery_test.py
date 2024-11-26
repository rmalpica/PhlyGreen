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
                'Polarization Ctt': 0.0033,     #in Volts over amp hour
                'Exp Amplitude': 0.2711,        #in volts
                'Exp Time constant': 152.13,    #in Ah^-1 
                'Voltage Constant':13.338,        #in volts
                'Cell Capacity': 42.82,            #in Ah
                'Cell C rating': 4,             #dimensionless
                'Internal Resistance': 0.0126,    #in ohms
                'Arrhenius a': 1225,
                'Arrhenius b': 2836,
                'Charge Slope': 0.1766/3600,
                'Voltage Slope': 0.00004918,
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

        self.cell_polarization_constant = self.cell_model['Polarization Ctt']
        self.cell_exponential_amplitude = self.cell_model['Exp Amplitude']
        self.cell_exponential_time_constant = self.cell_model['Exp Time constant']
        self.cell_voltage_constant = self.cell_model['Voltage Constant']
        self.arrh_a = self.cell_model['Arrhenius a']
        self.arrh_b = self.cell_model['Arrhenius b']
        self.DeltaV = self.cell_model['Charge Slope']
        self.DeltaQ = self.cell_model['Voltage Slope']

        if not (self.cell_Vmax > self.cell_Vnom and self.cell_Vnom > self.cell_Vmin):
            raise ValueError("Illegal cell voltages: Vmax must be greater than Vnom which must be greater than Vmin")

        self.cell_Vmax = self.cell_exponential_amplitude + self.cell_voltage_constant
        self.cell_charge = self.cell_capacity #convert the capacity from Ah to Coulomb to keep everything SI
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
        #self.pack_power_max = self.pack_current * self.outPuts(0,self.pack_current)  

    def outPuts(self, T,it,i):
        '''Converts the current being drawn + the current
        spent so far into an output voltage'''

        E0,R,A,B,K,Q,Cv = self.ConfigTemp(T)

        V = E0 -i*K*(Q/(Q-it)) -it*K*(Q/(Q-it)) +A*np.exp(-B * it) -i*R -it*Cv
        return V

    def Power_2_V_A(self, it, P, T):
        '''Receives: 
              it - charge spent from the battery over time, the integral of the current
              P  - power demanded from the battery
              T  - pack temperature
           Returns:
              U_out - voltage at the battery terminals
              I_out - current output from the battery
        '''

        if P == 0: #skips all the math if power is zero
            I_out = 0
            U_out = self.outPuts(T,it, I_out)

        else:
            ''' V = E0 - i*R - i*K*(Q/(Q-it)) - it*K*(Q/(Q-it)) + A*exp(-B * it) - C*it
                V = E0 - I*R - I*Qr - it*Qr + ee <- with substitutions to make shorter
                P = V*I = E0*I - I^2*R - I^2*Qr - I*it*Qr + I*ee 
                P = I^2 *(-R-Qr) + I *(E0+ee-it*Qr)
                quadratic solve: 
                a*I^2 + b*I - P = 0
            '''
            E0,R,A,B,K,Q,Cv = self.ConfigTemp(T)

            Qr = K*Q/(Q-it)
            ee = A*np.exp(-B * it)
            a = (-R-Qr)
            b = (E0+ee-it*Qr-it*Cv)
            c = -P
            try:
                I_out = (-b+math.sqrt(b**2-4*a*c))/(2*a) # just the quadratic formula
                U_out = self.outPuts(T, it, I_out)
            except Exception as err:
                print(err)
                I_out = None
                U_out = None
        return U_out, I_out

    def ConfigTemp(self,T):
        E0 = self.pack_voltage_constant
        R  = self.pack_resistance
        A  = self.pack_exponential_amplitude
        B  = self.pack_exponential_time_constant
        K  = self.pack_polarization_constant
        Q  = self.pack_charge
        Cv = 0.015
        alf = self.arrh_a
        bet = self.arrh_b
        EDelta = self.DeltaV
        QDelta = self.DeltaQ
        print("start E0, R, A, B, K, Q, Cv")
        print(E0, R, A, B, K, Q, Cv)
        Tref=300
        E0 = E0 + EDelta*(T-Tref)
        Q = Q + QDelta*(T-Tref)
        K = K * math.exp(alf * (1/T - 1/Tref))
        R = R * math.exp(bet * (1/T - 1/Tref))
        print("end E0, R, A, B, K, Q, Cv")
        print(E0, R, A, B, K, Q, Cv)
        print("-----------------------")
        return E0, R, A, B, K, Q, Cv

    def Curr_2_Ploss(self,T,it,i):
        E0,R,A,B,K,Q,Cv = self.ConfigTemp(T)
        Ploss = (i**2)*(K*(Q/(Q-it))+R)
        return Ploss

    def Ploss_2_Heat(self,P,T):
        Ta=320
        Cth = 11000
        Rth = 0.629
        dTdt = P/Cth + (Ta - T)/(Rth*Cth) 
        return dTdt
    
    def Curr_2_Heat(self,T,it,i):
        P = self.Curr_2_Ploss(T,it,i)
        dTdt = self.Ploss_2_Heat(P,T)
        return dTdt

#####################################################################
class Mission:
    def __init__(self, mybattery):
        self.battery = mybattery

    '''def modelP(self,t,y):
        
        #battery state of charge
        it = y[0]
        T = y[1]
        PElectric = 6
        SOC = 1-it/self.battery.pack_charge
        #current drawn to meet power demands
        Vout, i  = self.battery.Power_2_V_A(it, PElectric,T) #convert output power to volts and amps
        Vout = max(0,Vout)
        dTdt = self.battery.Curr_2_Heat(T,it,i)
        self.outBatVolt = Vout
        self.outBatCurr = i
        self.outBatPwr = PElectric
        self.outSOC = SOC
        self.outTemp = T
        self.outdTdt=dTdt
        return [i,dTdt]'''

    def modelC(self,t,y):
        '''constant current'''
        T=y[1]
        it=y[0]/3600
        i = 20
    
        #battery state of charge
        SOC = 1-it/self.battery.pack_charge

        Vout  = self.battery.outPuts(T,it,i)
        dTdt = self.battery.Curr_2_Heat(T,it,i)
        PElectric = Vout * i
        self.outBatVolt = Vout
        self.outBatCurr = i
        self.outBatPwr = PElectric
        self.outSOC = SOC
        self.outTemp = T
        self.outdTdt=dTdt
        return [i,dTdt]

    def evaluate(self,P_n,S_n):

        self.battery.Configure(P_n,S_n)
        self.integral_solution = []
        minutes = 120
        times = range(0,minutes*60,minutes)

        self.plottingVarsC=[]
        rtol = 1e-5
        method= 'BDF'
        y0 = [0,320] #initial spent charge
        for i in range(len(times)-1):
            sol = integrate.solve_ivp(self.modelC,[times[i], times[i+1]], y0, method=method, rtol=rtol)
            self.integral_solution.append(sol)
            for k in range(len(sol.t)):
                yy0 = [sol.y[0][k],sol.y[1][k]]
                self.modelC(sol.t[k],yy0)
                self.plottingVarsC.append([sol.t[k],
                                            self.outSOC,
                                            self.outBatVolt,
                                            self.outBatCurr,
                                            self.outBatPwr,
                                            self.outdTdt,
                                            self.outTemp])
            y0 = [sol.y[0][-1],sol.y[1][-1]]
        
        '''#########
        self.plottingVarsP=[]
        rtol = 1e-5
        method= 'BDF'
        y0 = [0,275] #initial spent charge and T
        for i in range(len(times)-1):
            sol = integrate.solve_ivp(self.modelP,[times[i], times[i+1]], y0, method=method, rtol=rtol)
            self.integral_solution.append(sol)
            for k in range(len(sol.t)):
                yy0 = [sol.y[0][k],sol.y[1][k]]
                self.modelP(sol.t[k],yy0)
                self.plottingVarsP.append([sol.t[k],
                                            self.outSOC,
                                            self.outBatVolt,
                                            self.outBatCurr,
                                            self.outBatPwr,
                                            self.outdTdt,
                                            self.outTemp])
            y0 = [sol.y[0][-1],sol.y[1][-1]]'''


##############################################################

mybat = Battery()
mybat.SetInput()
mymiss = Mission(mybat)

mymiss.evaluate(1,1)
aC=mymiss.plottingVarsC
#aP=mymiss.plottingVarsP
#for k in range(len(aC)):
    #print(f'{aC[k][0]}|{aC[k][1]}|{aC[k][2]}|{aC[k][3]}|{aC[k][4]}')

aC=np.array(aC)
#aP=np.array(aP)
bC = {'time': aC[:,0],
     'soc':aC[:,1],
     'voltage':aC[:,2],
     'current': aC[:,3],
     'power': aC[:,4],
     'dTdt':aC[:,5],
     'temperature':aC[:,6]
    }
'''
bP = {'time': aP[:,0],
     'soc':aP[:,1],
     'voltage':aP[:,2],
     'current': aP[:,3],
     'power': aP[:,4],
     'dTdt':aP[:,5],
     'temperature':aP[:,6]
    }'''

foldername = 'testingoutputs'
plotData(bC, 'time' , 'soc' , 'CC t v soc', foldername)
plotData(bC, 'time' , 'voltage' , 'CC t v volt', foldername)
plotData(bC, 'time' , 'current' , 'CC t v curr', foldername)
plotData(bC, 'time' , 'power' , 'CC t v pwr', foldername)
plotData(bC, 'time' , 'temperature' , 'CC t v temp', foldername)
plotData(bC, 'time' , 'dTdt' , 'CC t v dTdt', foldername)
'''
plotData(bP, 'time' , 'soc' , 'PP t v soc', foldername)
plotData(bP, 'time' , 'voltage' , 'PP t v volt', foldername)
plotData(bP, 'time' , 'current' , 'PP t v curr', foldername)
plotData(bP, 'time' , 'temperature' , 'PP t v temp', foldername)
plotData(bP, 'time' , 'dTdt' , 'PP t v dTdt', foldername)
'''
