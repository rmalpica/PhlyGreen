"""functions for plotting the flight data"""

import os
import seaborn as sns
import pandas as pd
import matplotlib.pyplot as plt
import extras as ex


def single_plot(x_data, y_data, x_label, y_label, directory, title=None, style="line"):
    """
    plot a single value from the flight and write
    the data used to a json file so that it can be
    retrieved and plotted manually easily if needed
    """
    # Quick n dirty way to pick the kind of plot to plot
    # print(f"DEBUUUUUGGG------------\n{x_label}:\n{x_data} \n\n\n\n {y_label}:\n{y_data}\n ---- fini\n")
    plts = {"line": sns.lineplot, "bar": sns.barplot, "scatter": sns.scatterplot}
    f = plts[style]
    f(x=x_data, y=y_data)

    # Add labels and title
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    if title is None:
        title = f"{x_label} vs {y_label} - {style}plot"
    plt.title(title)

    # Save the plot as a PDF
    filename = os.path.join(directory, title + ".pdf")
    plt.savefig(filename)
    print(f"||>- Saved '{title}' to '{filename}'")
    plt.close()

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


def multiplot_1(data, i, oo, output_d):
    """
    Make bar plots and scatter plots when only 1 configuration input is being swept over.
    Usually thats going to be the case for things like the powerplant or mission
    profile, so a bar plot makes sense there. Scatter plots are made anyway
    in case a numerical range is being swept over.
    """
    for o in oo:
        try:
            single_plot(data[i], data[o], i, o, output_d, style="bar")
            single_plot(data[i], data[o], i, o, output_d, style="scatter")
        except ValueError as err:
            print(f"Failed to plot {o}:\n{err}")


def multiplot_2(data, i, oo, output_d):
    """
    Make heat maps and scatter plots when 2 configuration inputs are swept over.
    A heat map is useful if two numerical ranges (like range and payload) are
    being swept. A scatter plot is useful if something like the powerplant and
    one numerical value are being swept over.
    """
    print("Successfully used multiplot_2")
    print(data, i, oo, output_d)

    for o in oo:
        heatmap(data, i[0], i[1], o, output_d)


def heatmap(dictlist, x, y, z, directory, title=None):
    """jank method of plotting the data into a heatmap"""
    print(dictlist)
    # data = []
    # for d in dictlist:
    #     data.append(
    #         {x: d[x], y: d[y], z: d[z]}
    #     )  # reorganize the data so that it can go into pandas


 # Create pivot table
    df = pd.DataFrame(dictlist)  # convert to pandas dataframe for use with seaborn
    pivot = df.pivot_table(values=z, index=y, columns=x, aggfunc='mean')
    sns.heatmap(pivot)


    # df = pd.DataFrame(dictlist)  # convert to pandas dataframe for use with seaborn
    # df = df.pivot(index=y, columns=x, values=z)
    # sns.heatmap(data=df)
    # # Add labels and title
    plt.xlabel(x)
    plt.ylabel(y)
    if title is None:
        title = f"Heatmap of {z} over {x} and {y}"
    plt.title(title)

    # Save the plot as a PDF
    filename = os.path.join(directory, title + ".pdf")  # create file inside the output directory
    plt.savefig(filename)
    print("]]=> Saved '", title, "' to", filename)
    plt.close()  # Close the plot


    # BROKEN, DOES NOT WORK RIGHT NOW, FIGURE OUT HOW TO SAVE PIVOT TABLE TO JSON/DICT
    # # create json of just the data used, so that this plot can be manually
    # # retrieved and easily replotted in a prettier way if desired
    # filename_json = os.path.join(directory, title + ".json")
    # dictjson = {"title": title, "x_units": "", "y_units": "", "z_units": "", "data": df}
    # ex.dump_json(dictjson, filename_json)
    # print("]]$> Wrote '", title, "' to", filename_json)
