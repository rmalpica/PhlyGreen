"""functions for plotting the flight data"""

import os
import seaborn as sns
import matplotlib.pyplot as plt
import extras as ex


def single_plot(x_data, y_data, x_label, y_label, directory, title=None, style="line"):
    """
    plot a single value from the flight and write
    the data used to a json file so that it can be
    retrieved and plotted manually easily if needed
    """
    # Create a plot using Seaborn
    if style == "line":
        sns.lineplot(x=x_data, y=y_data)
    elif style == "bar":
        sns.barplot(x=x_data, y=y_data)
    else:
        raise ValueError(f"Undefined plotting style:{style}")

    plts = {"line": sns.lineplot, "bar": sns.barplot}
    f = plts[style]
    f(x=x_data, y=y_data)

    # Add labels and title
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    if title is None:
        title = f"{x_label} vs {y_label}"
    plt.title(title)

    # Save the plot as a PDF
    filename = os.path.join(directory, title + ".pdf")  # create file inside the output directory
    plt.savefig(filename)
    print(f"||>- Saved '{title}' to '{filename}'")
    plt.close()  # Close the plot

    # create json of just the data used, so that this plot can be manually
    # retrieved and easily replotted in a prettier way if desired
    filename_json = os.path.join(directory, title + ".json")
    dictjson = {"title": title, "x_units": "", "y_units": "", x_label: x_data, y_label: y_data}
    ex.dump_json(dictjson, filename_json)
    print(f"||>+ Wrote '{title}' to '{filename_json}'")


def plot_flight(flight, directory):
    """processes and plots all the data from a given flight"""
    # Run the appropriate plots depending on the powerplant
    for key, _ in flight.items():
        if key != "Time":
            print(f"GOING TO PLOT {key}")
            single_plot(flight["Time"], flight[key], "Time", key, directory)


def perf_profile(data, directory):
    """extra plots for profiling the algorithm performance of a single flight"""
    ppn = data["Past_P_n"]
    pni = data["P_n Evaluations per iteration"]
    # first plot the evaluations over the iterations
    single_plot(
        list(range(len(pni))),
        pni,
        "Iteration",
        "Evaluations per iteration",
        directory,
        title="Number of P_n evaluations per iteration of the Brent algorithm",
        style="bar",
    )
    for i, p in enumerate(ppn):
        single_plot(
            list(range(len(p))),
            p,
            "Evaluation",
            "Evaluated P_n",
            directory,
            title=f"P_n values evaluated during iteration {i + 1} until the optimum was found",
            style="bar",
        )


############################# multi flight relations


def multiPlot(dictList, X, Y, Z, title, foldername):
    # searches in the data for flights with the same Z
    # puts them all in a dictionary grouped by Z
    # plots Y against X multiple times with a different line for each Z
    data = []
    for d in dictList:
        data.append(
            {X: d[X], Y: d[Y], Z: d[Z]}
        )  # reorganize the data so that it can go into pandas
    df = pd.DataFrame(data)  # convert to pandas dataframe for easier use with seaborn
    sns.scatterplot(data=df, x=X, y=Y, hue=Z)
    # Add labels and title
    plt.xlabel(X)
    plt.ylabel(Y)
    plt.title(title)

    # Save the plot as a PDF
    filename = os.path.join(foldername, title + ".pdf")  # create file inside the output directory
    plt.savefig(filename)
    print("]]=> Saved '", title, "' to", filename)
    plt.close()  # Close the plot


def heatMap(dictList, X, Y, Z, title, foldername):
    # searches in the data for flights with the same Z
    # puts them all in a dictionary grouped by Z
    # plots Y against X multiple times with a different line for each Z
    data = []
    for d in dictList:
        data.append(
            {X: d[X], Y: d[Y], Z: d[Z]}
        )  # reorganize the data so that it can go into pandas
    df = pd.DataFrame(data)  # convert to pandas dataframe for easier use with seaborn
    df = df.pivot(index=Y, columns=X, values=Z)
    sns.heatmap(data=df)
    # Add labels and title
    plt.xlabel(X)
    plt.ylabel(Y)
    plt.title(title)

    # Save the plot as a PDF
    filename = os.path.join(foldername, title + ".pdf")  # create file inside the output directory
    plt.savefig(filename)
    print("]]=> Saved '", title, "' to", filename)
    plt.close()  # Close the plot

    # create json of just the data used, so that this plot can be manually
    # retrieved and easily replotted in a prettier way if desired
    filenamejson = os.path.join(foldername, title + ".json")
    dictjson = {"title": title, "x_units": "", "y_units": "", "z_units": "", "data": df}
    writeJSON(dictjson, filenamejson)
    print("]]$> Wrote '", title, "' to", filename)
