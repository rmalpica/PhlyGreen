import math
import os
import numpy as np
from scipy import integrate
import seaborn as sns
import matplotlib.pyplot as plt
import pandas as pd

cellparameters = {
    "Exp Amplitude": 13.768 - 13.338,  # in volts
    "Exp Time constant": 1.5213,  # in Ah^-1
    "Internal Resistance": 0.0126,  # in ohms
    "Resistance Arrhenius Constant": 2836,  # dimensionless
    "Polarization Constant": 0.0033,  # in Volts over amp hour
    "Polarization Arrhenius Constant": 1225,  # dimensionless
    "Cell Capacity": 42.82,  # in Ah
    "Capacity Thermal Slope": 0.17660,  # in Ah per kelvin
    "Voltage Constant": 13.338,  # in volts
    "Voltage Thermal Slope": 0.00004918,  # in volts per kelvin
    "Cell Voltage Min": 2.5,  # in volts
    "Cell C rating": 4,  # dimensionless
    "Heat Capacity": 6000,  # WIP
    "Cell Mass": 0.005,  # in kg
    "Cell Radius": 0.006,  # in m
    "Cell Height": 0.065,  # in m
}


class Battery:
    def __init__(self):
        self.T = None
        self.i = None
        self.it = None

    @property
    def Vout(self) -> float:
        return self.voltageModel(self.T, self.it, self.i)

    @property
    def Voc(self) -> float:
        return self.voltageModel(self.T, self.it, 0)

    @property
    def SOC(self) -> float:
        return 1 - self.it / self.capacity

    # Set inputs from cell model chosen
    def SetInput(self):
        self.cell = cellparameters
        # Get all parameters of the battery
        self.Tref = 273.15 + 25  # self.cell['Reference Temperature']
        self.exp_amplitude = self.cell["Exp Amplitude"]  # in volts
        self.exp_time_ctt = self.cell["Exp Time constant"]  # in Ah^-1
        self.resistance = self.cell["Internal Resistance"]  # in ohms
        self.R_arrhenius = self.cell["Resistance Arrhenius Constant"]  # dimensionless
        self.polarization_ctt = self.cell["Polarization Constant"]  # in Volts over amp hour
        self.K_arrhenius = self.cell["Polarization Arrhenius Constant"]  # dimensionless
        self.capacity = self.cell["Cell Capacity"]  # in Ah
        self.Q_slope = self.cell["Capacity Thermal Slope"]  # in Ah per kelvin
        self.voltage_ctt = self.cell["Voltage Constant"]  # in volts
        self.E_slope = self.cell["Voltage Thermal Slope"]  # in volts per kelvin
        self.Vmax = self.exp_amplitude + self.voltage_ctt  # in volts
        self.Vmin = self.cell["Cell Voltage Min"]  # in volts
        self.rate = self.cell["Cell C rating"]  # dimensionless
        self.current = self.rate * self.capacity  # in amperes
        self.mass = self.cell["Cell Mass"]  # in kg
        self.radius = self.cell["Cell Radius"]  # in m
        self.height = self.cell["Cell Height"]  # in m

        if not (self.Vmax > self.Vmin):
            raise ValueError("Illegal cell voltages: Vmax must be greater than Vmin")

    def voltageModel(self, T, it, i):
        """Model that determines the voltage from the present battery state
        Receives:
            - T  - battery's temperature
            - it - battery current integral, aka charge spent so far
            - i  - current draw from the battery
        Returns:
            - V - battery voltage output
        """
        sE0, sR, A = self.voltage_ctt, self.resistance, self.exp_amplitude
        B, sK, sQ = self.exp_time_ctt, self.polarization_ctt, self.capacity
        alf, bet, EDelta = self.K_arrhenius, self.R_arrhenius, self.E_slope
        QDelta, Tref = self.Q_slope, self.Tref

        Cv = 0.015 * 0  # delete this later
        E0 = sE0 + EDelta * (T - Tref)
        Q = sQ + QDelta * (T - Tref)
        K = sK * math.exp(alf * (1 / T - 1 / Tref))
        R = sR * math.exp(bet * (1 / T - 1 / Tref))

        V = (
            E0
            - i * K * (Q / (Q - it))
            - it * K * (Q / (Q - it))
            + A * np.exp(-B * it)
            - i * R
            - it * Cv
        )
        return V

    def heatLoss(self, Ta):
        """Simple differential equation describing a simplified lumped element thermal
        model of the battery
        Receives:
            - Ta - temperature of the ambient cooling air
        Returns:
            - dTdt - battery temperature derivative
            - P    - dissipated waste power
        """
        V, Voc = self.Vout, self.Voc
        i, it = self.i, self.it
        T, dEdT = self.T, self.E_slope

        P = (Voc - V) * i + dEdT * i * T
        tc = 4880
        Rth = 0.629
        Cth = tc / Rth
        dTdt = P / Cth + (Ta - T) / (Rth * Cth)
        return dTdt, P


