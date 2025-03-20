"""Replot a given json"""

import os
import seaborn as sns
import pandas as pd
import matplotlib.pyplot as plt
import extras as ex

OUTDIR = ex.load_dir("PrettyOutputs")
INDIR = ex.load_dir("PrettyInputs")


def heatmap(d):
    # Create pivot table and plot heatmap
    df = pd.DataFrame(d["data"])  # convert to pandas dataframe for use with seaborn
    pivot = df.pivot_table(values=d["z"], index=d["y"], columns=d["x"])

    sns.heatmap(pivot, cbar_kws={"label": f"{d['z_label']} {d['z_units']}"})
    plt.xlabel(f"{d['x_label']} {d['x_units']}")
    plt.ylabel(f"{d['y_label']} {d['y_units']}")

    title = f"z-{d['z_label']}_x-{d['x_label']}_y-{d['y_label']}_heatmap"
    # plt.title(title)

    # Save the plot as a PDF
    filename = os.path.join(OUTDIR, title + ".pdf")  # create file inside the output directory
    plt.savefig(filename)
    print(f"SAVED: {filename}\n")
    plt.close()


def single_plot(d):
    plts = {"line": sns.lineplot, "bar": sns.barplot, "scatter": sns.scatterplot}
    f = plts[d["type"]]
    data = d["data"]
    f(x=data["x"], y=data["y"])

    # Add labels and title
    plt.xlabel(f"{d['x_label']} {d['x_units']}")
    plt.ylabel(f"{d['y_label']}  {d['y_units']}")
    title = f"y-{d['y_label']}_x-{d['x_label']}_{d['type']}"

    # Save the plot as a PDF
    filename = os.path.join(OUTDIR, title + ".pdf")
    plt.savefig(filename)
    print(f"SAVED: {filename}\n")
    plt.close()


def main():
    for file in os.scandir(INDIR):
        if file.is_file():  # Check if it's a file
            f = ex.load_json(file)
            if f["type"] == "heatmap":
                heatmap(f)
            else:
                single_plot(f)


main()
