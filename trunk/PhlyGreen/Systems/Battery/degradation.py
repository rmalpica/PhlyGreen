"""Opt-in Class-II battery thermal-management and cycle-life degradation analysis.

This is a *post-design* analysis layered on a **already-sized** Class-II battery pack — it is
never part of the take-off-weight sizing loop, so it cannot change a baseline design. Given a
designed pack it estimates:

* the **ground fast-charge** recharge time and the cell temperature reached, time-stepping a
  lumped thermal balance of Joule heating (Arrhenius-corrected internal resistance) against an
  active liquid cold-plate;
* the **peak active-cooling power** the thermal-management system (TMS) must reject during that
  recharge (a sizing driver for the ground/onboard cooling system);
* the expected **number of full cycles to end-of-life** via the Wang et al. capacity-fade law
  with a Miner (or Marco–Starkey) damage accumulation over the flight and the recharge.

Adapted from the Class-II battery heat-management & degradation work by Francesco Campagna and
ported to operate on the current battery model's attributes. All inputs are optional and read
from ``CellInput`` (typed: :class:`PhlyGreen.config.CellConfig`).
"""

import math

import numpy as np

# Wang et al. (2011) LFP/NMC capacity-fade coefficients (defaults; overridable per cell).
WANG_DEFAULTS = dict(A=31630.0, Ea=31700.0, Af=370.3, z=0.55, R=8.314)


class BatteryAgeingModel:
    """Ground-recharge thermal model + Wang/Miner cycle-life for a designed Class-II pack.

    Args:
        battery: a *configured* Class-II :class:`~PhlyGreen.Systems.Battery.Battery.Battery`
            (so ``cell_capacity``, ``S_number``/``P_number``, ``cell_resistance``,
            ``R_arrhenius``, ``Tref``, ``cell_area_surface``, ``Cth``, ``SOC_min``, ``T`` are
            set).
        charge_c_rate: ground fast-charge C-rate [1/h].
        discharge_c_rate: representative in-flight discharge C-rate [1/h]; defaults to the
            charge rate when not given.
        soc_start: SOC at the start of the recharge (end of flight); defaults to ``SOC_min``.
        soc_max: SOC at full charge (default 1.0).
        eol_capacity: end-of-life capacity fraction (default 0.8 = 80 %).
        coolant_temperature: ground coolant inlet temperature [K] (default 293.15).
        ground_h: ground cold-plate convective coefficient [W/m^2K] (default 150).
        wang: optional overrides for the Wang coefficients.
    """

    def __init__(self, battery, charge_c_rate, discharge_c_rate=None, soc_start=None,
                 soc_max=1.0, eol_capacity=0.8, coolant_temperature=293.15, ground_h=150.0,
                 wang=None):
        self.b = battery
        self.charge_c_rate = charge_c_rate
        self.discharge_c_rate = discharge_c_rate if discharge_c_rate is not None else charge_c_rate
        self.soc_max = soc_max
        self.soc_start = soc_start if soc_start is not None else battery.SOC_min
        self.eol_capacity = eol_capacity
        self.T_coolant = coolant_temperature
        self.h_ground = ground_h
        self.wang = {**WANG_DEFAULTS, **(wang or {})}

    # ------------------------------------------------------------------ recharge / cooling
    def recharge_time_min(self):
        """Constant-current recharge time from ``soc_start`` to ``soc_max`` [minutes]."""
        if not self.charge_c_rate or self.charge_c_rate <= 0:
            return float("inf")
        delta_soc = self.soc_max - self.soc_start
        if delta_soc <= 0:
            return 0.0
        return (delta_soc / self.charge_c_rate) * 60.0

    def simulate_ground_recharge(self, dt=5.0):
        """Time-step the pack temperature during ground fast charge.

        Returns a dict with ``recharge_time_min``, ``T_final`` [K], ``peak_cooling_w`` and
        ``peak_heat_w`` (pack-level). Joule heating uses the Arrhenius-corrected resistance;
        cooling is an active cold-plate ``h_ground * A * (T - T_coolant)``.
        """
        b = self.b
        t_min = self.recharge_time_min()
        if not math.isfinite(t_min):
            return {"recharge_time_min": t_min, "T_final": float(b.T),
                    "peak_cooling_w": 0.0, "peak_heat_w": 0.0}

        term_current = self.charge_c_rate * b.cell_capacity     # charge current per cell [A]
        area = b.cell_area_surface
        total_cells = b.S_number * b.P_number
        T = float(b.T)
        steps = max(int(t_min * 60.0 / dt), 1)
        peak_cool = peak_gen = 0.0
        for _ in range(steps):
            if b.R_arrhenius:
                r = b.cell_resistance * math.exp(b.R_arrhenius * (1.0 / T - 1.0 / b.Tref))
            else:
                r = b.cell_resistance
            q_gen = term_current ** 2 * r                       # Joule heat per cell [W]
            q_cool = self.h_ground * area * (T - self.T_coolant)
            peak_gen = max(peak_gen, q_gen * total_cells)
            peak_cool = max(peak_cool, q_cool * total_cells)
            T += ((q_gen - q_cool) * dt) / b.Cth
        return {"recharge_time_min": t_min, "T_final": T,
                "peak_cooling_w": peak_cool, "peak_heat_w": peak_gen}

    # ------------------------------------------------------------------ degradation
    def _cycles_to_eol(self, c_rate, dod, temperature_k):
        """Cycles to end-of-life at constant (c_rate, DoD, T) — Wang et al. capacity fade."""
        w = self.wang
        eol_loss_percent = (1.0 - self.eol_capacity) * 100.0
        if dod <= 0 or c_rate <= 0:
            return float("inf")
        Tk = np.asarray(temperature_k, dtype=float)
        Tk = np.where(Tk <= 0, 298.15, Tk)
        throughput_Ah = (eol_loss_percent /
                         (w["A"] * np.exp((-w["Ea"] + w["Af"] * c_rate) / (w["R"] * Tk)))) ** (1.0 / w["z"])
        return throughput_Ah / (dod * self.b.cell_capacity)

    def cycle_life(self, flight_temp_k=None, charge_temp_k=None, damage_exponent=1,
                   sf_flight=0.25, sf_charge=0.25):
        """Expected number of full cycles to end-of-life (flight + recharge damage)."""
        b = self.b
        if flight_temp_k is None:
            flight_temp_k = b.T
        if charge_temp_k is None:
            charge_temp_k = self.simulate_ground_recharge()["T_final"]
        dod = max(self.soc_max - self.soc_start, 1e-3)
        cyc_flight = self._cycles_to_eol(self.discharge_c_rate, dod, flight_temp_k)
        cyc_charge = self._cycles_to_eol(self.charge_c_rate, dod, charge_temp_k)
        dmg_flight = sf_flight * np.mean(0.5 / cyc_flight)
        dmg_charge = sf_charge * np.mean(0.5 / cyc_charge)
        if damage_exponent == 1:
            total = dmg_flight + dmg_charge                    # Miner (linear)
        else:
            total = (dmg_flight ** damage_exponent + dmg_charge ** damage_exponent) ** (1.0 / damage_exponent)
        return float(1.0 / total) if total > 0 else float("inf")

    # ------------------------------------------------------------------ orchestrator
    def analyze(self):
        """Run the full ground-recharge + cycle-life analysis and return a results dict."""
        rec = self.simulate_ground_recharge()
        n_cycles = self.cycle_life(charge_temp_k=rec["T_final"])
        out = dict(rec)
        out["dod"] = self.soc_max - self.soc_start
        out["n_cycles"] = n_cycles
        return out
