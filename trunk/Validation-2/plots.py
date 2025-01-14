"""functions for plotting the flight data"""

import os
import seaborn as sns
import matplotlib.pyplot as plt
import extras as ex

def single_plot(x_data, y_data, x_label, y_label, directory):
    """
    plot a single value from the flight and write
    the data used to a json file so that it can be
    retrieved and plotted manually easily if needed
    """
    # Create a plot using Seaborn
    sns.lineplot(x=x_data, y=y_data)

    # Add labels and title
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    title = f"{x_label} vs {y_label}"
    plt.title(title)

    # Save the plot as a PDF
    filename = os.path.join(directory, title + ".pdf")  # create file inside the output directory
    plt.savefig(filename)
    print("||>- Saved '", title, "' to", filename)
    plt.close()  # Close the plot

    # create json of just the data used, so that this plot can be manually
    # retrieved and easily replotted in a prettier way if desired
    filename_json = os.path.join(directory, title + ".json")
    dictjson = {"title": title, "x_units": "", "y_units": "", x_label: x_data, y_label: y_data}
    ex.dump_json(dictjson, filename_json)
    print("||>+ Wrote '", title, "' to", filename)


def plot_flight(flight, directory):
    """processes and plots all the data from a given flight"""
    # Run the appropriate plots depending on the powerplant
    data = flight["Outputs"]
    for key, _ in data.items():
        if not key == "Time":
            single_plot(data["Time"], data[key], "Time", key, directory)
