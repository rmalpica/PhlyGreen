# Aircraft Model

This page documents the `Aircraft` class, the central container that coordinates **constraint**, **mission**, **performance**, **systems**, **weight**, **climateimpact**, and **well‑to‑wake** modules in PhlyGreen.

---

## Overview

The `Aircraft` class is responsible for:

- Storing all high‑level aircraft configuration and inputs  
- Initializing subsystem models 
- Passing inputs between these subsystems  
- Coordinating the full simulation workflow

It acts as a *data and logic hub*, ensuring that all parts of the framework work with consistent and synchronized parameters.

---

## Key Attributes

### Configuration Parameters

- `Name` — aircraft name  
- `Configuration` — `"Traditional"` or `"Hybrid"`  
- `HybridType` — `"Serial"` or `"Parallel"` (if hybrid)  
- `Class` — weight estimation fidelity: `"I"` (simplified) or `"II"` (FLOPS‑based)
- `AircraftType` — structural model selection


### Sub‑Models

The Aircraft object instantiation requires instances of the submodules classes as arguments:

- `Systems.Powertrain` — gas‑turbine/electric/hybrid power models  
- `Systems.Structures` — structural weight estimation model
- `Systems.Aerodynamics` — aerodynamic polar model 
- `Performance` — aircraft performance equations  
- `Mission` — mission simulation module and mission profile 
- `Weight` — global mass iteration loop 
- `Constraint` — constraint diagram equations 
- `WellToWake` — well‑to‑wake energy model (fuel + battery)
- `Battery` — battery electro‑thermal model  
- `ClimateImpact` — climate impact model


Each is wired to the same parent aircraft instance.

![Aircraft Model](../images/mediator.png){ .img-left}

