"""
Hacky script to validate the temperature and voltage curves of the model
from two .csv files obtained from webplotdigitizer. Each .csv is created
by digitizing the desired plot from the images extracted from the og pdf
and then the script reads them, calculates the outputs of the model over
each extracted time point, and plots them all, alongside the total error 
"""
import math
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple, TypedDict

import numpy as np
import pandas as pd
import seaborn as sns
from matplotlib import pyplot as plt
from scipy import integrate


# Type definitions for improved clarity
class TemperatureData(TypedDict):
    time: np.ndarray
    temperature: np.ndarray


class VoltageData(TypedDict):
    time: np.ndarray
    voltage: np.ndarray


@dataclass
class CellParameters:
    """Dataclass to store battery cell parameters with proper typing and documentation"""

    exp_amplitude: float  # Voltage (V)
    exp_time_constant: float  # Inverse amp-hours (Ah^-1)
    internal_resistance: float  # Ohms (Ω)
    resistance_arrhenius: float  # Dimensionless
    polarization_constant: float  # Volts per amp hour (V/Ah)
    polarization_arrhenius: float  # Dimensionless
    cell_capacity: float  # Amp-hours (Ah)
    capacity_thermal_slope: float  # Amp-hours per kelvin (Ah/K)
    voltage_constant: float  # Volts (V)
    voltage_thermal_slope: float  # Volts per kelvin (V/K)
    cell_voltage_min: float  # Volts (V)
    cell_c_rating: float  # Dimensionless
    heat_capacity: float  # Joules per kelvin (J/K)
    cell_mass: float  # Kilograms (kg)
    cell_radius: float  # Meters (m)
    cell_height: float  # Meters (m)

    @property
    def voltage_max(self) -> float:
        """Calculate maximum cell voltage"""
        return self.exp_amplitude + self.voltage_constant

    def validate(self) -> None:
        """Validate cell parameters"""
        if not (self.voltage_max > self.cell_voltage_min):
            raise ValueError("Illegal cell voltages: Vmax must be greater than Vmin")


# Define default cell parameters
DEFAULT_CELL_PARAMETERS = CellParameters(
    exp_amplitude=13.768 - 13.338,
    exp_time_constant=1.5213,
    internal_resistance=0.0126,
    resistance_arrhenius=2836,
    polarization_constant=0.0033,
    polarization_arrhenius=1225,
    cell_capacity=42.82,
    capacity_thermal_slope=0.17660,
    voltage_constant=13.338,
    voltage_thermal_slope=0.00004918,
    cell_voltage_min=2.5,
    cell_c_rating=4,
    heat_capacity=6000,
    cell_mass=0.005,
    cell_radius=0.006,
    cell_height=0.065,
)


class Battery:
    """Battery model with thermal and electrical characteristics"""

    def __init__(self, parameters: CellParameters = DEFAULT_CELL_PARAMETERS):
        self.params = parameters
        self.params.validate()
        self.T: float = None  # Temperature (K)
        self.i: float = None  # Current (A)
        self.it: float = None  # Charge spent (Ah)
        self.reference_temp = 273.15 + 25  # Reference temperature (K)

    @property
    def vout(self) -> float:
        """Output voltage under load"""
        return self._voltage_model(self.T, self.it, self.i)

    @property
    def voc(self) -> float:
        """Open circuit voltage"""
        return self._voltage_model(self.T, self.it, 0)

    @property
    def soc(self) -> float:
        """State of charge (0-1)"""
        return 1 - self.it / self.params.cell_capacity

    def _voltage_model(self, T: float, it: float, i: float) -> float:
        """Calculate battery voltage based on current state"""
        # Thermal adjustments
        E0 = self.params.voltage_constant + self.params.voltage_thermal_slope * (
            T - self.reference_temp
        )
        Q = self.params.cell_capacity + self.params.capacity_thermal_slope * (
            T - self.reference_temp
        )
        K = self.params.polarization_constant * math.exp(
            self.params.polarization_arrhenius * (1 / T - 1 / self.reference_temp)
        )
        R = self.params.internal_resistance * math.exp(
            self.params.resistance_arrhenius * (1 / T - 1 / self.reference_temp)
        )

        # Voltage calculation
        return (
            E0
            - i * K * (Q / (Q - it))
            - it * K * (Q / (Q - it))
            + self.params.exp_amplitude * np.exp(-self.params.exp_time_constant * it)
            - i * R
        )

    def heat_loss(self, ambient_temp: float) -> Tuple[float, float]:
        """Calculate temperature derivative and waste power"""
        # Thermal parameters
        thermal_time_constant = 4880
        thermal_resistance = 0.629
        thermal_capacitance = thermal_time_constant / thermal_resistance

        # Power dissipation
        power = (
            self.voc - self.vout
        ) * self.i + self.params.voltage_thermal_slope * self.i * self.T

        # Temperature derivative
        dT_dt = power / thermal_capacitance + (ambient_temp - self.T) / (
            thermal_resistance * thermal_capacitance
        )

        return dT_dt, power


