"""Virtual Aircraft Design Lab — a Streamlit GUI over PhlyGreen.

A teaching front-end for a Sustainable Propulsion course: pick a propulsion architecture, tune the
inputs (a curated set up front, *every* parameter and model choice under "Advanced", and an
editable constraint diagram), then press **Run design** to size the aircraft and inspect it —
or compare architectures and sweep a parameter for a trade study.

The app is a *thin wrapper*: it builds typed ``AircraftConfig``s and calls the public ``PhlyGreen``
design + postprocess API. The package itself is unchanged.

Run it (from the repo root, after ``pip install -e ./trunk`` and
``pip install -r trunk/webapp/requirements.txt``):

    streamlit run trunk/webapp/app.py
"""

import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import streamlit as st

import templates
import controls
import advanced
import runner
import render


st.set_page_config(page_title="Virtual Aircraft Design Lab", layout="wide")


def _show_figure(fig):
    st.pyplot(fig)
    plt.close(fig)


# --- sidebar: architecture, Run button, all inputs ---------------------------------------------
def build_inputs():
    """Render the sidebar (architecture + inputs) and return ``(arch, config, run_clicked)``.

    Building the config is cheap (no sizing); the design is only run when ``run_clicked`` is True.
    Widget keys are namespaced by architecture, so switching architecture resets the inputs to that
    template's baseline.
    """
    st.sidebar.title("✈️ Design Lab")
    arch = st.sidebar.selectbox("Propulsion architecture", templates.TEMPLATE_LABELS, key="arch")
    run_clicked = st.sidebar.button("▶ Run design", type="primary", use_container_width=True)
    st.sidebar.caption(templates.template_blurb(arch))

    base = templates.make_config(arch)
    prefix = arch                              # namespace widget keys per architecture

    # 1. curated "main" inputs
    st.sidebar.markdown("### Main inputs")
    overrides = {}
    for knob in controls.knobs_for(base):
        overrides[knob.key] = st.sidebar.slider(
            knob.label, float(knob.lo), float(knob.hi), float(knob.value(base)),
            step=float(knob.step), help=knob.help or None, key=f"{prefix}.knob.{knob.key}")
    cfg = controls.apply_overrides(templates.clone(base), overrides)

    # 2. advanced: every parameter + model choice, then the editable constraint diagram
    advanced.render_advanced(st.sidebar, cfg, prefix)
    advanced.render_constraints(st.sidebar, cfg.constraints, prefix)

    return arch, cfg, run_clicked


# --- Design tab (renders the last run; never sizes on its own) ----------------------------------
def design_tab(current_key):
    run = st.session_state.get("last_run")
    if not run:
        st.info("Set your inputs in the sidebar, then press **▶ Run design**.")
        return
    if run["key"] != current_key:
        st.warning("Inputs changed since the last run — press **▶ Run design** to update the results.")
    if run["error"]:
        st.error(run["error"])
        return

    aircraft, results, cfg = run["aircraft"], run["results"], run["cfg"]
    cols = st.columns(len(render.headline_metrics(results)))
    for col, (name, val) in zip(cols, render.headline_metrics(results)):
        col.metric(name, val)

    _show_figure(render.dashboard_figure(aircraft, title=run["arch"]))

    with st.expander("Mission power & mass detail"):
        _show_figure(render.power_figure(aircraft, title="Mission power"))
        st.write({k: round(v, 1) for k, v in render.mass_breakdown(aircraft).items()})

    st.markdown("### Downloads")
    d1, d2, d3 = st.columns(3)
    d1.download_button("Config (JSON)", json.dumps(templates.config_to_dict(cfg), indent=2,
                       default=str), "design_config.json", "application/json")
    d2.download_button("Results (JSON)", json.dumps(results, indent=2, default=str),
                       "design_results.json", "application/json")
    try:
        d3.download_button("Time series (CSV)", render.timeseries_csv(aircraft),
                           "mission_timeseries.csv", "text/csv")
    except Exception:
        d3.caption("(time series unavailable)")


