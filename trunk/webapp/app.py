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
import sustainability


st.set_page_config(page_title="Virtual Aircraft Design Lab", layout="wide")


def _show_figure(fig):
    st.pyplot(fig)
    plt.close(fig)


_CARRIER_NAMES = {"jetA": "Jet-A", "saf": "SAF", "h2_green": "green H₂", "grid": "grid electricity"}


def _wtw_factor_inputs(container, arch, has_battery):
    """Editable **well-to-tank** factors (upstream production) for the carriers this design uses,
    rendered into ``container`` (the sidebar). The tank-to-wake (combustion) CO₂ is *not* here — it
    is fixed physics (fuel burn × CO₂ index). Returns ``(wtw_co2, ttw_co2, wtt_energy)`` overrides.
    """
    carrier = sustainability.CARRIER.get(arch, "jetA")
    carriers = [carrier] + (["grid"] if has_battery and carrier != "grid" else [])
    wtw_co2 = dict(sustainability.WTW_CO2)
    ttw_co2 = dict(sustainability.TTW_CO2)          # combustion CO₂ — physics, kept fixed
    wtt_energy = dict(sustainability.WTT_ENERGY)
    exp = container.expander("Well-to-tank factors (upstream production) — edit to explore")
    for c in carriers:
        exp.markdown(f"**{_CARRIER_NAMES.get(c, c)}**")
        eff = exp.number_input(
            "WtT energy efficiency [-]", 0.05, 1.0,
            value=round(1.0 / sustainability.WTT_ENERGY[c], 3), step=0.01, key=f"wtte_{c}",
            help="Delivered energy / primary energy consumed upstream (production + delivery).")
        wtt_energy[c] = 1.0 / max(eff, 1e-6)
        upstream = exp.number_input(
            "WtT (upstream) CO₂ [gCO₂/MJ]", 0.0, 400.0,
            value=float(sustainability.WTW_CO2[c] - sustainability.TTW_CO2[c]), step=1.0,
            key=f"wttco2_{c}")
        wtw_co2[c] = upstream + sustainability.TTW_CO2[c]   # upstream (editable) + combustion (fixed)
    return wtw_co2, ttw_co2, wtt_energy


def emissions_panel(container, arch, cfg):
    """Sidebar emissions controls. When enabled, attaches the climate model to ``cfg`` (in place) so
    the **design run itself** produces a climate-ready aircraft and the emissions come from that same
    sizing pass — no separate re-size. Returns the emissions settings used by the Design tab.
    """
    container.markdown("### Emissions / well-to-wake")
    on = container.checkbox(
        "Compute well-to-wake emissions", key="wtw_on",
        help="Attaches the climate model so the design is sized *with* emissions in one pass. "
             "Leave off for a faster design with no emissions output.")
    settings = {"on": on, "einox": "Surrogate", "wtw_co2": None, "ttw_co2": None, "wtt_energy": None}
    if not on:
        return settings

    is_gt = cfg.configuration in ("Traditional", "Hybrid")
    if is_gt:
        settings["einox"] = container.selectbox(
            "EINOx (gas-turbine emission) model", sustainability.EINOX_MODELS, key="einox_model",
            help="Surrogate: the PW127 emission-index response surface (NOx, CO, UHC). "
                 "Filippone: a NOx-only correlation.")
    has_batt = cfg.configuration in ("Hybrid", "FuelCellBattery")
    settings["wtw_co2"], settings["ttw_co2"], settings["wtt_energy"] = \
        _wtw_factor_inputs(container, arch, has_batt)

    # Attach climate to the config so designing it computes emissions directly.
    sustainability.attach_climate(cfg, settings["einox"])
    return settings


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

    # 3. emissions / well-to-wake — a sidebar input so the design is sized *with* (or without)
    # emissions directly; this mutates cfg (attaches the climate model) when enabled.
    emissions = emissions_panel(st.sidebar, arch, cfg)

    return arch, cfg, overrides, emissions


