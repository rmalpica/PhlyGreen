"""Net drag of a ram-air heat-exchanger duct (Meredith-type momentum balance).

The duct is modelled as: intake + diffuser -> heat-exchanger core -> nozzle.

1. The free stream (V_inf, T_amb, P_amb) is decelerated adiabatically in the diffuser; the
   total temperature is conserved and the intake recovers the fraction ``eta_ram`` of the
   free-stream dynamic (ram) pressure, ``p0_1 = P_amb + eta_ram (p0_inf - P_amb)``
   (1.0 = ideal intake). Ram recovery is defined on the dynamic pressure, not on the
   absolute total pressure, because at these speeds the dynamic pressure is only a few
   percent of the total pressure.
2. In the core the air is heated at the core Mach number (Rayleigh flow, giving the small
   total-pressure loss due to heating at low speed) and loses the core friction pressure
   drop ``dP_core`` computed by the exchanger sizer.
3. The nozzle expands the air isentropically back to ambient pressure.

The net drag is ``D = mdot * (V_inf - V_exit)``. Heat addition raises V_exit (Meredith
effect), friction and intake losses lower it. A negative value means net thrust.

The model has no spillage, external (cowl) drag or duct-wall losses beyond ``eta_ram``,
so it is a lower bound on the installation drag.
"""

import math

GAMMA = 1.4
CP_AIR = 1005.0     # [J/(kg K)]
R_AIR = 287.05      # [J/(kg K)]


def _rayleigh_T0_ratio(M: float) -> float:
    """T0/T0* of Rayleigh flow at Mach M."""
    g = GAMMA
    return 2.0 * (1.0 + g) * M ** 2 * (1.0 + (g - 1.0) / 2.0 * M ** 2) / (1.0 + g * M ** 2) ** 2


def _rayleigh_p0_ratio(M: float) -> float:
    """p0/p0* of Rayleigh flow at Mach M."""
    g = GAMMA
    return ((1.0 + g) / (1.0 + g * M ** 2)
            * ((2.0 / (g + 1.0)) * (1.0 + (g - 1.0) / 2.0 * M ** 2)) ** (g / (g - 1.0)))


def _subsonic_mach_from_T0_ratio(target: float, M_lo: float) -> float:
    """Subsonic Mach (above M_lo) whose Rayleigh T0/T0* equals ``target`` (bisection)."""
    if target >= 1.0:
        raise ValueError("thermal choking: the heat load cannot be added in subsonic flow")
    lo, hi = M_lo, 1.0
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if _rayleigh_T0_ratio(mid) < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def ram_air_drag(Q: float, mdot_air: float, T_amb: float, P_amb: float, V_inf: float,
                 V_core: float, dP_core: float, eta_ram: float = 1.0) -> float:
    """Net drag [N] of a ram-air cooling duct (see module docstring).

    Args:
        Q: heat added to the air [W].
        mdot_air: air mass flow [kg/s].
        T_amb: ambient static temperature [K].
        P_amb: ambient static pressure [Pa].
        V_inf: true airspeed [m/s].
        V_core: air velocity in the exchanger core [m/s].
        dP_core: core (air-side) pressure drop [Pa].
        eta_ram: fraction of the free-stream dynamic pressure recovered by the intake.
    """
    if mdot_air <= 0.0 or V_inf <= 0.0:
        return 0.0
    T0_1 = T_amb + V_inf ** 2 / (2.0 * CP_AIR)
    p0_inf = P_amb * (T0_1 / T_amb) ** (GAMMA / (GAMMA - 1.0))
    p0_1 = P_amb + eta_ram * (p0_inf - P_amb)

    T_core = T0_1 - V_core ** 2 / (2.0 * CP_AIR)
    M1 = V_core / math.sqrt(GAMMA * R_AIR * T_core)
    T0_2 = T0_1 + Q / (mdot_air * CP_AIR)
    M2 = _subsonic_mach_from_T0_ratio(_rayleigh_T0_ratio(M1) * T0_2 / T0_1, M_lo=M1)
    p0_2 = p0_1 * _rayleigh_p0_ratio(M2) / _rayleigh_p0_ratio(M1) - dP_core

    if p0_2 <= P_amb:                    # no expansion left: the air leaves at ~zero speed
        V_exit = 0.0
    else:
        V_exit = math.sqrt(2.0 * CP_AIR * T0_2 * (1.0 - (P_amb / p0_2) ** ((GAMMA - 1.0) / GAMMA)))
    return mdot_air * (V_inf - V_exit)
