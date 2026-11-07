"""Geometric heat-exchanger (HEX) sizing toolkit for the Class-II thermal-management system.

Contents, top to bottom:

1. Fluid streams and CoolProp property look-up (:class:`FluidStream`, :func:`coolprop_fluid`).
2. The epsilon-NTU method (:func:`effectiveness`, :func:`ntu_required`, :func:`thermal_solve`).
3. Three exchanger families, each sized from its geometry:

   - :class:`PlainTubeBankSizer`   -- liquid in tubes, gas across a plain staggered bank;
     Gnielinski inside, Zukauskas outside, Jakob pressure drop.
   - :class:`FinnedTubeBankSizer`  -- liquid in tubes, gas across annular-finned tubes;
     Gnielinski inside, Briggs & Young outside, Schmidt fin efficiency.
   - :class:`PlateFinSizer`        -- liquid in plain channels, gas in offset-strip fins;
     Manglik & Bergles j/f factors.

4. :class:`HeatExchangerSelector`, which picks the lightest family for one duty.

**Sizing and rating are consistent by construction.** Every sizer turns a candidate
geometry plus a required area into a *built* layout (tube count, rows, length, layers ...),
then recomputes U from the real velocities of that layout and iterates the area until the
two agree. The same :meth:`HeatExchangerSizer.compute_U` is used to *rate* a built geometry
at another flight condition (:func:`rate_design`), so rating a design at its own design point
returns its design duty.

All U values are referred to the area stored in ``HEX_Design.A`` (the total gas-side area for
finned surfaces), and the inner-side and wall resistances are scaled by the area ratio.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator, Optional

import numpy as np


# =============================================================================
# 1. FLUID STREAMS
# =============================================================================

def coolprop_available() -> bool:
    """True if CoolProp can be imported (it is an optional dependency of PhlyGreen)."""
    try:
        import CoolProp.CoolProp  # noqa: F401
        return True
    except ImportError:
        return False


def require_coolprop():
    """Raise a clear ImportError when CoolProp is missing (the Class-II TMS needs it)."""
    if not coolprop_available():
        raise ImportError("The Class-II thermal-management model needs CoolProp "
                          "(pip install CoolProp).")


@dataclass
class FluidStream:
    """One fluid stream: mass flow, transport properties and inlet temperature.

    ``cp`` is an *effective* heat capacity: for a stream that changes phase (the liquid
    hydrogen) it is the enthalpy rise divided by the temperature rise, so that
    ``mdot * cp * (T_out - T_in)`` is the exact heat absorbed.
    """
    name: str
    mdot: float          # [kg/s]
    cp: float            # [J/(kg K)]
    mu: float            # [Pa s]
    k: float             # [W/(m K)]
    rho: float           # [kg/m^3]
    T_in: float          # [K]

    @property
    def Pr(self) -> float:
        """Prandtl number cp*mu/k."""
        return self.cp * self.mu / self.k

    @property
    def C(self) -> float:
        """Heat-capacity rate mdot*cp [W/K]."""
        return self.mdot * self.cp

    @property
    def is_liquid(self) -> bool:
        """Crude phase label from the density, used only to pick a typical design velocity."""
        return self.rho > 500.0

    def with_inlet(self, T_in: float) -> "FluidStream":
        """Copy of this stream with another inlet temperature."""
        return FluidStream(self.name, self.mdot, self.cp, self.mu, self.k, self.rho, T_in)

    def split(self, n: int) -> "FluidStream":
        """The stream seen by one of ``n`` identical units in parallel (mass flow / n)."""
        return FluidStream(self.name, self.mdot / n, self.cp, self.mu, self.k, self.rho, self.T_in)

    def with_mdot(self, mdot: float) -> "FluidStream":
        """Copy of this stream with another mass flow."""
        return FluidStream(self.name, mdot, self.cp, self.mu, self.k, self.rho, self.T_in)


def coolprop_fluid(name: str, coolprop_name: str, T: float, P: float, mdot: float,
                   T_in: Optional[float] = None) -> FluidStream:
    """Build a :class:`FluidStream` with CoolProp properties evaluated at (T, P).

    ``T`` is the temperature at which properties are taken (e.g. a mean temperature);
    ``T_in`` is the stream inlet temperature (defaults to ``T``).
    """
    require_coolprop()
    from CoolProp.CoolProp import PropsSI
    cp = PropsSI("C", "T", T, "P", P, coolprop_name)
    mu = PropsSI("V", "T", T, "P", P, coolprop_name)
    k = PropsSI("L", "T", T, "P", P, coolprop_name)
    rho = PropsSI("D", "T", T, "P", P, coolprop_name)
    return FluidStream(name=name, mdot=mdot, cp=cp, mu=mu, k=k, rho=rho,
                       T_in=T if T_in is None else T_in)


@dataclass
class DesignSpec:
    """Duty and limits for ONE exchanger unit."""
    hot: FluidStream
    cold: FluidStream
    q_target: float                       # [W] heat to transfer
    dP_hot_max: float = math.inf          # [Pa]
    dP_cold_max: float = math.inf         # [Pa]
    max_volume: float = math.inf          # [m^3] per unit
    max_weight: float = math.inf          # [kg] per unit


# =============================================================================
# 2. EPSILON-NTU
# =============================================================================

class FlowArrangement(str, Enum):
    """Flow arrangement of an exchanger (selects the epsilon-NTU relation).

    For cross-flow with one stream mixed, the relation depends on whether the MIXED stream is
    the one with the smaller (C_min) or larger (C_max) heat-capacity rate; use
    :func:`crossflow_one_mixed` to pick the right one.
    """
    COUNTERFLOW = "counterflow"
    PARALLEL = "parallel"
    CROSSFLOW_UNMIXED = "crossflow_unmixed"
    CROSSFLOW_CMIN_MIXED = "crossflow_cmin_mixed"
    CROSSFLOW_CMAX_MIXED = "crossflow_cmax_mixed"


def effectiveness(ntu: float, cr: float, arrangement: FlowArrangement) -> float:
    """Exchanger effectiveness for the given NTU, capacity ratio Cr = C_min/C_max and
    arrangement (Incropera & DeWitt, Fundamentals of Heat and Mass Transfer, Table 11.3)."""
    if ntu <= 0.0:
        return 0.0
    if cr <= 1e-9:                                     # one stream has (near) infinite C
        return 1.0 - math.exp(-ntu)
    if arrangement == FlowArrangement.COUNTERFLOW:
        if abs(1.0 - cr) < 1e-9:
            return ntu / (1.0 + ntu)
        e = math.exp(-ntu * (1.0 - cr))
        return (1.0 - e) / (1.0 - cr * e)
    if arrangement == FlowArrangement.PARALLEL:
        return (1.0 - math.exp(-ntu * (1.0 + cr))) / (1.0 + cr)
    if arrangement == FlowArrangement.CROSSFLOW_UNMIXED:
        return 1.0 - math.exp((1.0 / cr) * ntu ** 0.22 * (math.exp(-cr * ntu ** 0.78) - 1.0))
    if arrangement == FlowArrangement.CROSSFLOW_CMAX_MIXED:
        return (1.0 / cr) * (1.0 - math.exp(-cr * (1.0 - math.exp(-ntu))))
    if arrangement == FlowArrangement.CROSSFLOW_CMIN_MIXED:
        return 1.0 - math.exp(-(1.0 / cr) * (1.0 - math.exp(-cr * ntu)))
    raise NotImplementedError(arrangement)


def ntu_required(eps_target: float, cr: float, arrangement: FlowArrangement,
                 ntu_max: float = 50.0, tol: float = 1e-9) -> float:
    """NTU that gives ``eps_target`` (bisection on :func:`effectiveness`, which is monotone in
    NTU). Raises ValueError if the effectiveness is not reachable with this arrangement."""
    if not (0.0 < eps_target < 1.0):
        raise ValueError(f"required effectiveness {eps_target:.4f} outside (0, 1)")
    if effectiveness(ntu_max, cr, arrangement) < eps_target:
        raise ValueError(f"effectiveness {eps_target:.4f} not reachable with "
                         f"{arrangement.value} at Cr={cr:.3f}")
    lo, hi = 0.0, ntu_max
    while hi - lo > tol * max(hi, 1.0):
        mid = 0.5 * (lo + hi)
        if effectiveness(mid, cr, arrangement) < eps_target:
            lo = mid
        else:
            hi = mid
    return hi


def thermal_solve(hot: FluidStream, cold: FluidStream, UA: float,
                  arrangement: FlowArrangement) -> float:
    """Heat [W] a given UA transfers between two streams (rating with epsilon-NTU)."""
    if UA <= 0.0 or hot.T_in <= cold.T_in:
        return 0.0
    cmin, cmax = min(hot.C, cold.C), max(hot.C, cold.C)
    eps = effectiveness(UA / cmin, cmin / cmax, arrangement)
    return eps * cmin * (hot.T_in - cold.T_in)


def crossflow_one_mixed(mixed: FluidStream, other: FluidStream) -> FlowArrangement:
    """Cross-flow arrangement label when ``mixed`` is the mixed stream (e.g. the gas across
    a tube bank) and ``other`` is unmixed (the liquid inside the tubes)."""
    return (FlowArrangement.CROSSFLOW_CMIN_MIXED if mixed.C <= other.C
            else FlowArrangement.CROSSFLOW_CMAX_MIXED)


# =============================================================================
# 3. HEAT-EXCHANGER FAMILIES
# =============================================================================

# Typical design velocities [m/s]: they fix the flow areas (tube count, face area, layers),
# which breaks the circular dependency h(velocity) -> area -> geometry -> velocity.
DESIGN_VELOCITY_LIQUID = 1.75
DESIGN_VELOCITY_GAS = 15.0


def design_velocity(fluid: FluidStream) -> float:
    """Typical design velocity of a stream [m/s] (liquid or gas)."""
    return DESIGN_VELOCITY_LIQUID if fluid.is_liquid else DESIGN_VELOCITY_GAS


def _internal_flow_h_and_f(fluid: FluidStream, v: float, D: float,
                           Nu_laminar: float) -> tuple[float, float, float]:
    """Heat-transfer coefficient [W/m^2K], Darcy friction factor and Re of an internal flow.

    Laminar (Re < 2300): fully developed Nu = ``Nu_laminar``, f = 64/Re.
    Turbulent: Petukhov friction factor and the Gnielinski Nusselt number.
    """
    Re = fluid.rho * v * D / fluid.mu
    if Re < 2300.0:
        return Nu_laminar * fluid.k / D, 64.0 / max(Re, 1e-9), Re
    f = (0.790 * math.log(Re) - 1.64) ** -2
    Pr = fluid.Pr
    Nu = (f / 8.0) * (Re - 1000.0) * Pr / (1.0 + 12.7 * math.sqrt(f / 8.0) * (Pr ** (2.0 / 3.0) - 1.0))
    return Nu * fluid.k / D, f, Re


@dataclass
class HEX_Design:
    """Sized exchanger unit.

    ``A`` is the reference heat-transfer area [m^2] (gas side for finned surfaces) and ``U``
    [W/m^2K] is referred to it. ``geometry`` holds the full built layout, so that the unit can
    be rated at other conditions with :func:`rate_design`.
    """
    family: str
    geometry: dict
    arrangement: FlowArrangement
    A: float
    U: float
    q: float
    volume: float
    weight: float
    dP_hot: float
    dP_cold: float
    v_cold: float            # [m/s] gas velocity in the core (used by the ram-air drag model)
    feasible: bool
    notes: str = ""


class HeatExchangerSizer(ABC):
    """Common interface of an exchanger family.

    A family implements :meth:`candidate_geometries`, :meth:`layout` (geometry + area ->
    built layout), :meth:`compute_U` (built layout + flows -> U, velocities, pressure drops)
    and :meth:`mass_volume`. :meth:`evaluate` then sizes one candidate self-consistently.
    """
    family_name = "generic"

    def __init__(self, spec: DesignSpec):
        self.spec = spec
        self._ntu = None          # required NTU of the spec's duty (independent of U)

    # --- to implement per family -------------------------------------------------------
    @abstractmethod
    def candidate_geometries(self) -> Iterator[dict]:
        """Yield every candidate geometry (dict of parameters) to evaluate."""

    @abstractmethod
    def arrangement(self, hot: FluidStream, cold: FluidStream) -> FlowArrangement:
        """Flow arrangement of this family for the given streams."""

    @abstractmethod
    def layout(self, geom: dict, A: float) -> dict:
        """Built layout (dict) of a candidate geometry with reference area ``A``."""

    @abstractmethod
    def compute_U(self, built: dict, hot: FluidStream, cold: FluidStream) -> dict:
        """U [W/m^2K] of a built layout at the given flows, plus velocities and pressure
        drops: keys ``U, v_hot, v_cold, dP_hot, dP_cold``, and ``R_hot``, the hot-side
        convective resistance referred to the reference area [m^2 K/W]. Raises ValueError
        when a correlation is used outside its range."""

    @abstractmethod
    def mass_volume(self, built: dict) -> tuple[float, float]:
        """(mass [kg], bounding volume [m^3]) of a built layout."""

    # --- shared sizing logic -----------------------------------------------------------
    def _area_for(self, U: float) -> float:
        """Area needed for the spec's duty at overall coefficient U (epsilon-NTU)."""
        hot, cold = self.spec.hot, self.spec.cold
        cmin, cmax = min(hot.C, cold.C), max(hot.C, cold.C)
        if self._ntu is None:
            eps = self.spec.q_target / (cmin * (hot.T_in - cold.T_in))
            self._ntu = ntu_required(eps, cmin / cmax, self.arrangement(hot, cold))
        return self._ntu * cmin / U

    def _infeasible(self, geom: dict, reason: str) -> HEX_Design:
        return HEX_Design(self.family_name, geom, self.arrangement(self.spec.hot, self.spec.cold),
                          0.0, 0.0, 0.0, math.inf, math.inf, math.inf, math.inf, 0.0,
                          False, reason)

    def evaluate(self, geom: dict, max_iter: int = 8, rtol: float = 1e-4) -> HEX_Design:
        """Size one candidate geometry self-consistently: start from the area at the U of a
        first layout, then iterate area -> layout -> real-velocity U -> area until the area
        converges. Returns an infeasible design if a correlation leaves its range, the duty
        is not reachable, or a limit (dP, mass, volume) is exceeded."""
        hot, cold = self.spec.hot, self.spec.cold
        if self.spec.q_target <= 0.0 or hot.T_in <= cold.T_in:
            return self._infeasible(geom, "no duty or no driving temperature difference")
        try:
            A = 1.0
            r = self.compute_U(self.layout(geom, A), hot, cold)
            for _ in range(max_iter):
                A_new = self._area_for(r["U"])
                built = self.layout(geom, A_new)
                r = self.compute_U(built, hot, cold)
                converged = abs(A_new - A) <= rtol * A_new
                A = A_new
                if converged:
                    break
            A = self._area_for(r["U"])     # area consistent with the final layout's U
        except ValueError as exc:
            return self._infeasible(geom, str(exc))

        weight, volume = self.mass_volume(built)
        feasible = (r["dP_hot"] <= self.spec.dP_hot_max and r["dP_cold"] <= self.spec.dP_cold_max
                    and volume <= self.spec.max_volume and weight <= self.spec.max_weight)
        return HEX_Design(self.family_name, built, self.arrangement(hot, cold), A, r["U"],
                          self.spec.q_target, volume, weight, r["dP_hot"], r["dP_cold"],
                          r["v_cold"], feasible)

    def best_candidate(self) -> Optional[HEX_Design]:
        """Lightest feasible candidate of this family (None if none is feasible)."""
        best = None
        for geom in self.candidate_geometries():
            d = self.evaluate(geom)
            if d.feasible and (best is None or d.weight < best.weight):
                best = d
        return best


