"""Replot a given json"""

import os
import seaborn as sns
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
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
    plt.tight_layout()
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

def heatmap_table(d,MAX_COLS=5,MAX_ROWS=25):
    """
    Generate and save a LaTeX table based on the provided data dictionary.
    """
    df = pd.DataFrame(d["data"])  # Convert data to a pandas dataframe
    pivot = df.pivot_table(values=d["z"], index=d["y"], columns=d["x"])
    pivot = pivot.round(1).fillna("-")

    num_cols = len(pivot.columns)
    if num_cols > MAX_COLS:
        indices = np.linspace(1, num_cols , MAX_COLS , dtype=int)  # Evenly spaced indices
        reduced_cols =  [pivot.columns[i-1] for i in indices]
        pivot = pivot[reduced_cols]

    num_rows = len(pivot.index)
    if num_rows > MAX_ROWS:
        indices = np.linspace(1, num_rows, MAX_ROWS , dtype=int)  # Evenly spaced indices
        reduced_rows = [pivot.index[i-1] for i in indices]
        pivot = pivot.loc[reduced_rows]

    # Extract labels and units
    x_label, x_units = d["x_label"], d["x_units"]
    y_label, y_units = d["y_label"], d["y_units"]
    z_label, z_units = d["z_label"], d["z_units"]

    # Format table header
    table_header = rf"""\begin{{table}}[htb!]
\centering
\caption{{{z_label} {z_units} obtained for different values of {x_label} and {y_label}}}
\label{{tab:{x_label}-{y_label}-{z_label}}}
\begin{{tabular}}{{{"c" * (len(pivot.columns) + 1)}}}
             & \multicolumn{{{len(pivot.columns)}}}{{c}}{{{x_label} {x_units}}} \\ \cline{{2-{len(pivot.columns) + 1}}} 
{y_label} {y_units} & {" & ".join(map(str, pivot.columns))} \\ \hline
"""

    # Format table rows
    table_rows = "\n".join(rf"{y} & {' & '.join(map(str, row))} \\" for y, row in pivot.iterrows())

    # Complete the table
    latex_str = rf"""{table_header}{table_rows}
\hline
\end{{tabular}}
\end{{table}}"""

    # Save LaTeX table to file
    title = f"z-{d['z_label']}_x-{d['x_label']}_y-{d['y_label']}"
    filename = os.path.join(OUTDIR, f"{title}.tex")
    with open(filename, "w") as f:
        f.write(latex_str)

    print(f"SAVED: {filename}\n")



def single_plot_table(d, MAX_ROWS=25):
    """
    Generate and save a LaTeX table based on the provided data dictionary for single plots.
    """
    df = pd.DataFrame({'x': d["data"]["x"], 'y': d["data"]["y"]})
    
    # Reduce the number of rows if necessary
    num_rows = len(df)
    if num_rows > MAX_ROWS:
        indices = np.linspace(0, num_rows - 1, MAX_ROWS, dtype=int)
        df = df.iloc[indices]
    
    df = df.round(1).fillna('-')
    
    # Extract labels and units
    x_label, x_units = d["x_label"], d["x_units"]
    y_label, y_units = d["y_label"], d["y_units"]
    
    # Format table header
    table_header = rf"""\begin{{table}}[htb!]
\centering
\caption{{{y_label} {y_units} obtained for different {x_label} {x_units}}}
\label{{tab:{x_label}-{y_label}}}
\begin{{tabular}}{{cc}}
{x_label} {x_units} & {y_label} {y_units} \\ \hline
"""
    
    # Format table rows
    table_rows = "\n".join([rf"{row['x']} & {row['y']} \\" for _, row in df.iterrows()])
    
    # Complete the table
    latex_str = rf"""{table_header}{table_rows}
\hline
\end{{tabular}}
\end{{table}}"""
    
    # Save LaTeX table to file
    title = f"y-{d['y_label']}_x-{d['x_label']}_table"
    filename = os.path.join(OUTDIR, f"{title}.tex")
    with open(filename, "w") as f:
        f.write(latex_str)
    
    print(f"SAVED: {filename}\n")