# --- Compare tab --------------------------------------------------------------------------------
def compare_tab():
    st.markdown("Compare architectures **on the same mission** (shared range & payload).")
    picks = st.multiselect("Architectures", templates.TEMPLATE_LABELS,
                           default=templates.TEMPLATE_LABELS[:3])
    c1, c2 = st.columns(2)
    rng = c1.number_input("Range [nm]", 200, 1500, 750, step=10)
    pay = c2.number_input("Payload [kg]", 1000, 7000, 4560, step=50)
    if not picks:
        st.info("Pick at least one architecture.")
        return
    if not st.button("Run comparison", type="primary"):
        return

    shared = {"range": rng, "payload": pay}
    with st.spinner("Sizing designs…"):
        configs = [(lab, controls.apply_overrides(templates.make_config(lab), shared))
                   for lab in picks]
        rows = runner.compare(configs)

    _show_figure(render.comparison_figure(rows))
    st.dataframe({
        "architecture": [r["label"] for r in rows],
        "WTO [kg]": [round(r["results"]["WTO"], 1) if r["ok"] else None for r in rows],
        "block fuel/H2 [kg]": [round(r["results"].get("block_fuel") or 0, 1) if r["ok"] else None for r in rows],
        "empty [kg]": [round(r["results"]["empty_weight"], 1) if r["ok"] else None for r in rows],
        "status": ["ok" if r["ok"] else r["error"] for r in rows],
    })


# --- Sweep tab ----------------------------------------------------------------------------------
def sweep_tab(arch, cfg):
    st.markdown(f"Sweep one input of the **{arch}** design (current sidebar values are the baseline).")
    knobs = controls.knobs_for(cfg)
    knob = st.selectbox("Parameter to sweep", knobs, format_func=lambda k: k.label)
    metric_label = st.selectbox("Output metric", list(render.METRIC_OPTIONS))
    c1, c2, c3 = st.columns(3)
    lo = c1.number_input("from", value=float(knob.lo), step=float(knob.step))
    hi = c2.number_input("to", value=float(knob.hi), step=float(knob.step))
    n = c3.number_input("points", 3, 40, 12, step=1)
    if not st.button("Run sweep", type="primary"):
        return

    import numpy as np
    values = np.linspace(lo, hi, int(n))
    prog = st.progress(0.0, text="Sizing…")
    rows = []
    for i, x in enumerate(values):
        rows.extend(runner.sweep(cfg, knob, [x]))
        prog.progress((i + 1) / len(values))
    prog.empty()

    _show_figure(render.sweep_figure(rows, knob.label, metric_label))
    key, scale = render.METRIC_OPTIONS[metric_label]
    st.dataframe({
        knob.label: [r["x"] for r in rows],
        metric_label: [round(r["results"][key] * scale, 2) if (r["ok"] and r["results"].get(key) is not None) else None for r in rows],
        "status": ["ok" if r["ok"] else "did not close" for r in rows],
    })


def about_tab():
    st.markdown(
        """
        ### Virtual Aircraft Design Lab
        A teaching front-end over **PhlyGreen** for the *Sustainable Propulsion* course.

        - **Main inputs** (sidebar) — the handful of parameters you tune most.
        - **⚙️ Advanced inputs** — *every* parameter and **model choice** (gas-turbine / propeller /
          motor efficiency models, NOₓ model, battery & weight class, aircraft type, …).
        - **📐 Constraint analysis** — the editable sizing requirements; change a point and re-run to
          watch the design point move on the constraint diagram.

        Nothing is sized until you press **▶ Run design** — changing an input no longer re-runs the
        design automatically. Each design solves the take-off-weight convergence loop (~1 s). Inputs
        that push a design too hard simply report *"did not close"* — relax the range, payload, or
        battery/fuel-cell assumptions.

        *This GUI only wraps the public PhlyGreen API; the toolkit itself is unchanged.*
        """
    )


def main():
    arch, cfg, run_clicked = build_inputs()
    if run_clicked:
        with st.spinner("Sizing the aircraft…"):
            aircraft, error = runner.safe_design(cfg)
        st.session_state["last_run"] = {
            "arch": arch, "key": runner.config_key(cfg), "aircraft": aircraft, "error": error,
            "results": aircraft.results().to_dict() if aircraft is not None else None, "cfg": cfg,
        }

    st.title("Virtual Aircraft Design Lab")
    tab_design, tab_compare, tab_sweep, tab_about = st.tabs(
        ["Design", "Compare", "Sweep", "About"])
    with tab_design:
        design_tab(runner.config_key(cfg))
    with tab_compare:
        compare_tab()
    with tab_sweep:
        sweep_tab(arch, cfg)
    with tab_about:
        about_tab()


if __name__ == "__main__":
    main()