# -----------------------------------------------------------------------------
# 3a. Tube banks (shared layout)
# -----------------------------------------------------------------------------

class _TubeBankSizer(HeatExchangerSizer):
    """Common layout of the two tube-bank families: liquid inside the tubes (hot), gas across
    a staggered bank (cold, mixed). Layout rules for a required gas-side area A:

    - total tube length  L_tot = A / a_o, with a_o the outer area per metre of tube;
    - face: ``n_per_row * L`` such that the gas reaches its design velocity in the minimum
      flow area, ``n_per_row * L * (S_T - w_block)``; square face (``n_per_row * S_T ~ L``);
    - depth: ``n_rows = ceil(L_tot / (n_per_row * L))``;
    - liquid side: parallel circuits at the liquid design velocity, the remaining tubes
      in series (``passes = n_tubes / n_circuits``).
    """
    WALL_THICKNESS = 0.001        # [m]
    TUBE_MATERIAL_RHO = 7800.0    # [kg/m^3] stainless steel
    K_WALL = 16.0                 # [W/(m K)]

    def arrangement(self, hot, cold):
        return crossflow_one_mixed(mixed=cold, other=hot)

    def _diameters(self) -> list[float]:
        """Tube outer diameters to scan [m] (6-25 mm). The liquid flow is accommodated by the
        number of parallel circuits, so the diameter range does not depend on the flow."""
        return [0.006, 0.008, 0.010, 0.0127, 0.016, 0.020, 0.025]

    # gas-side outer area per metre of tube and blocked width (overridden by the finned bank)
    def _outer_area_per_m(self, geom: dict) -> float:
        return math.pi * geom["d_o"]

    def _blocked_width(self, geom: dict) -> float:
        return geom["d_o"]

    def layout(self, geom: dict, A: float) -> dict:
        hot, cold = self.spec.hot, self.spec.cold
        d_o, S_T = geom["d_o"], geom["S_T"]
        d_i = d_o - 2.0 * self.WALL_THICKNESS
        gap = S_T - self._blocked_width(geom)
        L_tot = A / self._outer_area_per_m(geom)
        L_face = cold.mdot / (cold.rho * design_velocity(cold) * gap)   # n_per_row * L
        n_rows = max(1, math.ceil(L_tot / L_face - 1e-9))
        L_face = L_tot / n_rows
        L = math.sqrt(L_face * S_T)
        n_per_row = max(1, round(L_face / L))
        L = L_face / n_per_row
        n_tubes = n_per_row * n_rows
        n_circuits = hot.mdot / (hot.rho * design_velocity(hot) * math.pi / 4.0 * d_i ** 2)
        n_circuits = int(min(max(1, round(n_circuits)), n_tubes))
        return {**geom, "d_i": d_i, "L": L, "n_per_row": n_per_row, "n_rows": n_rows,
                "n_tubes": n_tubes, "n_circuits": n_circuits}

    def _tube_side(self, built: dict, hot: FluidStream) -> tuple[float, float, float]:
        """(h_in, v_hot, dP_hot) of the liquid inside the tubes."""
        d_i = built["d_i"]
        v = hot.mdot / (hot.rho * built["n_circuits"] * math.pi / 4.0 * d_i ** 2)
        h_in, f, _ = _internal_flow_h_and_f(hot, v, d_i, Nu_laminar=3.66)
        passes = built["n_tubes"] / built["n_circuits"]
        dP = f * (built["L"] * passes / d_i) * hot.rho * v ** 2 / 2.0
        return h_in, v, dP

    def _gas_vmax(self, built: dict, cold: FluidStream) -> float:
        A_min = built["n_per_row"] * built["L"] * (built["S_T"] - self._blocked_width(built))
        return cold.mdot / (cold.rho * A_min)

    def _tube_mass(self, built: dict) -> float:
        d_o, d_i = built["d_o"], built["d_i"]
        return (math.pi / 4.0 * (d_o ** 2 - d_i ** 2) * built["L"] * built["n_tubes"]
                * self.TUBE_MATERIAL_RHO)

    def _bank_volume(self, built: dict) -> float:
        S_T = built["S_T"]
        return (built["n_per_row"] * S_T) * (built["n_rows"] * S_T) * built["L"]


