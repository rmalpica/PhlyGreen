import math
import numbers
import numpy as np
import scipy.integrate as integrate
import os
import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd

cellparameters={
    'Exp Amplitude': 0.7,                   # in volts
    'Exp Time constant': 1.5213,            # in Ah^-1 
    'Internal Resistance': 0.0126,          # in ohms
    'Resistance Arrhenius Constant': 2836,  # dimensionless
    'Polarization Constant': 0.0033,        # in Volts over amp hour
    'Polarization Arrhenius Constant': 1225,# dimensionless
    'Cell Capacity': 42.82,                 # in Ah
    'Capacity Thermal Slope': 0.1766/3600,  # in UNCLEAR per kelvin
    'Voltage Constant':13.338,              # in volts
    'Voltage Thermal Slope': 0.00004918,    # in volts per kelvin
    'Cell Voltage Min': 2.5,                # in volts
    'Cell C rating': 4,                     # dimensionless
    'Heat Capacity':6000,                   # WIP
    'Cell Mass': 0.005,                     # in kg
    'Cell Radius': 0.006,                   # in m
    'Cell Height': 0.065,                   # in m
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

def load_csv(file_path):
    """Loads CSV with timestamps and values into numpy arrays."""
    data = pd.read_csv(file_path)
    timestamps = data.iloc[:, 0].values
    V = data.iloc[:, 1].values
    T = data.iloc[:, 2].values
    return timestamps, V, T

def ePlot(time, err, title, foldername):
    sns.scatterplot(x=time, y=err)
    # Add labels and title
    plt.xlabel('Time')
    plt.ylabel('Error')
    plt.title(title)
    # Save the plot as a PDF
    filename = os.path.join(foldername, title+".pdf") #create file inside the output directory
    plt.savefig(filename)
    print('||>- Saved \'',title,'\' to',filename)
    plt.close()  # Close the plot

def plotErrors(time, real, sim, title, foldername):
    absolute_err = sim-real
    relative_err = 100*absolute_err/real
    ePlot(time, absolute_err, title+"-err_abs", foldername)
    ePlot(time, relative_err, title+"-err_rel", foldername)


class Battery:
    def __init__(self):
        pass

    # Set inputs from cell model chosen
    def SetInput(self):
        self.cell_model = cellparameters
        # Get all parameters of the battery
        self.cell_exp_amplitude     = self.cell_model['Exp Amplitude']                  # in volts
        self.cell_exp_time_ctt      = self.cell_model['Exp Time constant']              # in Ah^-1 
        self.cell_resistance        = self.cell_model['Internal Resistance']            # in ohms
        self.cell_R_arrhenius       = self.cell_model['Resistance Arrhenius Constant']  # dimensionless
        self.cell_polarization_ctt  = self.cell_model['Polarization Constant']          # in Volts over amp hour
        self.cell_K_arrhenius       = self.cell_model['Polarization Arrhenius Constant']# dimensionless
        self.cell_capacity          = self.cell_model['Cell Capacity']                  # in Ah
        self.cell_Q_slope           = self.cell_model['Capacity Thermal Slope']         # in ??UNCLEAR?? per kelvin
        self.cell_voltage_ctt       = self.cell_model['Voltage Constant']               # in volts
        self.cell_E_slope           = self.cell_model['Voltage Thermal Slope']          # in volts per kelvin
        self.cell_Vmax              = self.cell_exp_amplitude + self.cell_voltage_ctt   # in volts
        self.cell_Vmin              = self.cell_model['Cell Voltage Min']               # in volts
        self.cell_rate              = self.cell_model['Cell C rating']                  # dimensionless
        self.cell_current           = self.cell_rate * self.cell_capacity               # in amperes
        self.cell_mass              = self.cell_model['Cell Mass']                      # in kg
        self.cell_radius            = self.cell_model['Cell Radius']                    # in m
        self.cell_height            = self.cell_model['Cell Height']                    # in m

        if not (self.cell_Vmax > self.cell_Vmin):
            raise ValueError("Illegal cell voltages: Vmax must be greater than Vmin")

    def voltageModel(self, T,it,i):
        '''Converts the current being drawn + the current
        spent so far into an output voltage'''

        E0,R,A,B,K,Q,Cv = self.ConfigTemp(T)

        V = E0 -i*K*(Q/(Q-it)) -it*K*(Q/(Q-it)) +A*np.exp(-B * it) -i*R -it*Cv
        return V

    def ConfigTemp(self,T):
        sE0 = self.cell_voltage_ctt
        sR  = self.cell_resistance
        A  = self.cell_exp_amplitude
        B  = self.cell_exp_time_ctt
        sK  = self.cell_polarization_ctt
        sQ  = self.cell_capacity
        Cv = 0.015
        alf = self.cell_K_arrhenius
        bet = self.cell_R_arrhenius
        EDelta = self.cell_E_slope
        QDelta = self.cell_Q_slope
        
        Tref=300
        E0 = sE0 + EDelta*(T-Tref)
        Q = sQ + QDelta*(T-Tref)
        K = sK * math.exp(alf * (1/T - 1/Tref))
        R = sR * math.exp(bet * (1/T - 1/Tref))

        print("E0 , R , K , Q")
        print(f'old {sE0:.5} | {sR:.5} | {sK:.5} | {sQ:.5}')
        print(f'new {E0:.5} | {R:.5} | {K:.5} | {Q:.5}')
        print(f'dlt {E0-sE0:.5} | {R-sR:.5} | {K-sK:.5} | {Q-sQ:.5}')
        print(f'pct {100*(E0-sE0)/sE0:.5} | {100*(R-sR)/sR:.5} | {100*(K-sK)/sK:.5} | {100*(Q-sQ)/sQ:.5}')
        print("-----------------------")
        return E0, R, A, B, K, Q, Cv
 
    def Curr_2_Heat(self,Ta,T,it,i):

        #E0,R,A,B,K,Q,Cv = self.ConfigTemp(T)
        V = self.voltageModel(T,it,i)
        Voc = self.voltageModel(T,it,0)
        P = (Voc-V)*i+self.cell_E_slope*i*T
        tc = 4880
        Rth = 0.629
        Cth = tc/Rth
        dTdt = P/Cth + (Ta - T)/(Rth*Cth) 
        return dTdt,P

#####################################################################
class Mission:
    def __init__(self, mybattery):
        self.battery = mybattery

    def model(self,t,y):
        '''constant current'''
        T=y[1]
        it=y[0]/3600
        i = 20
    
        #battery state of charge
        SOC = 1-it/self.battery.cell_capacity

        Vout  = self.battery.voltageModel(T,it,i)
        dTdt,Pl = self.battery.Curr_2_Heat(Ta,T,it,i)
        print("Ta",Ta)
        PElectric = Vout * i
        self.outBatVolt = Vout
        self.outBatCurr = i
        self.outBatPwr = PElectric
        self.outSOC = SOC
        self.outTemp = T
        self.outdTdt=dTdt
        self.outHeat=Pl
        return [i,dTdt]

    def evaluate(self,times,Tb):
        rtol = 1e-5
        method= 'BDF'
        y0 = [0,Tb] #initial spent charge
        sol = integrate.solve_ivp(self.model,(times[0],times[-1]), y0, method=method, rtol=rtol, t_eval=times)
        return sol

##############################################################

mybat = Battery()
mybat.SetInput()
mymiss = Mission(mybat)

Ta=273.15+0 #ambient T
Tb=Ta  #initial battery T

times, Vs, Ts = load_csv('data.csv')
results = mymiss.evaluate(times,Tb)

aC=[]
for k in range(len(results.t)):
    yy0 = [results.y[0][k],results.y[1][k]]
    mymiss.model(results.t[k],yy0)
    aC.append([ results.t[k],
                mymiss.outSOC,
                mymiss.outBatVolt,
                mymiss.outBatCurr,
                mymiss.outBatPwr,
                mymiss.outdTdt,
                mymiss.outTemp,
                mymiss.outHeat])
aC=np.array(aC)

bC = {'time': aC[:,0],
     'soc':aC[:,1],
     'voltage':aC[:,2],
     'current': aC[:,3],
     'power': aC[:,4],
     'dTdt':aC[:,5],
     'temperature':aC[:,6]-273.15,
     'loss':aC[:,7]
    }

foldername = 'testingoutputs'
plotData(bC, 'time' , 'soc' , 'CC t v soc', foldername)
plotData(bC, 'time' , 'voltage' , 'CC t v volt', foldername)
plotData(bC, 'time' , 'current' , 'CC t v curr', foldername)
plotData(bC, 'time' , 'power' , 'CC t v pwr', foldername)

plt.ylim(-20, 60)
plotData(bC, 'time' , 'temperature' , 'CC t v temp', foldername)
plotData(bC, 'time' , 'dTdt' , 'CC t v dTdt', foldername)
plotData(bC, 'time' , 'loss' , 'CC t v loss', foldername)

plotErrors(times,Vs,bC['voltage'],'VoltageError',foldername)