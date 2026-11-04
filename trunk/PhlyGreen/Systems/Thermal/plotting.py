"""Figures for the Class-II thermal-management system.

- :func:`draw_hex` — to-scale drawing of ONE sized heat-exchanger unit (front cross-section,
  side/top view and a summary), for the three families of :mod:`.hex`.
- :func:`plot_tms_rating` — heat to reject vs capacity of a sized TMS at every mission point.

matplotlib is imported inside the functions, so the package does not require it.
"""

import math


def _summary_lines(design, n_parallel=None):
    g = design.geometry
    lines = [f"family: {design.family.replace('_', ' ')}",
             f"duty per unit: {design.q / 1e3:.1f} kW",
             f"area A (gas side): {design.A:.2f} m²",
             f"U: {design.U:.0f} W/m²K",
             f"mass: {design.weight:.1f} kg",
             f"volume: {design.volume * 1e3:.1f} L",
             f"Δp liquid: {design.dP_hot / 1e3:.1f} kPa",
             f"Δp gas: {design.dP_cold:.0f} Pa",
             f"gas velocity in core: {design.v_cold:.1f} m/s"]
    if n_parallel:
        lines.insert(0, f"{n_parallel} identical unit(s) in parallel")
    if design.family != "plate_fin":
        lines += [f"tubes: {g['n_tubes']} ({g['n_per_row']} per row x {g['n_rows']} rows)",
                  f"tube d_o: {g['d_o'] * 1e3:.1f} mm, length {g['L'] * 1e3:.0f} mm",
                  f"coolant circuits: {g['n_circuits']}"]
        if design.family == "finned_tube_bank":
            lines.append(f"fins: {g['fin_density']:.0f}/m, height {g['fin_height'] * 1e3:.0f} mm")
    else:
        lines += [f"layers: {g['n_layers']}, width {g['width'] * 1e3:.0f} mm",
                  f"flow length: {g['L_flow'] * 1e3:.0f} mm",
                  f"fin pitch {g['fin_pitch'] * 1e3:.1f} mm, height {g['fin_height'] * 1e3:.0f} mm",
                  f"liquid gap: {g['gap_h'] * 1e3:.2f} mm"]
    return lines


def _draw_tube_bank(design, ax_front, ax_side, max_show=10):
    from matplotlib.patches import Circle, Rectangle
    g = design.geometry
    d_o, S_T = g["d_o"] * 1e3, g["S_T"] * 1e3
    D_fin = (g["d_o"] + 2 * g.get("fin_height", 0.0)) * 1e3
    n_row_show = min(g["n_per_row"], max_show)
    n_depth_show = min(g["n_rows"], max_show)
    # front view: cross-section normal to the tubes; gas flows left -> right through the depth
    for i in range(n_depth_show):
        for j in range(n_row_show):
            x = (i + 0.5) * S_T
            y = (j + 0.5 + (0.5 if i % 2 else 0.0)) * S_T
            if D_fin > d_o:
                ax_front.add_patch(Circle((x, y), D_fin / 2, fc="#cfe3f3", ec="#4a7fb0", lw=0.6))
            ax_front.add_patch(Circle((x, y), d_o / 2, fc="#9a9a9a", ec="k", lw=0.6))
    w, h = n_depth_show * S_T, (n_row_show + 0.5) * S_T
    ax_front.annotate("", xy=(w * 0.75, -0.12 * h), xytext=(w * 0.05, -0.12 * h),
                      arrowprops=dict(arrowstyle="->", color="tab:blue"))
    ax_front.text(w * 0.8, -0.12 * h, "gas", color="tab:blue", ha="left", va="center")
    trunc = (g["n_per_row"] > max_show) or (g["n_rows"] > max_show)
    ax_front.set_title("front cross-section" + (" (detail)" if trunc else ""))
    ax_front.set_xlim(-0.05 * w, 1.05 * w)
    ax_front.set_ylim(-0.25 * h, (n_row_show + 1.0) * S_T)
    ax_front.set_xlabel("depth [mm]")
    ax_front.set_ylabel("face height [mm]")
    # side view: one row of tubes of length L, fins as ticks, face height and length to scale
    L = g["L"] * 1e3
    H = g["n_per_row"] * S_T
    ax_side.add_patch(Rectangle((0, 0), L, H, fc="#eef4fa", ec="k", lw=0.8))
    n_lines = min(g["n_per_row"], 25)
    for j in range(n_lines):
        y = (j + 0.5) * H / n_lines
        ax_side.plot([0, L], [y, y], color="#7a7a7a", lw=0.8)
    if design.family == "finned_tube_bank":
        pitch = 1e3 / g["fin_density"]
        step = max(1, int(math.ceil(L / pitch / 60)))         # draw at most ~60 fins
        for k in range(0, int(L / pitch), step):
            ax_side.plot([k * pitch] * 2, [0, H], color="#4a7fb0", lw=0.3, alpha=0.6)
    ax_side.set_title(f"face: {L:.0f} mm (tube length) x {H:.0f} mm")
    ax_side.set_xlim(-0.05 * L, 1.05 * L)
    ax_side.set_ylim(-0.05 * H, 1.1 * H)
    ax_side.set_xlabel("tube length [mm]")
    ax_side.set_ylabel("face height [mm]")