class PlainTubeBankSizer(_TubeBankSizer):
    """Plain staggered tube bank (square pitch S_T = S_L).

    Gas side: Zukauskas correlation for staggered banks, Nu = C Re^m Pr^0.36 C2, with the
    row-number correction C2; the (Pr/Pr_s)^0.25 wall factor is taken as 1. Pressure drop:
    Jakob's correlation for staggered banks, dP = 4 f' N rho Vmax^2 / 2,
    f' = [0.25 + 0.118 / ((S_T - d)/d)^1.08] Re^-0.16 (as reported by Holman, Heat Transfer).
    """
    family_name = "plain_tube_bank"
    PITCH_RATIOS = (1.25, 1.5, 2.0)            # S_T / d_o
    # Zukauskas row correction for staggered banks, N_rows < 20 (Incropera Table 7.6)
    _C2_ROWS = (1, 2, 3, 4, 5, 7, 10, 13, 16, 20)
    _C2_VALS = (0.64, 0.76, 0.84, 0.89, 0.92, 0.95, 0.97, 0.98, 0.99, 1.0)

    def candidate_geometries(self):
        for d_o in self._diameters():
            for pr in self.PITCH_RATIOS:
                yield {"d_o": d_o, "S_T": pr * d_o}

    def compute_U(self, built, hot, cold):
        d_o, d_i, S_T = built["d_o"], built["d_i"], built["S_T"]
        h_in, v_hot, dP_hot = self._tube_side(built, hot)
        Vmax = self._gas_vmax(built, cold)
        Re = cold.rho * Vmax * d_o / cold.mu
        if Re < 10.0 or Re > 2e6:
            raise ValueError(f"Zukauskas outside range (Re={Re:.0f})")
        if Re < 1000.0:
            C, m = 0.71, 0.5
        elif Re < 2e5:
            C, m = 0.35, 0.60                        # (S_T/S_L)^0.2 = 1 for a square pitch
        else:
            C, m = 0.022, 0.84
        C2 = float(np.interp(built["n_rows"], self._C2_ROWS, self._C2_VALS))
        h_out = C2 * C * Re ** m * cold.Pr ** 0.36 * cold.k / d_o
        r_wall = d_o * math.log(d_o / d_i) / (2.0 * self.K_WALL)       # referred to A_o
        U = 1.0 / (d_o / (d_i * h_in) + r_wall + 1.0 / h_out)
        f_jakob = (0.25 + 0.118 / ((S_T - d_o) / d_o) ** 1.08) * Re ** -0.16
        dP_cold = 4.0 * f_jakob * built["n_rows"] * cold.rho * Vmax ** 2 / 2.0
        return {"U": U, "v_hot": v_hot, "v_cold": Vmax, "dP_hot": dP_hot, "dP_cold": dP_cold,
                "R_hot": d_o / (d_i * h_in)}

    def mass_volume(self, built):
        return self._tube_mass(built), self._bank_volume(built)


