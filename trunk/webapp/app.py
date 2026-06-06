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
    """Render the sidebar (architecture + inputs) and return ``(arch, config, overrides)``.

    Building the config is cheap (no sizing); sizing happens only when a tab's run button is
    pressed. Widget keys are namespaced by architecture, so switching architecture resets the
    inputs to that template's baseline. ``overrides`` (the main-input values) is returned so the
    Compare tab can apply the *same* sidebar inputs to every architecture.
    """
    st.sidebar.title("✈️ Design Lab")
    arch = st.sidebar.selectbox("Propulsion architecture", templates.TEMPLATE_LABELS, key="arch")
    st.sidebar.caption(templates.template_blurb(arch))

    base = templates.make_config(arch)
    prefix = arch                              # namespace widget keys per architecture

    # Fuel-cell + battery: let the user pick the battery model (Class I energy/power, or the
    # Class-II cell-level electro-thermal model with P-number sizing).
    if arch == templates.FCB_LABEL:
        bm = st.sidebar.selectbox(
            "Battery model", ["Class I (specific energy/power)", "Class II (cell thermal)"],
            key=f"{prefix}.fcb_battmodel",
            help="Class II sizes a physics cell pack (P-number + thermal cooling); slower to run.")
        if bm.startswith("Class II"):
            base.cell = templates.fcb_class_ii_cell()

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

    return arch, cfg, overrides


# --- Design tab (owns the Run-design button; sizes only on click) -------------------------------
def design_tab(arch, cfg):
    current_key = runner.config_key(cfg)
    if st.button("▶ Run design", type="primary"):
        with st.spinner("Sizing the aircraft…"):
            aircraft, error = runner.safe_design(cfg)
        st.session_state["last_run"] = {
            "arch": arch, "key": current_key, "aircraft": aircraft, "error": error,
            "results": aircraft.results().to_dict() if aircraft is not None else None, "cfg": cfg,
        }

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
def compare_tab(overrides):
    st.markdown("Compare architectures **on the same mission — using the inputs set in the sidebar.**")
    st.caption("The sidebar **Main inputs** (range, payload, cruise, aerodynamics, battery shares, …) "
               "are applied to every architecture below. Architecture-specific inputs that don't "
               "apply to a given design are left at that template's default. Use **Run comparison** "
               "here — the **Run design** button on the Design tab sizes only the single current design.")
    picks = st.multiselect("Architectures", templates.TEMPLATE_LABELS,
                           default=templates.TEMPLATE_LABELS[:3])
    if not picks:
        st.info("Pick at least one architecture.")
        return
    if not st.button("Run comparison", type="primary"):
        return

    with st.spinner("Sizing & comparing designs…"):
        configs = [(lab, controls.apply_overrides(templates.make_config(lab), overrides))
                   for lab in picks]
        rows = runner.compare_detailed(configs)

    st.markdown("#### Summary")
    st.dataframe(render.comparison_table(rows))

    if not any(r["ok"] for r in rows):
        st.warning("No design closed — relax the shared inputs (range, payload, battery shares).")
        return

    st.markdown("#### Take-off mass breakdown")
    _show_figure(render.mass_breakdown_figure(rows))

    st.markdown("#### Energy and CO₂")
    st.caption("Well-to-wake uses **illustrative** lifecycle intensity factors (in `sustainability.py`), "
               "not a physics model — Jet-A vs SAF vs green-H₂ vs grid electricity. Change them and the "
               "ranking changes; that is the lesson.")
    _show_figure(render.energy_co2_figure(rows))

    st.markdown("#### CO₂ vs CO₂-equivalent")
    st.caption("Adds the gas-turbine **non-CO₂** effect (NOx-ozone, contrails) from the PW127 emission "
               "surrogate + the ATR climate model. Fuel-cell architectures have no combustion non-CO₂.")
    fig, notes = render.co2e_figure(rows)
    _show_figure(fig)
    for line in notes:
        st.caption(line)

    st.markdown("#### Mission profile")
    st.caption("All architectures fly the same prescribed mission, so the profile is shared.")
    ok_rows = [r for r in rows if r["ok"]]
    _show_figure(render.mission_profile_figure(ok_rows[0]))


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
    arch, cfg, overrides = build_inputs()
    st.title("Virtual Aircraft Design Lab")
    tab_design, tab_compare, tab_sweep, tab_about = st.tabs(
        ["Design", "Compare", "Sweep", "About"])
    with tab_design:
        design_tab(arch, cfg)
    with tab_compare:
        compare_tab(overrides)
    with tab_sweep:
        sweep_tab(arch, cfg)
    with tab_about:
        about_tab()


if __name__ == "__main__":
    main()
