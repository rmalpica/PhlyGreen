"""Hydrogen fuel-cell models.

Currently exposes the fuel-cell parameter database (``FC_Database``, Kulikovsky-based PEM
models). The fuel cell participates in the powertrain as an energy source; see the
``fuelcell_battery_graph`` architecture in
:mod:`PhlyGreen.Systems.Powertrain.graph` and the fuel-cell + battery power-ratio method
on :class:`~PhlyGreen.Systems.Powertrain.Powertrain.Powertrain`.

The full electrochemical sizing/weight model and the cryogenic LH2 tank (which require
``CoolProp``) are integrated through the efficiency-model interface and remain optional /
dependency-gated.
"""

from .FC_Models import FC_Database

__all__ = ["FC_Database"]