class FinnedTubeBankSizer(_TubeBankSizer):
    """Annular-finned staggered tube bank (aluminium fins on steel tubes).

    Gas side: Briggs & Young (1963), Nu = 0.134 Re^0.681 Pr^(1/3) (s/l)^0.2 (s/t)^0.1134,
    with Re on the tube diameter and the maximum velocity; the candidate fin spacing is kept
    inside the correlation's tested range of s/t. Fin efficiency: annular fin with Schmidt's
    equivalent-radius approximation. The transverse pitch is set from the FIN diameter, so
    fins of adjacent tubes never overlap.

    Gas-side pressure drop: ``N_rows * f * rho * Vmax^2 / 2`` with ``f = 1.5 Re^-0.2``, an
    approximation without a literature source; a validated finned-bank friction correlation
    (e.g. Robinson & Briggs) should replace it.
    """
    family_name = "finned_tube_bank"
    FIN_MATERIAL_RHO = 2700.0    # [kg/m^3] aluminium
    K_FIN = 200.0                # [W/(m K)]
    FIN_THICKNESS = 0.0003       # [m]
    FIN_HEIGHTS = (0.006, 0.010, 0.014)          # [m]
    FIN_DENSITIES = (450.0, 550.0, 650.0)        # [fins/m]: s/t = 6.1, 4.9, 4.1
    PITCH_FACTORS = (1.05, 1.20)                 # S_T / fin outer diameter

    def candidate_geometries(self):
        for d_o in self._diameters():
            for h_f in self.FIN_HEIGHTS:
                for n_f in self.FIN_DENSITIES:
                    for pf in self.PITCH_FACTORS:
                        yield {"d_o": d_o, "fin_height": h_f, "fin_density": n_f,
                               "S_T": pf * (d_o + 2.0 * h_f)}

    def _fin_areas(self, geom):
        """(fin area, bare-tube area) per metre of tube [m^2/m]."""
        t, n_f = self.FIN_THICKNESS, geom["fin_density"]
        r1 = geom["d_o"] / 2.0
        r2 = r1 + geom["fin_height"]
        A_fin = n_f * 2.0 * math.pi * (r2 ** 2 - r1 ** 2)
        A_bare = math.pi * geom["d_o"] * (1.0 - t * n_f)
        return A_fin, A_bare

    def _outer_area_per_m(self, geom):
        A_fin, A_bare = self._fin_areas(geom)
        return A_fin + A_bare

    def _blocked_width(self, geom):
        return geom["d_o"] + 2.0 * geom["fin_density"] * geom["fin_height"] * self.FIN_THICKNESS

    def _fin_efficiency(self, h_out: float, geom: dict) -> float:
        t = self.FIN_THICKNESS
        r1 = geom["d_o"] / 2.0
        r2c = r1 + geom["fin_height"] + t / 2.0
        phi = (r2c / r1 - 1.0) * (1.0 + 0.35 * math.log(r2c / r1))
        mrphi = math.sqrt(2.0 * h_out / (self.K_FIN * t)) * r1 * phi
        return 1.0 if mrphi < 1e-6 else math.tanh(mrphi) / mrphi

    def compute_U(self, built, hot, cold):
        d_o, d_i = built["d_o"], built["d_i"]
        t = self.FIN_THICKNESS
        s = 1.0 / built["fin_density"] - t                # clear gap between fins
        h_in, v_hot, dP_hot = self._tube_side(built, hot)
        Vmax = self._gas_vmax(built, cold)
        Re = cold.rho * Vmax * d_o / cold.mu
        if Re < 1000.0 or Re > 1e5:
            raise ValueError(f"Briggs & Young outside range (Re={Re:.0f})")
        Nu = (0.134 * Re ** 0.681 * cold.Pr ** (1.0 / 3.0)
              * (s / built["fin_height"]) ** 0.2 * (s / t) ** 0.1134)
        h_out = Nu * cold.k / d_o
        A_fin, A_bare = self._fin_areas(built)
        A_o = A_fin + A_bare
        eta_o = 1.0 - (A_fin / A_o) * (1.0 - self._fin_efficiency(h_out, built))
        A_i = math.pi * d_i
        r_wall = math.log(d_o / d_i) / (2.0 * math.pi * self.K_WALL)   # per metre of tube
        # resistances per metre of tube, referred to the gas-side area A_o
        U = 1.0 / (A_o / (A_i * h_in) + A_o * r_wall + 1.0 / (eta_o * h_out))
        f = 1.5 * Re ** -0.2
        dP_cold = built["n_rows"] * f * cold.rho * Vmax ** 2 / 2.0
        return {"U": U, "v_hot": v_hot, "v_cold": Vmax, "dP_hot": dP_hot, "dP_cold": dP_cold,
                "eta_o": eta_o, "R_hot": A_o / (A_i * h_in)}

    def mass_volume(self, built):
        A_fin, _ = self._fin_areas(built)
        m_fins = A_fin / 2.0 * self.FIN_THICKNESS * built["L"] * built["n_tubes"] * self.FIN_MATERIAL_RHO
        return self._tube_mass(built) + m_fins, self._bank_volume(built)


