import numpy as np
import matplotlib.pyplot as plt

# Load the text file
file_path = "pareto_front.txt"  # Replace this with the actual file path
data = np.loadtxt(file_path)

# Assuming the file contains design points and responses
X = data[:, :2]  # Assuming the first two columns are design points
F = data[:, 2:]      # Assuming the remaining columns are responses

plt.figure(figsize=(8, 6))
plt.scatter(X[:, 0], X[:, 1], c=F[:, 0], s=(1e-11*F[:, 2]-4.15)*1e3, cmap='viridis',alpha=0.75)
plt.xlabel('Deg. of. Hybr. [-]')
plt.ylabel('Battery specific energy [Wh/Kg]')
plt.title('Circle size: source energy')
plt.colorbar(label='TOW [Kg]')
plt.grid(True)
plt.savefig('phi_vs_ebat.png', dpi=600, format='png',bbox_inches="tight")
plt.close()


plt.figure(figsize=(8, 6))
plt.scatter(F[:, 0], F[:, 1], c=X[:, 0], s=1e-3*X[:, 1]**2, cmap='viridis',alpha=0.75)
plt.xlabel('MTOW [Kg]')
plt.ylabel('Fuel Weight [Kg]')
plt.title('Circle size: battery energy')
plt.colorbar(label='Deg. of Hybr.')
plt.grid(True)
plt.savefig('TOW_vs_FW.png', dpi=600, format='png',bbox_inches="tight")
plt.close()

plt.figure(figsize=(8, 6))
plt.scatter(F[:, 2], F[:, 3], c=X[:, 0], s=1e-11*F[:, 0]**3, cmap='viridis',alpha=0.75)
plt.xlabel('Source energy [MJ]')
plt.ylabel('WtW CO2 [Kg]')
plt.title('Circle size: TOW')
plt.colorbar(label='Deg. of Hybr.')
plt.grid(True)
plt.savefig('source_vs_CO2_tow.png', dpi=600, format='png',bbox_inches="tight")
plt.close()

plt.figure(figsize=(8, 6))
plt.scatter(F[:, 2], F[:, 3], c=X[:, 0], s=1e-3*X[:, 1]**2, cmap='viridis',alpha=0.75)
plt.xlabel('Source energy [MJ]')
plt.ylabel('WtW CO2 [Kg]')
plt.title('Circle size: battery energy')
plt.colorbar(label='Deg. of Hybr.')
plt.grid(True)
plt.savefig('source_vs_CO2.png', dpi=600, format='png',bbox_inches="tight")
plt.close()

plt.figure(figsize=(8, 6))
plt.scatter(F[:, 0], F[:, 3], c=X[:, 0], s=(1e-11*F[:, 2]-4.15)*1e3, cmap='viridis',alpha=0.75)
plt.xlabel('TOW [Kg]')
plt.ylabel('WtW CO2 [Kg]')
plt.title('Circle size: Source Energy')
plt.colorbar(label='Deg. of Hybr.')
plt.grid(True)
plt.savefig('TOW_vs_CO2.png', dpi=600, format='png',bbox_inches="tight")
plt.close()