# --- Design tab (owns the Run-design button; sizes only on click) -------------------------------
def design_tab(arch, cfg, emissions):
    current_key = runner.config_key(cfg)
    if st.button("▶ Run design", type="primary"):
        with st.spinner("Sizing the aircraft…"):
            aircraft, error = runner.safe_design(cfg)
        # Emissions are computed as part of the run (from the same sized aircraft) when enabled in
        # the sidebar — so the design is sized *with* emissions in one pass, not as a later re-size.
        gt = None
        if emissions["on"] and aircraft is not None and cfg.configuration in ("Traditional", "Hybrid"):
            with st.spinner("Computing gas-turbine emissions…"):
                gt = sustainability.gt_emissions(cfg, emissions["einox"], aircraft=aircraft)
        st.session_state["last_run"] = {
            "arch": arch, "key": current_key, "aircraft": aircraft, "error": error,
            "results": aircraft.results().to_dict() if aircraft is not None else None, "cfg": cfg,
            "gt": gt,
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
    # Metrics in rows of at most 4 so the (fixed-size) metric font stays readable / unclipped
    # even in a narrow window.
    metrics = render.headline_metrics(results)
    per_row = 4
    for i in range(0, len(metrics), per_row):
        cols = st.columns(per_row)
        for col, (name, val) in zip(cols, metrics[i:i + per_row]):
            col.metric(name, val)

    _show_figure(render.dashboard_figure(aircraft, title=run["arch"]))

    # LH2 tank thermodynamic evolution (hydrogen architectures with a physics tank).
    if render.has_physics_tank(aircraft):
        st.markdown("#### LH2 tank evolution")
        st.caption("Pressure, stored hydrogen and vent flow over the mission (self-pressurisation, "
                   "venting at P_max, heater at P_min).")
        try:
            _show_figure(render.tank_figure(aircraft))
        except Exception as exc:
            st.caption(f"(tank state unavailable: {type(exc).__name__})")

    # Well-to-wake emissions — switched on (and configured) in the sidebar, so the design was sized
    # with the climate model attached and these come from that same run (no re-size here).
    if emissions["on"]:
        st.markdown("#### Well-to-wake emissions")
        st.caption("Illustrative lifecycle factors (`sustainability.py`) — Jet-A / green-H₂ / grid "
                   "electricity — split into **well-to-tank** (upstream production) and "
                   "**tank-to-wake** (onboard use). CO₂e adds the gas-turbine non-CO₂ effect from "
                   "the emission surrogate.")
        is_gt = results.get("configuration") in ("Traditional", "Hybrid")
        # The gas turbine's combustion pollutants were computed during the run (from the sized
        # aircraft's mission solution); fuel-cell architectures have no combustion emissions.
        gt = run.get("gt") or {"nox": None, "co": None, "uhc": None, "nonco2": 0.0}
        wb = sustainability.wtw_breakdown(
            run["arch"], aircraft, cfg, wtw_co2=emissions["wtw_co2"], ttw_co2=emissions["ttw_co2"],
            wtt_energy=emissions["wtt_energy"], nonco2=gt["nonco2"])

        if is_gt:
            st.markdown("##### Gas-turbine mission emissions (combustion, tank-to-wake)")
            e = st.columns(4)
            e[0].metric("CO₂ [kg]", f"{wb['ttw_co2']:,.0f}")
            e[1].metric("NOx [kg]", f"{gt['nox']:,.1f}" if gt["nox"] is not None else "—")
            e[2].metric("CO [kg]", f"{gt['co']:,.1f}" if gt["co"] is not None else "—")
            e[3].metric("UHC [kg]", f"{gt['uhc']:,.2f}" if gt["uhc"] is not None else "—")

        st.markdown("##### Well-to-wake totals")
        c1, c2, c3 = st.columns(3)
        c1.metric("WTW energy [MJ]", f"{wb['wtw_MJ']:,.0f}")
        c2.metric("WTW CO₂ [kg]", f"{wb['wtw_co2']:,.0f}")
        c3.metric("WTW CO₂e [kg]", f"{wb['wtw_co2e']:,.0f}")
        st.dataframe(render.wtw_table(wb))
        _show_figure(render.wtw_figure(wb))

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
          motor efficiency models, battery & weight class, aircraft type, …).
        - **Emissions / well-to-wake** (sidebar) — switch it on to size the design *with* emissions in
          one pass (pick the NOₓ model and edit the well-to-tank lifecycle factors); leave it off for
          a faster design with no emissions output.
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
    arch, cfg, overrides, emissions = build_inputs()
    st.title("Virtual Aircraft Design Lab")
    tab_design, tab_compare, tab_sweep, tab_about = st.tabs(
        ["Design", "Compare", "Sweep", "About"])
    with tab_design:
        design_tab(arch, cfg, emissions)
    with tab_compare:
        compare_tab(overrides)
    with tab_sweep:
        sweep_tab(arch, cfg)
    with tab_about:
        about_tab()


if __name__ == "__main__":
    main()