# -----------------------------------------------------------------------------
# 3b. Plate-fin
# -----------------------------------------------------------------------------

class PlateFinSizer(HeatExchangerSizer):
    """Brazed aluminium plate-fin core, counterflow: gas in offset-strip-fin layers, liquid
    in plain channels, alternating and separated by parting sheets.

    Gas side: Manglik & Bergles (1995) j and f factors. Liquid side: plain parallel-plate
    channel, laminar Nu = 7.54 or Gnielinski. Layout: the number of layers and the liquid
    channel gap follow from the design velocities of the two streams at the candidate width;
    a liquid gap below ``MIN_GAP_H`` is not producible. U is referred to the gas-side area
    A_c; the liquid-side and wall resistances are scaled by A_c/A_h = (s + h)/s.
    """
    family_name = "plate_fin"
    MATERIAL_RHO = 2700.0     # [kg/m^3] aluminium
    K_MATERIAL = 200.0        # [W/(m K)]
    FIN_THICKNESS = 0.0002    # [m]
    PLATE_THICKNESS = 0.0005  # [m]
    MIN_GAP_H = 0.001         # [m] smallest producible liquid channel
    FIN_PITCHES = (0.0015, 0.0025, 0.004)   # s [m]
    FIN_HEIGHTS = (0.006, 0.010)            # h [m]
    STRIP_LENGTHS = (0.003, 0.006)          # l [m]
    WIDTHS = (0.1, 0.2, 0.3, 0.5)           # core width [m]

    def arrangement(self, hot, cold):
        return FlowArrangement.COUNTERFLOW

    def candidate_geometries(self):
        for s in self.FIN_PITCHES:
            for h in self.FIN_HEIGHTS:
                for l in self.STRIP_LENGTHS:
                    for w in self.WIDTHS:
                        yield {"fin_pitch": s, "fin_height": h, "strip_length": l, "width": w}

    def _beta(self, geom):
        """Gas-side area per unit gas-layer volume [m^2/m^3]."""
        s, h = geom["fin_pitch"], geom["fin_height"]
        return 2.0 * (s + h) / (s * h)

    def layout(self, geom, A):
        hot, cold = self.spec.hot, self.spec.cold
        h, w = geom["fin_height"], geom["width"]
        n_cold = cold.mdot / (cold.rho * design_velocity(cold) * h * w)
        n_hot = hot.mdot / (hot.rho * design_velocity(hot) * h * w)
        n_layers = max(1, round(max(n_cold, n_hot)))
        gap_h = hot.mdot / (hot.rho * design_velocity(hot)) / (n_layers * w)
        if gap_h < self.MIN_GAP_H:
            raise ValueError(f"liquid channel gap {gap_h*1e3:.2f} mm below the producible "
                             f"minimum ({self.MIN_GAP_H*1e3:.1f} mm)")
        L_flow = A / (self._beta(geom) * n_layers * h * w)
        return {**geom, "n_layers": n_layers, "gap_h": gap_h, "L_flow": L_flow}

    def compute_U(self, built, hot, cold):
        s, h, l, w = built["fin_pitch"], built["fin_height"], built["strip_length"], built["width"]
        t = self.FIN_THICKNESS
        n, gap_h, L = built["n_layers"], built["gap_h"], built["L_flow"]

        Dh_c = 4.0 * s * h / (2.0 * (s + h))
        G_c = cold.mdot / (n * h * w)
        Re_c = G_c * Dh_c / cold.mu
        if Re_c < 100.0:
            raise ValueError(f"Manglik & Bergles outside range (Re={Re_c:.0f})")
        alpha, delta, gamma = s / h, t / l, t / s
        j = (0.6522 * Re_c ** -0.5403 * alpha ** -0.1541 * delta ** 0.1499 * gamma ** -0.0678
             * (1 + 5.269e-5 * Re_c ** 1.34 * alpha ** 0.504 * delta ** 0.456 * gamma ** -1.055) ** 0.1)
        f = (9.6243 * Re_c ** -0.7422 * alpha ** -0.1856 * delta ** 0.3053 * gamma ** -0.2659
             * (1 + 7.669e-8 * Re_c ** 4.429 * alpha ** 0.920 * delta ** 3.767 * gamma ** 0.236) ** 0.1)
        h_c = j * G_c * cold.cp / cold.Pr ** (2.0 / 3.0)
        mlf = math.sqrt(2.0 * h_c / (self.K_MATERIAL * t)) * (h / 2.0)
        eta_f = 1.0 if mlf < 1e-6 else math.tanh(mlf) / mlf
        eta_o = 1.0 - (h / (s + h)) * (1.0 - eta_f)          # fin area fraction h/(s+h)

        v_h = hot.mdot / (hot.rho * n * gap_h * w)
        h_h, f_h, _ = _internal_flow_h_and_f(hot, v_h, 2.0 * gap_h, Nu_laminar=7.54)
        area_ratio = (s + h) / s                              # A_c / A_h
        U = 1.0 / (area_ratio / h_h + area_ratio * self.PLATE_THICKNESS / self.K_MATERIAL
                   + 1.0 / (eta_o * h_c))

        v_c = G_c / cold.rho
        dP_cold = 4.0 * f * (L / Dh_c) * cold.rho * v_c ** 2 / 2.0
        dP_hot = f_h * (L / (2.0 * gap_h)) * hot.rho * v_h ** 2 / 2.0
        return {"U": U, "v_hot": v_h, "v_cold": v_c, "dP_hot": dP_hot, "dP_cold": dP_cold,
                "eta_o": eta_o, "R_hot": area_ratio / h_h}

    def mass_volume(self, built):
        s, h, w = built["fin_pitch"], built["fin_height"], built["width"]
        n, L = built["n_layers"], built["L_flow"]
        t = self.FIN_THICKNESS
        # fin sheet: per channel of pitch s, one vertical web (h) and one horizontal (s)
        m_fins = n * w * L * (h + s) / s * t * self.MATERIAL_RHO
        m_plates = 2 * n * w * L * self.PLATE_THICKNESS * self.MATERIAL_RHO
        height = n * (h + built["gap_h"] + 2.0 * self.PLATE_THICKNESS)
        return m_fins + m_plates, w * height * L


