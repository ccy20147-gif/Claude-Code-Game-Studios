---
name: godot-review-design
description: Review Godot 4 game design, narrative, systems, scope, and cross-discipline consistency against an accepted baseline. Use for design reviews, GDD reviews, scope checks, and pre-production or release gates.
---

# Review Godot 4 Design

Read the project profile, accepted baseline, trace graph, and affected design artifacts. Check each requirement for player-facing intent, owner, dependency, implementation path, measurable acceptance evidence, and conflict with narrative, level, UX, art, audio, persistence, simulation, localization, or platform constraints. Evaluate scope against the proven vertical slice and current capacity, not aspirational future work.

Write findings with stable IDs, severity, evidence, owner, disposition, and recheck condition to `production/reviews`. Distinguish a missing decision from a defect and a deferred item from an accepted requirement. A review recommends `PASS`, `FAIL`, or `CONDITIONAL`; only the baseline approval workflow can accept a scope or creative decision, and a `FAIL` needs an explicit scoped, expiring waiver.
