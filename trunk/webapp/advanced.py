"""Advanced input forms: expose *every* config field (and the model choices), plus an editable
constraint diagram.

The Design tab's sidebar shows a curated set of "main inputs" (``controls.KNOBS``). This module
adds the rest: a reflection-based form over each typed config section (so new config fields show
up automatically), with selectboxes for the enum-like *model* fields, and a dedicated editor for
the 8-point constraint diagram. Everything mutates the working config in place; the caller sizes
the design only when the Run button is pressed.

No ``streamlit`` import here — the Streamlit container is passed in, so these functions stay thin.
"""

import dataclasses


# Enum-like (model / class / type) fields -> their allowed values. Rendered as selectboxes.
ENUMS = {
    "eta_gas_turbine_model": ["constant", "ResponseSurface"],
    "eta_propulsive_model": ["constant", "Hamilton", "Surrogate"],
    "eta_electric_motor_model": ["constant", "Smart"],
    "einox_model": ["Filippone", "Surrogate", "unset"],
    "cell_class": ["I", "II"],
}

# Fields already controlled by the main-input sliders (controls.KNOBS) — skip in the advanced
# form so a value is never driven by two widgets at once.
_EXCLUDE = {
    "mission": {"range_mission", "payload_weight"},
    "aerodynamics": {"cd0", "analytic_polar", "numerical_polar"},
    "energy": {"eta_propulsive", "eta_gas_turbine", "v_cell_design",
               "stack_power_density", "battery_specific_energy"},
    "cell": {"specific_energy"},
}

# Order + labels of the sections shown in the advanced panel.
_SECTIONS = [
    ("Mission", "mission"),
    ("Aerodynamics", "aerodynamics"),
    ("Energy / powertrain (incl. models)", "energy"),
    ("Battery cell", "cell"),
    ("Well-to-tank", "well_to_tank"),
    ("Climate impact", "climate_impact"),
    ("LH₂ tank", "tank"),
]


def _label(section, name):
    return getattr(type(section), "_KEY_MAP", {}).get(name, name.replace("_", " "))


def render_section(c, section, prefix, exclude=()):
    """Render an editable widget for every scalar field of a config dataclass, mutating it."""
    for f in dataclasses.fields(section):
        name = f.name
        if name in exclude or name.startswith("_"):
            continue
        val = getattr(section, name)
        key = f"{prefix}.{name}"
        label = _label(section, name)

        if name in ENUMS:
            opts = ENUMS[name]
            cur = val if val in opts else opts[0]
            setattr(section, name, c.selectbox(label, opts, index=opts.index(cur), key=key))
        elif isinstance(val, bool):
            setattr(section, name, c.checkbox(label, value=val, key=key))
        elif isinstance(val, int):                       # bool already handled above
            setattr(section, name, int(c.number_input(label, value=int(val), step=1, key=key)))
        elif isinstance(val, float):
            setattr(section, name, c.number_input(label, value=float(val), key=key))
        elif isinstance(val, str):
            setattr(section, name, c.text_input(label, value=val, key=key))
        elif isinstance(val, (list, tuple)) and all(isinstance(x, (int, float)) for x in val):
            s = c.text_input(label + " (comma-sep)", value=", ".join(str(x) for x in val), key=key)
            try:
                parsed = [float(x) for x in s.split(",") if x.strip()]
                if parsed:
                    setattr(section, name, parsed)
            except ValueError:
                pass
        elif val is None:                                # optional, unset -> blank text box
            s = c.text_input(label + " (optional)", value="", key=key)
            if s.strip():
                try:
                    setattr(section, name, float(s))
                except ValueError:
                    setattr(section, name, s)
        # dicts / other complex fields are handled specially (aero polar below) or left alone.


def render_flags(c, cfg, prefix):
    """Top-level configuration flags and the global model/structure choices."""
    cls = ["I", "II"]
    cfg.weight_class = c.selectbox(
        "Weight model (Class)", cls, index=cls.index(cfg.weight_class or "I"),
        key=f"{prefix}.weight_class",
        help="I = regression structural model. II = FLOPS component masses (needs a FLOPS input "
             "block, which the lab templates do not provide — leave on I unless you supply one).")
    types = ["ATR", "DO228", "Jet", "TwinTP"]
    cfg.aircraft_type = c.selectbox(
        "Aircraft type (Class-I structure)", types,
        index=types.index(cfg.aircraft_type) if cfg.aircraft_type in types else 0,
        key=f"{prefix}.aircraft_type")
    if cfg.configuration == "Hybrid":
        ht = ["Parallel", "Serial"]
        cfg.hybrid_type = c.selectbox(
            "Hybrid type", ht, index=ht.index(cfg.hybrid_type) if cfg.hybrid_type in ht else 0,
            key=f"{prefix}.hybrid_type")
    cur = cfg.design_wing_loading
    s = c.text_input("Design wing loading W/S [N/m²] (optional, blank = optimise)",
                     value="" if cur is None else str(cur), key=f"{prefix}.dwl")
    cfg.design_wing_loading = float(s) if s.strip() else None


def render_advanced(container, cfg, prefix):
    """Render the whole advanced panel (flags + every section) into ``container`` (the sidebar)."""
    container.markdown("### ⚙️ Advanced inputs")
    container.caption("Every parameter and model choice. Edit, then press **Run design**.")

    flags = container.expander("Configuration & model choices")
    render_flags(flags, cfg, prefix)

    for title, attr in _SECTIONS:
        section = getattr(cfg, attr, None)
        if section is None:
            continue
        exp = container.expander(title)
        render_section(exp, section, f"{prefix}.{attr}", exclude=_EXCLUDE.get(attr, ()))
        if attr == "aerodynamics":
            _render_polar(exp, section, prefix)


def _render_polar(exp, aero, prefix):
    """The quadratic drag polar's Oswald efficiency lives inside the analytic_polar dict."""
    ap = getattr(aero, "analytic_polar", None)
    if ap and isinstance(ap.get("input"), dict) and "e_osw" in ap["input"]:
        ap["input"]["e_osw"] = exp.number_input(
            "Oswald efficiency e [-]", value=float(ap["input"]["e_osw"]),
            key=f"{prefix}.aero.e_osw")


def render_constraints(container, constraints, prefix):
    """Editable constraint diagram: DISA + every phase point. Edit and re-run to move the design point."""
    exp = container.expander("📐 Constraint analysis (editable)")
    exp.caption("The sizing requirements. Change a point (speed, altitude, gradient, …) and press "
                "**Run design** to see the design point move on the constraint diagram.")
    constraints.disa = exp.number_input("DISA — ISA temperature offset [°C]",
                                        value=float(constraints.disa), key=f"{prefix}.disa")
    for phase, params in constraints.phases.items():
        exp.markdown(f"**{phase}**")
        for k in list(params.keys()):
            v = params[k]
            wkey = f"{prefix}.{phase}.{k}"
            if k == "Speed Type":
                opts = ["Mach", "KCAS", "TAS"]
                cur = v if v in opts else opts[0]
                params[k] = exp.selectbox(k, opts, index=opts.index(cur), key=wkey)
            elif isinstance(v, bool):
                params[k] = exp.checkbox(k, value=v, key=wkey)
            elif isinstance(v, (int, float)):
                params[k] = exp.number_input(k, value=float(v), key=wkey)
            else:
                params[k] = exp.text_input(k, value=str(v), key=wkey)