# =============================================================================
# 4. FAMILY COMPARISON AND RATING
# =============================================================================

SIZERS = {
    PlainTubeBankSizer.family_name: PlainTubeBankSizer,
    FinnedTubeBankSizer.family_name: FinnedTubeBankSizer,
    PlateFinSizer.family_name: PlateFinSizer,
}


class HeatExchangerSelector:
    """Compares exchanger families for one duty.

    :meth:`select_best` returns the lightest feasible design (volume as tie-break): the volume
    limit is already enforced as a hard per-unit cap by the sizers, and for an aircraft the
    mass is what feeds back into the design. :meth:`pareto_front` is available for reporting.
    """
    def __init__(self, spec: DesignSpec, families=tuple(SIZERS)):
        self.spec = spec
        self.sizers = [SIZERS[f](spec) for f in families]
        self._candidates = None

    def candidates(self) -> list[HEX_Design]:
        """Best feasible design of each family (families with none are omitted)."""
        if self._candidates is None:
            self._candidates = [d for d in (s.best_candidate() for s in self.sizers) if d is not None]
        return self._candidates

    def pareto_front(self) -> list[HEX_Design]:
        """Candidates not dominated in the (mass, volume) plane."""
        c = self.candidates()
        return [d for d in c if not any(
            o.weight <= d.weight and o.volume <= d.volume and (o.weight < d.weight or o.volume < d.volume)
            for o in c if o is not d)]

    def select_best(self) -> Optional[HEX_Design]:
        """Lightest feasible design across the families (None if no family can do the duty)."""
        c = self.candidates()
        return min(c, key=lambda d: (d.weight, d.volume)) if c else None