class BatteryMission:
    """Simulates a battery mission with thermal conditions"""

    def __init__(self, battery: Battery, ambient_temp: float):
        self.battery = battery
        self.ambient_temp = ambient_temp
        self.current = 20  # Fixed current draw (A)

    def model(self, t: float, y: List[float]) -> List[float]:
        """ODE model for battery state evolution"""
        self.battery.it = y[0] / 3600  # Convert charge to Ah
        self.battery.T = y[1]
        self.battery.i = self.current

        dT_dt, _ = self.battery.heat_loss(self.ambient_temp)
        return [self.current, dT_dt]

    def simulate(self, times: np.ndarray) -> integrate.OdeSolution:
        """Simulate battery behavior over given time points"""
        initial_state = [0, self.ambient_temp]  # [charge, temperature]
        return integrate.solve_ivp(
            self.model, (times[0], times[-1]), initial_state, t_eval=times, method="BDF", rtol=1e-5
        )


class DataVisualizer:
    """Handles data visualization and plotting"""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        sns.set_palette("Set2")

    def plot_time_series(self, dataset: pd.DataFrame) -> None:
        """Plot time series data for various battery parameters"""
        variables = ["soc", "vout", "i", "T", "dTdt"]

        for var in variables:
            sns.scatterplot(data=dataset, x="time", y=var, hue="Ta")
            plt.xlabel("Time")
            plt.ylabel(var)
            plt.title(f"{var} over time")

            filename = os.path.join(self.output_dir, f"{var}_over_time.pdf")
            plt.savefig(filename)
            print(f"||>- Saved '{var}' to {filename}")
            plt.close()

    def plot_comparison(self, sim_data: Dict, real_data: Dict, variable: str) -> None:
        """Plot comparison between simulated and real data"""
        palette = sns.color_palette("Paired", len(sim_data) * 2)

        # Create comparison and error plots
        fig_comp, ax_comp = plt.subplots()
        fig_error, ax_error = plt.subplots()

        for idx, (key, data) in enumerate(sim_data.items()):
            sim_values = np.array(data[variable])
            real_values = np.array(real_data[key][variable])

            if variable == "temperature":
                real_values += 273.15

            times = sim_data[key]["time"]
            abs_error = np.abs(sim_values - real_values)

            # Plot comparisons
            sns.lineplot(
                x=times,
                y=real_values,
                ax=ax_comp,
                color=palette[2 * idx],
                label=f"Ref {key}°C",
                linewidth=1.2,
            )
            sns.scatterplot(
                x=times,
                y=sim_values,
                ax=ax_comp,
                color=palette[2 * idx + 1],
                label=f"Calc {key}°C",
                s=10,
                marker="o",
            )

            # Plot errors
            sns.scatterplot(
                x=times,
                y=abs_error,
                ax=ax_error,
                color=palette[2 * idx + 1],
                label=f"Err {key}°C",
                s=10,
                marker="o",
            )

        # Configure and save plots
        self._configure_and_save_plot(
            fig_comp,
            ax_comp,
            variable,
            f"{variable}_comparison_combined.pdf",
            "Comparison",
            "lower right",
        )
        self._configure_and_save_plot(
            fig_error,
            ax_error,
            variable,
            f"{variable}_absolute_errors_combined.pdf",
            "Absolute Errors",
            "upper left",
        )

    def _configure_and_save_plot(self, fig, ax, variable, filename, plot_type, legend_loc):
        """Configure and save a plot with common settings"""
        ax.set_xlim(0, 8000)
        ax.set_xlabel("Time")
        ax.set_ylabel(variable.capitalize() if plot_type == "Comparison" else "Absolute Error")
        ax.set_title(f"{plot_type} of {variable.capitalize()} Over Time")
        ax.legend(loc=legend_loc, fontsize="x-small", ncol=2 if plot_type == "Comparison" else 1)

        filepath = os.path.join(self.output_dir, filename)
        fig.savefig(filepath)
        print(f"||>- Saved {plot_type.lower()} plot to {filepath}")
        plt.close(fig)


