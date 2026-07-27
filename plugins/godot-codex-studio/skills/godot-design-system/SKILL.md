---
name: godot-design-system
description: Create or revise a testable Godot 4 game-system specification from an accepted baseline. Use for mechanics, economy, combat, progression, interaction, UI state, or other game rules.
---

# Design A System

Read `../../references/state-contract.md`, the baseline, and `design/system-map.yaml`. Give each specification a stable `system_id` and define player outcome, rules, formulas, boundaries, dependencies, edge cases, tuning ranges, persistence implications, required capabilities, and measurable evidence.

For a small approved change, create a focused delta linked to the affected requirement rather than cloning the whole specification. For unresolved game feel or feasibility, create a prototype hypothesis instead of pretending a number is final. Present the spec for approval before writing under `design/systems/`.
