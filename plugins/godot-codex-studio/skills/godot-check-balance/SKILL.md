---
name: godot-check-balance
description: Evaluate Godot 4 combat, economy, progression, difficulty, rewards, and systemic balance with declared models and player evidence. Use when tuning game variables, validating a progression curve, or reviewing balance regressions.
---

# Check Godot 4 Balance

Read the accepted system specification, simulation contract if present, and target player profiles. State the mechanic, controlled variables, initial conditions, seed, model assumptions, target outcome, and failure thresholds before changing values. Use calculations or deterministic owned-subsystem simulations to expose ranges and exploits, then validate player-facing behavior in the relevant runtime journey.

Record test cases, input data, build identity, observed outcomes, variance, exploit or accessibility risks, recommendation, and linked requirements in `production/balance`. Keep tuning data separate from prose and version every accepted table. Do not make a balance claim from a single playthrough, hide a dominant strategy in an average, or label a subjective preference as an objective balance defect.