#####################################################################
class Mission:
    def __init__(self, batt, Ta):
        self.bt = batt
        self.Ta = Ta

    def model(self, t, y):
        # update the battery temperature, charge, and current
        self.bt.T = y[1]
        self.bt.it = y[0] / 3600
        self.bt.i = 20
        # calculate the heat loss at the present ambient T
        dTdt, _ = self.bt.heatLoss(self.Ta)

        return [self.bt.i, dTdt]

    def evaluate(self, times):
        y0 = [0, self.Ta]  # initial spent charge
        # print(times)
        sol = integrate.solve_ivp(
            self.model, (times[0], times[-1]), y0, t_eval=times, method="BDF", rtol=1e-5
        )
        return sol


##############################################################


def load_csv():
    """Loads CSV with timestamps and values into numpy arrays."""
    # Read the CSV file
    df = pd.read_csv("temperature.csv", header=[0, 1])
    # Create a dictionary to store temperature data
    temperatures = {
        "2": {
            "time": df[("2", "X")].dropna().values,
            "temperature": df[("2", "Y")].dropna().values,
        },
        "12": {
            "time": df[("12", "X")].dropna().values,
            "temperature": df[("12", "Y")].dropna().values,
        },
        "25": {
            "time": df[("25", "X")].dropna().values,
            "temperature": df[("25", "Y")].dropna().values,
        },
        "47": {
            "time": df[("47", "X")].dropna().values,
            "temperature": df[("47", "Y")].dropna().values,
        },
    }

    # Read the CSV file
    df = pd.read_csv("voltage.csv", header=[0, 1])
    # Create a dictionary to store temperature data
    voltages = {
        "2": {"time": df[("2", "X")].dropna().values, "voltage": df[("2", "Y")].dropna().values},
        "12": {"time": df[("12", "X")].dropna().values, "voltage": df[("12", "Y")].dropna().values},
        "25": {"time": df[("25", "X")].dropna().values, "voltage": df[("25", "Y")].dropna().values},
        "47": {"time": df[("47", "X")].dropna().values, "voltage": df[("47", "Y")].dropna().values},
    }
    return temperatures, voltages


def plotData(dataset):
    to_plot = ["soc", "vout", "i", "T", "dTdt"]
    sns.set_palette("Set2")  # Distinct, high-contrast colors

    for variable in to_plot:
        sns.scatterplot(data=dataset, x="time", y=variable, hue="Ta")

        plt.xlabel("Time")
        plt.ylabel(variable)
        title = f"{variable}_over_time"
        plt.title(title)
        # Save the plot as a PDF
        filename = os.path.join(
            foldername, title + ".pdf"
        )  # create file inside the output directory
        plt.savefig(filename)
        print("||>- Saved '", title, "' to", filename)
        plt.close()  # Close the plot


