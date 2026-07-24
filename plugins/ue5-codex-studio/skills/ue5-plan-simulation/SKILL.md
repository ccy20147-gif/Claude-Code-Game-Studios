---
name: ue5-plan-simulation
description: Plan systemic sandbox simulation with stable entities, deterministic owned subsystems, persistence, and soak evidence. Use for Kenshi-like worlds, AI jobs, population simulation, economy simulation, or long-running systemic gameplay.
---

# Plan A Simulation

Use `../../templates/simulation.yaml`. Define stable entity IDs, simulation layers, job ownership, near/far/hibernated transitions, data references, event log, seed, checksum scope, error tolerance, and 2/8/24-hour soak scenarios.

Only promise determinism for the owned subsystem's seeded PRNG and logged state. Explicitly exclude Unreal physics, rendering, and other nondeterministic engine components. Couple the plan to `$ue5-plan-persistence` and require replay or declared tolerance evidence before acceptance.
