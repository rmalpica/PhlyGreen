"""Class-II cell model figures (no aircraft design is run).

fig_cell_discharge.pdf : constant-current discharge curves of the cell of
                         ``common.hybrid_config('II')`` at several C-rates and temperatures.
fig_cell_power.pdf     : open-circuit and loaded voltage vs SOC, and the cell power-current
                         parabola that Battery.Power_2_current solves.
data/cell.json         : cell parameters before and after rescaling, and the numbers quoted.
"""

import numpy as np

from _setup import C, SEQ, GREY, TEXTWIDTH, plt, save, dump, label_panel

import PhlyGreen as pg
from PhlyGreen.Systems.Battery.Cell_Models import Cell_Models
from common import hybrid_config

PARAMS = ["Tref", "exp_amplitude", "exp_time_ctt", "cell_resistance", "R_arrhenius",
          "polarization_ctt", "K_arrhenius", "cell_capacity", "Q_slope", "voltage_ctt",
          "E_slope", "cell_Vmax", "cell_Vmin", "cell_max_current", "cell_mass", "Vnom",
          "cell_energy_nom", "S_number", "pack_Vmax", "Rith", "Cth", "cell_area_surface",
          "module_area_section"]


def battery(se=1500.0, sp=8000.0, model="Finger-Cell-Thermal"):
    """A configured Class-II battery (no design). ``se``/``sp`` = None keep the database cell.

    The typed CellConfig drops None fields, and Battery.SetInput indexes 'SpecificEnergy' /
    'SpecificPower' directly, so the un-rescaled cell is obtained by re-running SetInput on a
    CellInput dict that carries explicit None values.
    """
    a = pg.build_aircraft()
    a.configure(hybrid_config("II"), design=False)
    a.CellInput = dict(a.CellInput)
    a.CellInput.update({"SpecificEnergy": se, "SpecificPower": sp, "Model": model})
    a.battery.SetInput()
    a.battery.Configure(1)
    return a.battery


def params(b):
    return {k: float(getattr(b, k)) for k in PARAMS}


def discharge(b, current, T, n=600):
    """Constant-current discharge: cell voltage vs spent charge until V < Vmin or it -> Q(T)."""
    b.T = T
    q = b.Q
    it = np.linspace(0.0, 0.999 * min(q, b.cell_capacity), n)
    v = np.array([b._voltageModel(x, current) for x in it])
    ok = v >= b.cell_Vmin
    stop = np.argmin(ok) if not ok.all() else len(v)
    return it[:stop], v[:stop]