def _draw_plate_fin(design, ax_front, ax_side, max_layers=6):
    from matplotlib.patches import Rectangle
    g = design.geometry
    w, s, hf = g["width"] * 1e3, g["fin_pitch"] * 1e3, g["fin_height"] * 1e3
    gap, tp = g["gap_h"] * 1e3, 0.5
    n_show = min(g["n_layers"], max_layers)
    y = 0.0
    w_show = min(w, 30 * s)                               # detail of the width
    for _ in range(n_show):
        ax_front.add_patch(Rectangle((0, y), w_show, tp, fc="0.4", ec="none")); y += tp
        xs, ys, x = [], [], 0.0                            # square-wave fin (gas layer)
        while x < w_show:
            xs += [x, x, x + s / 2, x + s / 2]
            ys += [y, y + hf, y + hf, y]
            x += s
        ax_front.fill_between([0, w_show], y, y + hf, color="#e6f0f8")
        ax_front.plot(xs, ys, color="#4a7fb0", lw=0.8); y += hf
        ax_front.add_patch(Rectangle((0, y), w_show, tp, fc="0.4", ec="none")); y += tp
        ax_front.add_patch(Rectangle((0, y), w_show, gap, fc="#f6d9c6", ec="none")); y += gap
    ax_front.set_xlim(-0.02 * w_show, 1.02 * w_show)
    ax_front.set_ylim(-0.05 * y, 1.05 * y)
    ax_front.set_title(f"layer stack (detail: {n_show} of {g['n_layers']} layers)")
    ax_front.set_xlabel("width [mm]")
    ax_front.set_ylabel("height [mm]")
    ax_front.text(0.98, 0.02, "blue: gas fins   orange: liquid channel", transform=ax_front.transAxes,
                  ha="right", va="bottom", fontsize=8)
    # top view: core w x L_flow, counterflow arrows
    L = g["L_flow"] * 1e3
    ax_side.add_patch(Rectangle((0, 0), L, w, fc="#eef4fa", ec="k", lw=0.8))
    ax_side.annotate("", xy=(0.9 * L, 0.7 * w), xytext=(0.1 * L, 0.7 * w),
                     arrowprops=dict(arrowstyle="->", color="tab:blue"))
    ax_side.text(0.5 * L, 0.75 * w, "gas", color="tab:blue", ha="center")
    ax_side.annotate("", xy=(0.1 * L, 0.3 * w), xytext=(0.9 * L, 0.3 * w),
                     arrowprops=dict(arrowstyle="->", color="tab:red"))
    ax_side.text(0.5 * L, 0.18 * w, "liquid (counterflow)", color="tab:red", ha="center")
    ax_side.set_title(f"top view: {L:.0f} mm x {w:.0f} mm, height {g['n_layers'] * (hf + gap + 2 * tp):.0f} mm")
    ax_side.set_xlim(-0.05 * L, 1.05 * L)
    ax_side.set_ylim(-0.05 * w, 1.1 * w)
    ax_side.set_xlabel("flow length [mm]")
    ax_side.set_ylabel("width [mm]")


def draw_hex(design, n_parallel=None, title=None):
    """Draw one sized heat-exchanger unit (a :class:`~.hex.HEX_Design`) to scale.

    Three panels: the front cross-section (tube pattern with fins, or the plate-fin layer
    stack), the side/top view with the core dimensions, and a summary of the design.
    Large cores are shown as a detail (the titles say so). Returns the figure.
    """
    import matplotlib.pyplot as plt
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(15, 4.6),
                                     gridspec_kw={"width_ratios": [1.1, 1.3, 0.8]})
    if design.family == "plate_fin":
        _draw_plate_fin(design, a1, a2)
    else:
        _draw_tube_bank(design, a1, a2)
    for a in (a1, a2):
        a.set_aspect("equal", adjustable="box")
    a3.axis("off")
    a3.text(0.0, 1.0, "\n".join(_summary_lines(design, n_parallel)), va="top", family="monospace",
            fontsize=9, transform=a3.transAxes)
    fig.suptitle(title or design.family.replace("_", " "))
    fig.tight_layout()
    return fig


def plot_tms_rating(tms, result, profile, ax=None):
    """Bar chart: heat to reject vs capacity of the fixed TMS hardware at every mission point
    (``tms.RateAtPoint(..., capped=False)``). Returns the axes."""
    import numpy as np
    import matplotlib.pyplot as plt
    if ax is None:
        _, ax = plt.subplots(figsize=(10, 4))
    req, cap = [], []
    for p in profile:
        q_cap, q_req = tms.RateAtPoint(result, p, capped=False)
        req.append(q_req / 1e3)
        cap.append(q_cap / 1e3)
    x = np.arange(len(profile))
    ax.bar(x - 0.2, req, 0.4, label="heat to reject")
    ax.bar(x + 0.2, cap, 0.4, label="capacity of the sized TMS")
    ax.set_xticks(x)
    ax.set_xticklabels([p["name"] for p in profile], rotation=45, ha="right")
    ax.set_ylabel("heat [kW]")
    ax.set_title(f"TMS sized at '{result.design_point['name']}', rated over the mission")
    ax.legend()
    return ax
