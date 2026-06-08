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
    # Class-II battery: show the cell pack configuration and its specific energy explicitly.
    if results.get("S_number") and results.get("P_number"):
        metrics.append(("Battery cells", f"S{results['S_number']:.0f}/P{results['P_number']:.0f}"))
        if results.get("pack_energy") and results.get("WBat"):
            metrics.append(("Cell [Wh/kg]", _fmt(results["pack_energy"] / results["WBat"])))
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


def has_physics_tank(aircraft):
    """True if the design carries a physics LH2 tank whose state can be tracked."""
    tank = getattr(aircraft, "tank", None)
    return tank is not None and hasattr(tank, "time_step")


def tank_figure(aircraft):
    """LH2 tank thermodynamic evolution (pressure, stored mass, vent flow) over the mission."""
    pp.compute_tank_history(aircraft)
    axes = pp.plot_tank_state(aircraft)
    fig = axes[0].figure
    axes[0].set_title("LH2 tank state over the mission")
    fig.tight_layout()
    return fig


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


def wtw_table(b):
    """Well-to-wake breakdown as a WTT / TTW / total table (dict-of-columns for ``st.dataframe``)."""
    rnd = lambda x: round(x)
    return {
        "stage": ["Well-to-tank (upstream)", "Tank-to-wake (onboard)", "Well-to-wake (total)"],
        "energy [MJ]": [rnd(b["wtt_MJ"]), rnd(b["ttw_MJ"]), rnd(b["wtw_MJ"])],
        "CO₂ [kg]": [rnd(b["wtt_co2"]), rnd(b["ttw_co2"]), rnd(b["wtw_co2"])],
        "CO₂e [kg]": [rnd(b["wtt_co2e"]), rnd(b["ttw_co2e"]), rnd(b["wtw_co2e"])],
    }


def wtw_figure(b):
    """Well-to-wake energy and CO₂/CO₂e, stacked into well-to-tank and tank-to-wake parts."""
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.4))
    a1.bar(["energy"], [b["ttw_MJ"]], color="tab:cyan", label="tank-to-wake (used)")
    a1.bar(["energy"], [b["wtt_MJ"]], bottom=[b["ttw_MJ"]], color="tab:blue", label="well-to-tank (production)")
    a1.set_ylabel("energy [MJ]"); a1.set_title("Well-to-wake energy")
    a1.legend(fontsize=8); a1.grid(axis="y", alpha=0.3)

    x = ["CO₂", "CO₂e"]
    comb = [b["ttw_co2"], b["ttw_co2"]]                     # tank-to-wake combustion CO₂
    wtt = [b["wtt_co2"], b["wtt_co2"]]                      # well-to-tank upstream CO₂
    nonco2 = [0.0, b["nonco2"]]                             # GT non-CO₂ (CO₂e only)
    a2.bar(x, comb, color="tab:olive", label="TTW combustion CO₂")
    a2.bar(x, wtt, bottom=comb, color="tab:gray", label="WTT upstream CO₂")
    a2.bar(x, nonco2, bottom=[comb[i] + wtt[i] for i in range(2)], color="tab:red", label="GT non-CO₂")
    a2.set_ylabel("mass [kg]"); a2.set_title("Well-to-wake CO₂ / CO₂-equivalent")
    a2.legend(fontsize=8); a2.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


def comparison_table(rows):
    """A wide summary table (one row per architecture) as a dict-of-columns for ``st.dataframe``."""
    out = {k: [] for k in ("architecture", "WTO [kg]", "OEW [kg]", "fuel/H₂ [kg]", "battery [kg]",
                           "H₂ tank [kg]", "wing [m²]", "engine [kW]", "onboard [MJ]", "WtW [MJ]",
                           "WtW CO₂ [kg]", "CO₂e [kg]", "status")}
    for r in rows:
        out["architecture"].append(r["label"])
        if not r["ok"]:
            for k in list(out)[1:-1]:
                out[k].append(None)
            out["status"].append((r["error"] or "did not close")[:40])
            continue
        res = r["results"]
        out["WTO [kg]"].append(round(res["WTO"]))
        out["OEW [kg]"].append(round(res.get("empty_weight") or 0))
        out["fuel/H₂ [kg]"].append(round(res.get("block_fuel") or res.get("Wf") or 0))
        out["battery [kg]"].append(round(res.get("WBat") or 0))
        out["H₂ tank [kg]"].append(round(r["breakdown"].get("H2 tank", 0.0)))
        out["wing [m²]"].append(round(res.get("WingSurface") or 0, 1))
        out["engine [kW]"].append(round((res.get("engineRating") or 0) / 1000))
        out["onboard [MJ]"].append(round(r["onboard_MJ"]))
        out["WtW [MJ]"].append(round(r["wtw_MJ"]))
        out["WtW CO₂ [kg]"].append(round(r["co2_kg"]))
        out["CO₂e [kg]"].append(round(r["co2_kg"] + r["nonco2_kg"]))
        out["status"].append("ok")
    return out