def plotErrors(simDataset, realDataset, which):
    # Load the paired color palette and assign matching pairs of colors
    palette = sns.color_palette("Paired", len(simDataset) * 2)

    fig, ax = plt.subplots()
    fig_error, ax_error = plt.subplots()

    # Iterate and plot with paired colors
    for idx, (key, data) in enumerate(simDataset.items()):
        sim = np.array(data[which])
        real = np.array(realDataset[key][which])

        if which == "temperature":
            real += 273.15

        time = simDataset[key]["time"]
        absolute_error = np.abs(sim - real)

        # Use color pairs: even for reference, odd for calculated
        sns.lineplot(
            x=time, y=real, ax=ax, color=palette[2 * idx], label=f"Ref {key}°C", linewidth=1.2
        )
        sns.scatterplot(
            x=time,
            y=sim,
            ax=ax,
            color=palette[2 * idx + 1],
            label=f"Calc {key}°C",
            s=10,
            marker="o",
        )

        # Plot absolute errors using distinct colors
        sns.lineplot(
            x=time,
            y=absolute_error,
            ax=ax_error,
            color=palette[2 * idx],
            label=f"Err {key}°C",
            linewidth=1.2,
        )

    # Temperature comparison plot settings
    ax.set_xlim(0, 8000)
    ax.set_xlabel("Time")
    ax.set_ylabel(which.capitalize())
    ax.set_title(f"Comparison of {which.capitalize()} Over Time")
    ax.legend(loc="lower right", fontsize="x-small", ncol=2, handletextpad=0.4, columnspacing=0.8)

    # Save the temperature comparison plot
    temp_plot_filename = os.path.join(foldername, f"{which}_comparison_combined.pdf")
    fig.savefig(temp_plot_filename)
    print(f"||>- Saved combined {which} comparison plot to {temp_plot_filename}")
    plt.close(fig)

    # Absolute error plot settings
    ax_error.set_xlim(0, 8000)
    ax_error.set_xlabel("Time")
    ax_error.set_ylabel("Absolute Error")
    ax_error.set_title(f"Absolute Errors for {which.capitalize()} Over Time")
    ax_error.legend(loc="upper left", fontsize="small", handletextpad=0.4, columnspacing=0.8)

    # Save the absolute error plot
    error_plot_filename = os.path.join(foldername, f"{which}_absolute_errors_combined.pdf")
    fig_error.savefig(error_plot_filename)
    print(f"||>- Saved combined absolute error plot to {error_plot_filename}")
    plt.close(fig_error)


def getData(results, evaluator):
    out = {"time": [], "soc": [], "vout": [], "i": [], "T": [], "dTdt": [], "Ta": []}
    outerr = {"time": [], "voltage": [], "temperature": []}
    for k , _ in enumerate(results.t):
        yy0 = [results.y[0][k], results.y[1][k]]
        sol = evaluator.model(results.t[k], yy0)
        out["time"].append(results.t[k])
        out["soc"].append(bat.SOC)
        out["vout"].append(bat.Vout)
        out["i"].append(bat.i)
        out["T"].append(bat.T)
        out["dTdt"].append(sol[1])
        out["Ta"].append(evaluator.Ta)

        outerr["time"].append(results.t[k])
        outerr["temperature"].append(bat.T)
        outerr["voltage"].append(bat.Vout)

    return pd.DataFrame(out), outerr


def validate(realdata):
    frames = []
    errdat = {}
    for key in realdata:
        Ta = int(key)
        evaluator = Mission(bat, Ta + 273.15)
        solution = evaluator.evaluate(realdata[key]["time"])
        results_df, errdat[key] = getData(solution, evaluator)
        frames.append(results_df)

    return pd.concat(frames, ignore_index=True), errdat


def validate_all():
    temp_data, volt_data = load_csv()
    results, forerrors = validate(temp_data)
    plotData(results)
    plotErrors(forerrors, temp_data, "temperature")

    results, forerrors = validate(volt_data)
    plotData(results)
    plotErrors(forerrors, volt_data, "voltage")


bat = Battery()
bat.SetInput()
foldername = "testingoutputs"
validate_all()
