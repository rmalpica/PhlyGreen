"""Shared paths, plotting style and helpers for the battery-manual figure scripts.

Every figure of the manual is produced by these scripts from the PhlyGreen package itself.
The numbers quoted in the text are written to ``manuals/battery/data/*.json`` next to the
figures, so that each value in the manual can be traced to one run.
"""

import json
import os
import sys
import warnings

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MANUAL = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(MANUAL))
TRUNK = os.path.join(REPO, "trunk")
EXAMPLES = os.path.join(TRUNK, "examples")
FIGURES = os.path.join(MANUAL, "figures")
DATA = os.path.join(MANUAL, "data")

for p in (TRUNK, EXAMPLES):
    if p not in sys.path:
        sys.path.insert(0, p)

os.makedirs(FIGURES, exist_ok=True)
os.makedirs(DATA, exist_ok=True)

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

# Fixed categorical order (validated reference palette of the dataviz guidelines).
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
# Sequential blue ramp (light -> dark) for ordered families (C-rates, temperatures).
SEQ = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281", "#0d366b"]
GREY = "#52514e"
INK = "#0b0b0b"

TEXTWIDTH = 6.3  # [in], a4paper with the manual's margins

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.labelsize": 9,
    "axes.titlesize": 9,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "axes.edgecolor": GREY,
    "axes.labelcolor": INK,
    "xtick.color": GREY,
    "ytick.color": GREY,
    "axes.grid": True,
    "grid.color": "#d9d8d4",
    "grid.linewidth": 0.5,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "lines.linewidth": 1.5,
    "lines.markersize": 4,
    "legend.frameon": False,
    "savefig.bbox": "tight",
    "pdf.fonttype": 42,
})


def save(fig, name):
    path = os.path.join(FIGURES, name)
    fig.savefig(path)
    plt.close(fig)
    print(f"  figure  {path}")
    return path


def _clean(obj):
    if isinstance(obj, dict):
        return {str(k): _clean(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return _clean(obj.tolist())
    return obj


def dump(name, data):
    path = os.path.join(DATA, name)
    with open(path, "w") as f:
        json.dump(_clean(data), f, indent=2)
    print(f"  data    {path}")


def design(cfg, quiet=True):
    """Size ``cfg`` with the typed-config API and return the aircraft."""
    import contextlib
    import io

    import PhlyGreen as pg
    a = pg.build_aircraft()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if quiet:   # the Class-II P-number search prints its brackets
            with contextlib.redirect_stdout(io.StringIO()):
                a.configure(cfg)
        else:
            a.configure(cfg)
    return a


def label_panel(ax, letter):
    ax.text(-0.13, 1.04, f"({letter})", transform=ax.transAxes, fontsize=9,
            fontweight="bold", va="bottom", ha="left", color=INK)