def mass_breakdown_figure(rows):
    """Stacked take-off mass breakdown per architecture; black ticks mark WTO (the bars sum to it)."""
    import matplotlib.cm as cm
    ok = [r for r in rows if r["ok"]]
    names = [r["label"] for r in ok]
    comps = []
    for r in ok:
        for k in r["breakdown"]:
            if k not in comps:
                comps.append(k)
    colors = cm.tab20(np.linspace(0, 1, max(len(comps), 1)))
    fig, ax = plt.subplots(figsize=(10, 5.5))
    bottoms = np.zeros(len(names))
    for i, c in enumerate(comps):
        vals = np.array([r["breakdown"].get(c, 0.0) for r in ok])
        ax.bar(names, vals, bottom=bottoms, label=c, color=colors[i])
        bottoms += vals
    ax.scatter(range(len(names)), [r["results"]["WTO"] for r in ok], marker="_", s=900,
               color="black", linewidth=2, zorder=5, label="WTO")
    ax.set_ylabel("mass [kg]"); ax.set_title("Take-off mass breakdown (sums to WTO)")
    ax.tick_params(axis="x", rotation=15)
    ax.legend(ncol=4, fontsize=8); ax.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


def energy_co2_figure(rows):
    """Two panels: onboard vs well-to-wake energy, and well-to-wake CO₂ (illustrative factors)."""
    ok = [r for r in rows if r["ok"]]
    labels = [r["label"] for r in ok]
    x = np.arange(len(labels)); w = 0.38
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(13, 4.8))
    a1.bar(x - w / 2, [r["onboard_MJ"] for r in ok], w, label="onboard (tank-to-wake)", color="tab:cyan")
    a1.bar(x + w / 2, [r["wtw_MJ"] for r in ok], w, label="well-to-wake (incl. production)", color="tab:blue")
    a1.set_xticks(x); a1.set_xticklabels(labels, rotation=20, ha="right")
    a1.set_ylabel("energy [MJ]"); a1.set_title("Energy: onboard vs well-to-wake")
    a1.grid(axis="y", alpha=0.3); a1.legend(fontsize=8)
    a2.bar(labels, [r["co2_kg"] for r in ok], color="tab:olive")
    a2.set_ylabel("well-to-wake CO₂ [kg]"); a2.set_title("Well-to-wake CO₂")
    a2.tick_params(axis="x", rotation=20); a2.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    return fig


def co2e_figure(rows):
    """CO₂ vs CO₂-equivalent (+ gas-turbine non-CO₂). Returns ``(fig, notes)``."""
    ok = [r for r in rows if r["ok"]]
    labels = [r["label"] for r in ok]
    co2 = np.array([r["co2_kg"] for r in ok])
    co2e = co2 + np.array([r["nonco2_kg"] for r in ok])
    x = np.arange(len(labels)); w = 0.38
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.bar(x - w / 2, co2, w, label="well-to-wake CO₂", color="tab:olive")
    ax.bar(x + w / 2, co2e, w, label="CO₂-equivalent (+ GT non-CO₂)", color="tab:red")
    ax.set_xticks(x); ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel("mission [kg]")
    ax.set_title("CO₂ vs CO₂-equivalent (non-CO₂ from the PW127 emission surrogate)")
    ax.grid(axis="y", alpha=0.3); ax.legend()
    notes = [f"{n}: CO₂ {c:,.0f} → CO₂e {ce:,.0f} kg ({100 * (ce / c - 1):+.1f}% from GT non-CO₂)"
             for n, c, ce in zip(labels, co2, co2e) if c > 0]
    fig.tight_layout()
    return fig, notes


def mission_profile_figure(row):
    """THE mission profile (altitude + TAS vs time) — the same prescribed mission all designs fly."""
    ts = row["timeseries"]
    t = np.asarray(ts["time"]) / 60.0
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(t, np.asarray(ts["altitude"]), color="tab:blue")
    ax.set_xlabel("time [min]"); ax.set_ylabel("altitude [m]", color="tab:blue")
    ax.tick_params(axis="y", labelcolor="tab:blue")
    axv = ax.twinx()
    axv.plot(t, np.asarray(ts["velocity"]), color="tab:orange")
    axv.set_ylabel("TAS [m/s]", color="tab:orange")
    axv.tick_params(axis="y", labelcolor="tab:orange")
    ax.set_title("Mission profile (shared by all architectures)")
    ax.grid(alpha=0.3)
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
