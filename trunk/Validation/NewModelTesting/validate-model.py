import math
import numbers
import numpy as np
import scipy.integrate as integrate
import os
import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd

cellparameters={
    'Exp Amplitude': 13.768-13.338,         # in volts
    'Exp Time constant': 1.5213,            # in Ah^-1 
    'Internal Resistance': 0.0126,          # in ohms
    'Resistance Arrhenius Constant': 2836,  # dimensionless
    'Polarization Constant': 0.0033,        # in Volts over amp hour
    'Polarization Arrhenius Constant': 1225,# dimensionless
    'Cell Capacity': 42.82,                 # in Ah
    'Capacity Thermal Slope': 0.17660,      # in Ah per kelvin
    'Voltage Constant':13.338,              # in volts
    'Voltage Thermal Slope': 0.00004918,    # in volts per kelvin
    'Cell Voltage Min': 2.5,                # in volts
    'Cell C rating': 4,                     # dimensionless
    'Heat Capacity':6000,                   # WIP
    'Cell Mass': 0.005,                     # in kg
    'Cell Radius': 0.006,                   # in m
    'Cell Height': 0.065,                   # in m
}


def load_csv(file):
    """Loads CSV with timestamps and values into numpy arrays."""
    data = pd.read_csv(file)
    t = data.iloc[:, 0].values
    y = data.iloc[:, 1].values
    return t, y

def plotData(data, foldername):
    time = data['time']
    for key, values in data.items():
        if key != 'time':
            sns.scatterplot(x=time, y=values)
            plt.xlabel('Time')
            plt.ylabel(key)
            title = f'{key}_over_time'
            plt.title(title)
            # Save the plot as a PDF
            filename = os.path.join(foldername, title+".pdf") #create file inside the output directory
            plt.savefig(filename)
            print('||>- Saved \'',title,'\' to',filename)
            plt.close()  # Close the plot

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

    sns.scatterplot(x=time, y=real)
    sns.scatterplot(x=time, y=sim)

    # Add labels and title
    plt.xlabel("time")
    plt.ylabel("value")
    plt.title(title)

    # Save the plot as a PDF
    filename = os.path.join(foldername, title+"-compare.pdf") #create file inside the output directory
    plt.savefig(filename)
    print('||>- Saved \'',title,'\' to',filename)
    plt.close()  # Close the plot


class Battery:
    def __init__(self):
        self.T = None
        self.i = None
        self.it = None

    @property
    def Vout(self) -> float:
        return self.voltageModel(self.T , self.it , self.i)
    
    @property
    def Voc(self) -> float:
        return self.voltageModel(self.T , self.it , 0)
    
    @property
    def SOC(self) -> float:
        return 1-self.it/self.capacity

    # Set inputs from cell model chosen
    def SetInput(self):
        self.cell = cellparameters
        # Get all parameters of the battery
        self.Tref              = 273.15+23 #self.cell['Reference Temperature']
        self.exp_amplitude     = self.cell['Exp Amplitude']                  # in volts
        self.exp_time_ctt      = self.cell['Exp Time constant']              # in Ah^-1 
        self.resistance        = self.cell['Internal Resistance']            # in ohms
        self.R_arrhenius       = self.cell['Resistance Arrhenius Constant']  # dimensionless
        self.polarization_ctt  = self.cell['Polarization Constant']          # in Volts over amp hour
        self.K_arrhenius       = self.cell['Polarization Arrhenius Constant']# dimensionless
        self.capacity          = self.cell['Cell Capacity']                  # in Ah
        self.Q_slope           = self.cell['Capacity Thermal Slope']         # in ??UNCLEAR?? per kelvin
        self.voltage_ctt       = self.cell['Voltage Constant']               # in volts
        self.E_slope           = self.cell['Voltage Thermal Slope']          # in volts per kelvin
        self.Vmax              = self.exp_amplitude + self.voltage_ctt       # in volts
        self.Vmin              = self.cell['Cell Voltage Min']               # in volts
        self.rate              = self.cell['Cell C rating']                  # dimensionless
        self.current           = self.rate * self.capacity                   # in amperes
        self.mass              = self.cell['Cell Mass']                      # in kg
        self.radius            = self.cell['Cell Radius']                    # in m
        self.height            = self.cell['Cell Height']                    # in m

        if not (self.Vmax > self.Vmin):
            raise ValueError("Illegal cell voltages: Vmax must be greater than Vmin")

    def voltageModel(self, T,it,i):
        '''Converts the current being drawn + the current
        spent so far into an output voltage'''

        E0,R,A,B,K,Q,Cv = self.ConfigTemp(T)

        V = E0 -i*K*(Q/(Q-it)) -it*K*(Q/(Q-it)) +A*np.exp(-B * it) -i*R -it*Cv
        return V

    def ConfigTemp(self,T):
        sE0 , sR , A      = self.voltage_ctt , self.resistance      , self.exp_amplitude
        B   , sK , sQ     = self.exp_time_ctt, self.polarization_ctt, self.capacity
        alf , bet, EDelta = self.K_arrhenius , self.R_arrhenius     , self.E_slope
        QDelta, Tref      = self.Q_slope     , self.Tref

        Cv = 0.015*0 # delete this later
        E0 = sE0 + EDelta*(T-Tref)
        Q = sQ + QDelta*(T-Tref)
        K = sK * math.exp(alf * (1/T - 1/Tref))
        R = sR * math.exp(bet * (1/T - 1/Tref))

        return E0, R, A, B, K, Q, Cv
 
    def heatLoss(self,Ta):

        V , Voc  = self.Vout , self.Voc
        i , it   = self.i    , self.it
        T , dEdT = self.T    , self.E_slope

        P = (Voc-V)*i + dEdT*i*T
        tc = 4880
        Rth = 0.629
        Cth = tc/Rth
        dTdt = P/Cth + (Ta - T)/(Rth*Cth) 
        return dTdt,P

#####################################################################
class Mission:
    def __init__(self, batt,Ta):
        self.bt = batt
        self.Ta = Ta
    def model(self,t,y):
        
        # update the battery temperature, charge, and current
        self.bt.T = y[1]
        self.bt.it = y[0]/3600
        self.bt.i = 20
        # calculate the heat loss at the present ambient T
        dTdt,_ = self.bt.heatLoss(Ta)

        return [self.bt.i,dTdt]

    def evaluate(self,times):
        y0 = [0,self.Ta] #initial spent charge
        sol = integrate.solve_ivp(self.model,(times[0],times[-1]), y0, t_eval=times, method='BDF', rtol=1e-5)
        return sol

##############################################################

bat = Battery()
bat.SetInput()
Ta=273.15+0 #ambient T

mymiss = Mission(bat,Ta)
times, Vs = load_csv('data.csv')
results = mymiss.evaluate(times)

aC=[]
for k in range(len(results.t)):
    yy0 = [results.y[0][k],results.y[1][k]]
    out = mymiss.model(results.t[k],yy0)
    aC.append([ results.t[k],
                bat.SOC,
                bat.Vout,
                bat.i,
                bat.i*bat.Vout,
                out[1],
                bat.T])
aC=np.array(aC)

bC = {'time': aC[:,0],
     'soc':aC[:,1],
     'voltage':aC[:,2],
     'current': aC[:,3],
     'power': aC[:,4],
     'dTdt':aC[:,5],
     'temperature':aC[:,6]-273.15
    }

foldername = 'testingoutputs'
plotData(bC,foldername)

plotErrors(times,Vs,bC['voltage'],'VoltageError',foldername)