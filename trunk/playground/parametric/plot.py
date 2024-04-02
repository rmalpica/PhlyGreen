import numpy as np
import matplotlib.pyplot as plt

#cases = ['conventional','fteu2021+pem+cc','ft eu2021+smr+cc','fteu2050+pem+cc', 'ftWindPower+pem+cc', 'ftNuclear+cc' ]
cases = ['conventional','ft eu2021+smr+cc','fteu2050+pem+cc', 'ftWindPower+pem+cc', 'ftNuclear+cc' ]

def rescale_data(data, new_min=50, new_max=500):
    """
    Rescales a given data array to a new range.
    
    Parameters:
        data (list or numpy array): The input data array.
        new_min (float, optional): The minimum value of the new range. Default is 50.
        new_max (float, optional): The maximum value of the new range. Default is 500.
        
    Returns:
        rescaled_data (numpy array): The rescaled data array.
    """
    # Find the min and max values of the input data
    min_val = min(data)
    max_val = max(data)
    
    # Rescale the data to the new range
    rescaled_data = []
    for val in data:
        rescaled_val = ((val - min_val) / (max_val - min_val)) * (new_max - new_min) + new_min
        rescaled_data.append(rescaled_val)
    
    return rescaled_data
    
results = []
    
# Load the text file
for case in cases:
    file_path = 'samples_'+case+'.txt' 
    data = np.loadtxt(file_path)
    results.append(data)

results = np.concatenate(results, axis=0)

WTO = results[:,4] 
SourceEnergy = results[:,5] * 1e-9  #GJ 
Psi = results[:,6] 
Phi = results[:,0] 
WF = results[:,9]
WBat = results[:,8] 
WPT = results[:,10] 
WS = results[:,7] 
WtWCO2 = results[:,13] 

plt.figure(figsize=(8, 6))
plt.scatter(WTO, WF, c=Phi, s=rescale_data(WBat,25,500), cmap='viridis',alpha=0.75)
plt.xlabel('MTOW [Kg]')
plt.ylabel('Fuel Weight [Kg]')
plt.title('Circle size: Battery Weight')
plt.colorbar(label='Deg. of Hybr.')
plt.grid(True)
plt.savefig('TOW_vs_FW.png', dpi=600, format='png',bbox_inches="tight")
plt.close()

plt.figure(figsize=(8, 6))
plt.scatter(SourceEnergy, WtWCO2, c=Phi, s=rescale_data(WTO,25,200), cmap='viridis',alpha=0.75)
plt.xlabel('Source energy [GJ]')
plt.ylabel('WtW CO2 [Kg]')
plt.title('Circle size: TOW')
plt.colorbar(label='Deg. of Hybr.')
plt.grid(True)
plt.savefig('source_vs_CO2_tow.png', dpi=600, format='png',bbox_inches="tight")
plt.close()

plt.figure(figsize=(8, 6))
plt.scatter(WTO, WtWCO2, c=Phi, s=rescale_data(SourceEnergy,25,500), cmap='viridis',alpha=0.75)
plt.xlabel('TOW [Kg]')
plt.ylabel('WtW CO2 [Kg]')
plt.title('Circle size: Source Energy')
plt.colorbar(label='Deg. of Hybr.')
plt.grid(True)
plt.savefig('TOW_vs_CO2.png', dpi=600, format='png',bbox_inches="tight")
plt.close()