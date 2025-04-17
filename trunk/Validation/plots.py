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

    plts = {"line": sns.lineplot, "bar": sns.barplot, "scatter": sns.scatterplot}
    f = plts[style]
    f(x=x_data, y=y_data)

    # Add labels and title
    plt.xlabel(x_label)
    plt.ylabel(y_label)
    if title is None:
        title = f"{y_label} vs {x_label} - {style}plot"
    plt.title(title)

    # Save the plot as a PDF
    filename = os.path.join(directory, title + ".pdf")
    plt.savefig(filename)
    print(f"||>- Saved '{title}' to '{filename}'")
    plt.close()

    # create json of just the data used, so that this plot can be manually
    # retrieved and easily replotted in a prettier way if desired
    filename_json = os.path.join(directory, title + ".json")
    dictjson = {
        "class": "Class II",
        "type": style,
        "title": title,
        "x_units": "",
        "y_units": "",
        "x_label": x_label,
        "y_label": y_label,
        "x_scale": 1,
        "y_scale": 1,
        "x_offset": 0,
        "y_offset": 0,
        "data": {
            "x": x_data,
            "y": y_data,
        },
    }
    ex.dump_json(dictjson, filename_json)
    print(f"||>+ Wrote '{title}' to '{filename_json}'")


def plot_flight(flight, directory):
    """processes and plots all the data from a given flight"""
    # Run the appropriate plots depending on the powerplant
    for key, _ in flight.items():
        if key != "Time":
            # print(f"GOING TO PLOT {key}")
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
        title="eval_per_iter",
        style="bar",
    )
    for i, p in enumerate(ppn):
        single_plot(
            list(range(len(p))),
            p,
            "Evaluation",
            "Evaluated P_n",
            directory,
            title=f"P_at_iter_{i + 1}",
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
        except Exception as err:
            print(f"Failed to plot [{o}] over [{i}]:\n{err}")


def multiplot_2(data, i, oo, output_d):
    """
    Make heat maps and scatter plots when 2 configuration inputs are swept over.
    A heat map is useful if two numerical ranges (like range and payload) are
    being swept. A scatter plot is useful if something like the powerplant and
    one numerical value are being swept over.
    """
    for o in oo:
        try:
            heatmap(data, i[0], i[1], o, output_d)
            iter_plot(data, i[0], i[1], o, output_d)
            iter_plot(data, i[1], i[0], o, output_d)
        except Exception as err:
            print(f"WARNING! FAILED TO PLOT  [{o}] over [{i[0]}] and [{i[1]}]\nObtained error:\n{err}")


def iter_plot(data, x, z, y, directory, title=None):
    """Make scatter plots of the data"""
    sns.scatterplot(data=data, x=x, y=y, hue=z)

    plt.xlabel(x)
    plt.ylabel(y)
    if title is None:
        title = f"Scatterplot of {y} vs {x} for different {z}"
    plt.title(title)

    # Save the plot as a PDF
    filename = os.path.join(directory, title + ".pdf")  # create file inside the output directory
    plt.savefig(filename)
    print("]]=> Saved '", title, "' to", filename)
    plt.close()  # Close the plot


def clean_dictlist(dictlist):

    max_length = max(len(lst) for lst in dictlist.values())
    filtered_data = {key: lst for key, lst in dictlist.items() if len(lst) == max_length}
    return filtered_data

def heatmap(dictlist, x, y, z, directory, title=None):
    """jank method of plotting the data into a heatmap"""
    # Create pivot table and plot heatmap
    dicts = clean_dictlist(dictlist)
    df = pd.DataFrame(dicts)  # convert to pandas dataframe for use with seaborn
    pivot = df.pivot_table(values=z, index=y, columns=x)
    sns.heatmap(pivot)

    plt.xlabel(x)
    plt.ylabel(y)
    if title is None:
        title = f"Heatmap of {z} over {x} and {y}"
    plt.title(title)
    
    plt.tight_layout()
    # Save the plot as a PDF
    filename = os.path.join(directory, title + ".pdf")  # create file inside the output directory
    plt.savefig(filename)
    print("]]=> Saved '", title, "' to", filename)
    plt.close()  # Close the plot

    # Export data to json file
    filename_json = os.path.join(directory, title + ".json")
    dfout = df[[x, y, z]]
    dictjson = {
        "class": "Class II",
        "type": "heatmap",
        "title": title,
        "x_units": "",
        "y_units": "",
        "z_units": "",
        "x_scale": 1,
        "y_scale": 1,
        "z_scale": 1,
        "x_offset": 0,
        "y_offset": 0,
        "z_offset": 0,
        "x_label": x,
        "y_label": y,
        "z_label": z,
        "x": x,
        "y": y,
        "z": z,
        "z average":dfout[z].mean(),
        "data": dfout.to_dict("records"),
    }
    ex.dump_json(dictjson, filename_json)
    print(f"||>+ Wrote '{title}' to '{filename_json}'")
