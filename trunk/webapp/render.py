"""Turn a sized design into the lab's visuals: dashboard figures, headline metrics, downloads.

Everything here is a thin reuse of :mod:`PhlyGreen.postprocess` (the same plotters the examples
use) plus a couple of comparison/sweep charts the GUI adds. Figures are returned (not saved); the
caller renders them with ``st.pyplot`` and closes them.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from PhlyGreen import postprocess as pp


# --- headline scalar metrics ------------------------------------------------------------------
def _fmt(v, scale=1.0, nd=0):
    if v is None:
        return "—"
    v = float(v) * scale
    return f"{v:,.{nd}f}"


def headline_metrics(results):
    """Return a list of ``(label, value_string)`` for the top metrics row.

    ``results`` is an ``AircraftResults.to_dict()`` dict.
    """
    cfg = results.get("configuration")
    fuel_label = "Hydrogen [kg]" if cfg in ("Hydrogen", "FuelCellBattery") else "Block fuel [kg]"
    metrics = [
        ("Take-off weight [kg]", _fmt(results.get("WTO"))),
        (fuel_label, _fmt(results.get("block_fuel") or results.get("Wf"))),
        ("Empty weight [kg]", _fmt(results.get("empty_weight"))),
        ("Wing area [m²]", _fmt(results.get("WingSurface"), nd=1)),
        ("Engine rating [kW]", _fmt(results.get("engineRating"), scale=1e-3)),
    ]
    if results.get("WBat"):
        metrics.append(("Battery [kg]", _fmt(results.get("WBat"))))
    if results.get("SourceEnergy"):
        metrics.append(("Source energy [MJ]", _fmt(results.get("SourceEnergy"), scale=1e-6)))
    return metrics


# --- the 4-panel design dashboard -------------------------------------------------------------
def dashboard_figure(aircraft, title=None):
    """A 2x2 dashboard (flight profile, energy/SOC, constraint diagram, mass breakdown).

    Reuses the generic ``postprocess`` helpers so it works for every configuration. Panels that
    are not applicable to a given design are hidden.
    """
    ts = pp.mission_timeseries(aircraft)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    if title:
        fig.suptitle(title, fontsize=13)

    # (0,0) altitude + true airspeed
    t_min = ts["time"] / 60.0
    ax = axes[0, 0]
    ax.plot(t_min, ts["altitude"], color="tab:blue")
    ax.set_xlabel("time [min]"); ax.set_ylabel("altitude [m]", color="tab:blue")
    axv = ax.twinx()
    axv.plot(t_min, ts["velocity"], color="tab:orange")
    axv.set_ylabel("TAS [m/s]", color="tab:orange")
    ax.set_title("Flight profile"); ax.grid(alpha=0.3)

    for (r, c), fn, ttl in (
        ((0, 1), pp.plot_energy_timeseries, "Energy / state of charge"),
        ((1, 0), pp.plot_constraint_diagram, "Constraint diagram"),
        ((1, 1), pp.plot_mass_breakdown, "Take-off mass breakdown"),
    ):
        try:
            fn(aircraft, ax=axes[r, c])
            axes[r, c].set_title(ttl)
        except Exception:
            axes[r, c].set_visible(False)

    fig.tight_layout()
    return fig


def power_figure(aircraft, title=None):
    """Mission power time-series (propulsive / gas-turbine / electric-motor)."""
    ax = pp.plot_power_timeseries(aircraft)
    if title:
        ax.set_title(title)
    fig = ax.figure
    fig.tight_layout()
    return fig


def mass_breakdown(aircraft):
    """``{component: mass_kg}`` ordered dict (for a table)."""
    return pp.mass_breakdown(aircraft)


def timeseries_csv(aircraft):
    """Return the mission time-series as an in-memory CSV string (for a download button)."""
    import csv
    import io
    header, columns = pp.timeseries_table(aircraft)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    writer.writerows(zip(*columns))
    return buf.getvalue()


# --- comparison + sweep charts ----------------------------------------------------------------
# Result keys a student can plot, with display label + unit scaling.
METRIC_OPTIONS = {
    "Take-off weight [kg]": ("WTO", 1.0),
    "Block fuel / H2 [kg]": ("block_fuel", 1.0),
    "Empty weight [kg]": ("empty_weight", 1.0),
    "Wing area [m²]": ("WingSurface", 1.0),
    "Engine rating [kW]": ("engineRating", 1e-3),
    "Battery mass [kg]": ("WBat", 1.0),
}


def comparison_figure(rows, metric_keys=("WTO", "block_fuel", "empty_weight")):
    """Grouped bar chart comparing several designs on a few headline masses.

    ``rows`` is the output of ``runner.compare`` (each row has 'label', 'ok', 'results').
    """
    ok = [r for r in rows if r["ok"]]
    labels = [r["label"] for r in ok]
    pretty = {"WTO": "Take-off", "block_fuel": "Block fuel/H2", "empty_weight": "Empty"}
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(labels))
    w = 0.8 / max(len(metric_keys), 1)
    for i, key in enumerate(metric_keys):
        vals = [(r["results"].get(key) or 0.0) for r in ok]
        ax.bar(x + i * w - 0.4 + w / 2, vals, w, label=pretty.get(key, key))
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=15, ha="right")
    ax.set_ylabel("mass [kg]"); ax.grid(axis="y", alpha=0.3); ax.legend()
    ax.set_title("Architecture comparison")
    fig.tight_layout()
    return fig


def sweep_figure(rows, knob_label, metric_label):
    """Line chart of a chosen output metric vs the swept input parameter."""
    key, scale = METRIC_OPTIONS[metric_label]
    xs = [r["x"] for r in rows if r["ok"] and r["results"].get(key) is not None]
    ys = [r["results"][key] * scale for r in rows if r["ok"] and r["results"].get(key) is not None]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(xs, ys, "o-", color="tab:red")
    ax.set_xlabel(knob_label); ax.set_ylabel(metric_label); ax.grid(alpha=0.3)
    ax.set_title(f"{metric_label}  vs  {knob_label}")
    n_fail = sum(1 for r in rows if not r["ok"])
    if n_fail:
        ax.text(0.02, 0.95, f"{n_fail} point(s) did not close", transform=ax.transAxes,
                fontsize=8, color="tab:gray", va="top")
    fig.tight_layout()
    return fig