def main():
    b = battery()
    raw = battery(None, None)
    module = battery(None, None, "ThermalModel-Cell")
    Q0, Tref = b.cell_capacity, b.Tref
    out = {"scaled_cell": params(b), "raw_cell": params(raw), "thermal_model_cell": params(module),
           "database": Cell_Models}
    for key, bb in (("scaled_cell", b), ("raw_cell", raw), ("thermal_model_cell", module)):
        bb.T = bb.Tref
        out[key]["pmax_cell_W"] = float(bb.cell_max_current * bb._voltageModel(0, bb.cell_max_current))
        out[key]["specific_power_W_per_kg"] = out[key]["pmax_cell_W"] / bb.cell_mass
        out[key]["specific_energy_Wh_per_kg"] = bb.cell_energy_nom / bb.cell_mass
        out[key]["max_C_rate"] = bb.cell_max_current / bb.cell_capacity

    # ---------------- figure 1: discharge curves ----------------
    fig, axes = plt.subplots(1, 2, figsize=(TEXTWIDTH, 2.7), sharey=True)
    ax = axes[0]
    rates = [0.5, 1.0, 2.0, 4.0]
    rec = {}
    for k, cr in enumerate(rates):
        it, v = discharge(b, cr * Q0, Tref)
        ax.plot(it, v, color=SEQ[k + 1], label=f"{cr:g}C")
        rec[f"{cr:g}C"] = {"charge_at_cutoff_Ah": float(it[-1]), "V_start": float(v[0]),
                           "V_at_SOCmin": float(np.interp((1 - 0.2) * Q0, it, v)) if it[-1] > 0.8 * Q0 else None}
    imax = b.cell_max_current
    it, v = discharge(b, imax, Tref)
    ax.plot(it, v, color=C[1], ls="--", label=f"$I_{{max}}$ ({imax / Q0:.1f}C)")
    rec["Imax"] = {"current_A": float(imax), "charge_at_cutoff_Ah": float(it[-1]), "V_start": float(v[0])}
    ax.axvline(0.8 * Q0, color=GREY, lw=0.8, ls=":")
    ax.text(0.8 * Q0, 4.12, "SOC$_{min}$ = 0.2 ", color=GREY, fontsize=7, ha="right")
    ax.axhline(b.cell_Vmin, color=GREY, lw=0.8)
    ax.set_xlabel("discharged capacity $i_t$ [Ah]")
    ax.set_ylabel("cell voltage $V$ [V]")
    ax.set_title(f"$T = T_{{ref}}$ = {Tref - 273.15:.0f} °C")
    ax.legend(loc="lower left")
    label_panel(ax, "a")
    out["discharge_vs_C_rate"] = rec

    ax = axes[1]
    temps = [10.0, 25.0, 40.0, 50.0]
    rec = {}
    for k, Tc in enumerate(temps):
        it, v = discharge(b, 2.0 * Q0, Tc + 273.15)
        b.T = Tc + 273.15
        ax.plot(it, v, color=SEQ[k + 1], label=f"{Tc:g} °C")
        rec[f"{Tc:g}C"] = {"Q_T_Ah": float(b.Q), "R_T_ohm": float(b.R), "K_T": float(b.K),
                           "E0_T": float(b.E0), "charge_at_cutoff_Ah": float(it[-1])}
    ax.axhline(b.cell_Vmin, color=GREY, lw=0.8)
    ax.axvline(0.8 * Q0, color=GREY, lw=0.8, ls=":")
    ax.set_xlabel("discharged capacity $i_t$ [Ah]")
    ax.set_title("2C discharge")
    ax.legend(loc="lower left")
    label_panel(ax, "b")
    out["discharge_vs_T_2C"] = rec
    fig.tight_layout()
    save(fig, "fig_cell_discharge.pdf")

    # ---------------- figure 2: OCV vs loaded voltage, power parabola ----------------
    b.T = Tref
    fig, axes = plt.subplots(1, 2, figsize=(TEXTWIDTH, 2.7))
    ax = axes[0]
    soc = np.linspace(1.0, 0.05, 300)
    it = (1 - soc) * Q0
    voc = [b._voltageModel(x, 0.0) for x in it]
    ax.plot(soc, voc, color=C[0], label="open circuit, $V(i_t, 0)$")
    v1 = [b._voltageModel(x, Q0) for x in it]
    vmax = [b._voltageModel(x, imax) for x in it]
    ax.plot(soc, v1, color=C[2], label="1C")
    ax.plot(soc, vmax, color=C[1], ls="--", label="$I_{max}$")
    ax.axhline(b.cell_Vmin, color=GREY, lw=0.8)
    ax.axvline(0.2, color=GREY, lw=0.8, ls=":")
    ax.set_xlim(1.0, 0.05)
    ax.set_ylim(1.5, 4.4)
    ax.set_xlabel("state of charge [-]")
    ax.set_ylabel("cell voltage [V]")
    ax.legend(loc="lower left")
    label_panel(ax, "a")

    ax = axes[1]
    rec = {}
    for k, s in enumerate([1.0, 0.5, 0.2]):
        itc = (1 - s) * Q0
        R, K, Q, E0 = b.R, b.K, b.Q, b.E0
        Qr = K * Q / (Q - itc)
        a_ = -R - Qr
        bb = E0 + b.exp_amplitude * np.exp(-b.exp_time_ctt * itc) - itc * Qr
        i = np.linspace(0, -bb / a_, 300)
        p = a_ * i ** 2 + bb * i
        ax.plot(i, p, color=C[k], label=f"SOC = {s:g}")
        i_star = -bb / (2 * a_)
        rec[f"SOC_{s:g}"] = {"P_peak_W": float(-bb ** 2 / (4 * a_)), "I_at_peak_A": float(i_star),
                             "V_at_peak": float(b._voltageModel(itc, i_star)),
                             "P_at_Imax_W": float(imax * b._voltageModel(itc, imax)),
                             "V_at_Imax": float(b._voltageModel(itc, imax))}
        ax.plot([i_star], [-bb ** 2 / (4 * a_)], "o", color=C[k], ms=4)
    ax.axvline(imax, color=GREY, lw=0.8, ls="--")
    ax.text(imax, 0.03 * ax.get_ylim()[1], " $I_{max}$", color=GREY, fontsize=7)
    ax.set_xlabel("cell current $i$ [A]")
    ax.set_ylabel("cell power $P = V i$ [W]")
    ax.legend(loc="upper right")
    label_panel(ax, "b")
    out["power_parabola"] = rec
    fig.tight_layout()
    save(fig, "fig_cell_power.pdf")

    # Heat-generation terms at 2C, half charge (for the discussion of heatLoss)
    b.T = Tref
    b.it = 0.5 * Q0
    b.i = 2.0 * Q0
    b.phi = 1.0
    i = 2.0 * Q0
    irr = (b.cell_Voc - b.cell_Vout) * i
    rev = b.E_slope * i * b.T
    out["heat_terms_2C_SOC05"] = {"irreversible_W": float(irr), "entropic_W": float(rev)}
    dump("cell.json", out)


if __name__ == "__main__":
    main()
