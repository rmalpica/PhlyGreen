"""Cryogenic liquid-hydrogen (LH2) tank model.

Physics-based tank sizing (structure + multi-layer insulation, after Svensson et al.) and a
transient ``time_step`` model of the tank thermodynamic state — self-pressurization from
heat ingress, venting at the maximum pressure, and heater power at the minimum pressure.

This module requires **CoolProp** (for para-hydrogen properties) and is therefore an
*optional* dependency: it is imported lazily where needed (e.g. ``Weight.Hydrogen`` falls
back to a simple gravimetric-index tank model when CoolProp is unavailable). Importing this
package without CoolProp raises ImportError by design.
"""

from .Tank import LH2_Tank, get_isa_atmosphere
from .TANK_Database import TANK_Database

__all__ = ["LH2_Tank", "get_isa_atmosphere", "TANK_Database"]