def heatmap_table_booktabs(d, MAX_COLS=5, MAX_ROWS=25):
    """
    Generate and save a LaTeX table in booktabs format based on a pivot table.
    
    This function takes a data dictionary, builds a pivot table from the data
    (like constructing a matrix in MATLAB or a 2D array in C), and then formats it
    as a LaTeX table using the booktabs style.
    """
    import os
    import numpy as np
    import pandas as pd

    # Convert the raw data into a pandas DataFrame
    df = pd.DataFrame(d["data"])
    
    # Create a pivot table with the specified x, y, and z keys
    pivot = df.pivot_table(values=d["z"], index=d["y"], columns=d["x"])
    pivot = pivot.round(1).fillna("-")

    # Limit the number of columns (like subsetting an array in C or MATLAB)
    num_cols = len(pivot.columns)
    if num_cols > MAX_COLS:
        indices = np.linspace(1, num_cols, MAX_COLS, dtype=int)
        reduced_cols = [pivot.columns[i - 1] for i in indices]
        pivot = pivot[reduced_cols]

    # Limit the number of rows if necessary
    num_rows = len(pivot.index)
    if num_rows > MAX_ROWS:
        indices = np.linspace(1, num_rows, MAX_ROWS, dtype=int)
        reduced_rows = [pivot.index[i - 1] for i in indices]
        pivot = pivot.loc[reduced_rows]

    # Extract labels and units (similar to variables in C or MATLAB)
    x_label, x_units = d["x_label"], d["x_units"]
    y_label, y_units = d["y_label"], d["y_units"]
    z_label, z_units = d["z_label"], d["z_units"]

    # Build the LaTeX table header using booktabs commands
    # Use \multirow to merge the left column header over two rows.
    # \multicolumn is used to span the x-axis label across all columns.
    col_count = len(pivot.columns)
    # Calculate the ending column for cmidrule (e.g. 2-6 for 5 columns)
    cmid_end = col_count + 1

    table_header = rf"""\begin{{table}}[htb!]
\centering
\caption{{{z_label} {z_units} obtained for different values of {x_label} and {y_label}}}
\label{{tab:{x_label}-{y_label}-{z_label}}}
\begin{{tabular}}{{@{{}}c{'c' * col_count}@{{}}}}
\toprule
\multirow{{2}}{{*}}{{{y_label} {y_units}}} & \multicolumn{{{col_count}}}{{c}}{{{x_label} {x_units}}} \\
\cmidrule(l){{2-{cmid_end}}}
 & {" & ".join(map(str, pivot.columns))} \\ \midrule
"""

    # Build table rows: each row of the pivot table is written out
    table_rows = "\n".join(rf"{y} & {' & '.join(map(str, row))} \\" for y, row in pivot.iterrows())

    # Finish the table with bottom rule and end tabular/table environment
    latex_str = rf"""{table_header}{table_rows}
\bottomrule
\end{{tabular}}
\end{{table}}"""

    # Save LaTeX table to file
    title = f"z-{d['z_label']}_x-{d['x_label']}_y-{d['y_label']}"
    filename = os.path.join(OUTDIR, f"{title}.tex")
    with open(filename, "w") as f:
        f.write(latex_str)

    print(f"SAVED: {filename}\n")


    print(f"SAVED: {filename}\n")


def single_plot_table_booktabs(d, MAX_ROWS=25):
    """
    Generate and save a LaTeX table in booktabs format for single plot data.
    
    This function converts a simple two-column dataset (similar to a 2-column matrix
    in MATLAB or a struct in C) into a nicely formatted LaTeX table using the booktabs style.
    """
    import os
    import numpy as np
    import pandas as pd

    # Create DataFrame from the x and y data
    df = pd.DataFrame({'x': d["data"]["x"], 'y': d["data"]["y"]})
    
    # Optionally reduce the number of rows for display purposes
    num_rows = len(df)
    if num_rows > MAX_ROWS:
        indices = np.linspace(0, num_rows - 1, MAX_ROWS, dtype=int)
        df = df.iloc[indices]
    
    df = df.round(1).fillna('-')

    # Extract labels and units
    x_label, x_units = d["x_label"], d["x_units"]
    y_label, y_units = d["y_label"], d["y_units"]

    # Build the header for the table using booktabs style:
    # \toprule for the top line, \midrule for the header separator.
    table_header = rf"""\begin{{table}}[htb!]
\centering
\caption{{{y_label} {y_units} obtained for different {x_label} {x_units}}}
\label{{tab:{x_label}-{y_label}}}
\begin{{tabular}}{{@{{}}cc@{{}}}}
\toprule
{x_label} {x_units} & {y_label} {y_units} \\ \midrule
"""

    # Format each row of data from the DataFrame into LaTeX table rows
    table_rows = "\n".join([rf"{row['x']} & {row['y']} \\" for _, row in df.iterrows()])
    
    # Complete the table by adding the bottom rule
    latex_str = rf"""{table_header}{table_rows}
\bottomrule
\end{{tabular}}
\end{{table}}"""
    
    # Save LaTeX table to file
    title = f"y-{d['y_label']}_x-{d['x_label']}_table"
    filename = os.path.join(OUTDIR, f"{title}.tex")
    with open(filename, "w") as f:
        f.write(latex_str)
    
    print(f"SAVED: {filename}\n")





def main():
    for file in os.scandir(INDIR):
        if file.is_file():  # Check if it's a file
            f = ex.load_json(file)
            if f["type"] == "heatmap":
                heatmap(f)
                #heatmap_table(f)
                heatmap_table_booktabs(f)
            else:
                single_plot(f)
                #single_plot_table(f)
                single_plot_table_booktabs(f)

main()