@dataclass
class UnitRating:
    """Operating state of ONE built unit at given (per-unit) streams (see :func:`rate_unit`).
    Outside a correlation's range the heat is 0 and the other fields are nan."""
    q: float                 # [W] heat transferred
    U: float                 # [W/(m^2 K)] referred to HEX_Design.A
    R_hot: float             # [m^2 K/W] hot-side film resistance, referred to HEX_Design.A
    dP_hot: float            # [Pa] hot-side pressure drop
    dP_cold: float           # [Pa] cold-side pressure drop
    v_cold: float            # [m/s] cold-stream velocity in the core
    in_range: bool           # False when a flow is outside a correlation's range


def rate_unit(design: HEX_Design, hot: FluidStream, cold: FluidStream) -> UnitRating:
    """Rate ONE built unit at the given (per-unit) streams.

    U, velocities and pressure drops are recomputed from the stored layout at the new flows
    (same correlations used to size it). A flow outside a correlation's range is rated as
    transferring no heat, with unknown (nan) pressure drops."""
    sizer = SIZERS[design.family](DesignSpec(hot=hot, cold=cold, q_target=0.0))
    try:
        r = sizer.compute_U(design.geometry, hot, cold)
    except ValueError:
        return UnitRating(0.0, math.nan, math.nan, math.nan, math.nan, math.nan, False)
    q = thermal_solve(hot, cold, r["U"] * design.A, sizer.arrangement(hot, cold))
    return UnitRating(q, r["U"], r["R_hot"], r["dP_hot"], r["dP_cold"], r["v_cold"], True)


def rate_design(design: HEX_Design, hot: FluidStream, cold: FluidStream) -> float:
    """Heat [W] that ONE built unit transfers at the given (per-unit) streams
    (the ``q`` of :func:`rate_unit`)."""
    return rate_unit(design, hot, cold).q