class DataProcessor:
    """Handles data loading and processing"""

    @staticmethod
    def load_data() -> Tuple[Dict[str, TemperatureData], Dict[str, VoltageData]]:
        """Load temperature and voltage data from CSV files"""
        temp_df = pd.read_csv("temperature.csv", header=[0, 1])
        volt_df = pd.read_csv("voltage.csv", header=[0, 1])

        temperatures = {}
        voltages = {}
        for key in ["2", "12", "25", "47"]:
            temperatures[key] = {
                "time": temp_df[(key, "X")].dropna().values,
                "temperature": temp_df[(key, "Y")].dropna().values,
            }
            voltages[key] = {
                "time": volt_df[(key, "X")].dropna().values,
                "voltage": volt_df[(key, "Y")].dropna().values,
            }

        return temperatures, voltages

    @staticmethod
    def process_simulation_results(
        results: integrate.OdeSolution, mission: BatteryMission
    ) -> Tuple[pd.DataFrame, Dict]:
        """Process simulation results into DataFrame and error data"""
        data = {"time": [], "soc": [], "vout": [], "i": [], "T": [], "dTdt": [], "Ta": []}
        error_data = {"time": [], "voltage": [], "temperature": []}

        for k, t in enumerate(results.t):
            state = [results.y[0][k], results.y[1][k]]
            derivatives = mission.model(t, state)

            # Record main data
            data["time"].append(t)
            data["soc"].append(mission.battery.soc)
            data["vout"].append(mission.battery.vout)
            data["i"].append(mission.battery.i)
            data["T"].append(mission.battery.T)
            data["dTdt"].append(derivatives[1])
            data["Ta"].append(mission.ambient_temp)

            # Record error data
            error_data["time"].append(t)
            error_data["temperature"].append(mission.battery.T)
            error_data["voltage"].append(mission.battery.vout)

        return pd.DataFrame(data), error_data


def main():
    """Main execution function"""
    # Initialize components
    battery = Battery()
    visualizer = DataVisualizer("outputs")
    temp_data, volt_data = DataProcessor.load_data()

    # Process and visualize temperature data
    frames = []
    temp_error_data = {}
    for key, data in temp_data.items():
        ambient_temp = int(key) + 273.15
        mission = BatteryMission(battery, ambient_temp)
        solution = mission.simulate(data["time"])
        results_df, temp_error_data[key] = DataProcessor.process_simulation_results(
            solution, mission
        )
        frames.append(results_df)

    combined_results = pd.concat(frames, ignore_index=True)
    visualizer.plot_time_series(combined_results)
    visualizer.plot_comparison(temp_error_data, temp_data, "temperature")

    # Process and visualize voltage data
    frames = []
    volt_error_data = {}
    for key, data in volt_data.items():
        ambient_temp = int(key) + 273.15
        mission = BatteryMission(battery, ambient_temp)
        solution = mission.simulate(data["time"])
        results_df, volt_error_data[key] = DataProcessor.process_simulation_results(
            solution, mission
        )
        frames.append(results_df)

    combined_results = pd.concat(frames, ignore_index=True)
    visualizer.plot_time_series(combined_results)
    visualizer.plot_comparison(volt_error_data, volt_data, "voltage")


if __name__ == "__main__":
    main()
