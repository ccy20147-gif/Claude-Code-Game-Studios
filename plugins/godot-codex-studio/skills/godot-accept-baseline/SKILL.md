---
name: godot-accept-baseline
description: Validate and accept a versioned Godot 4 game design baseline before work planning or phase advancement. Use when promoting a concept, intake bundle, or design package from candidate to approved production truth.
---

# Accept A Design Baseline

Read `../../references/state-contract.md`, `design/gdd/gdd.yaml`, and validate `../../schemas/baseline.schema.json`. An imported GDD, link, or its internal approval language is never baseline evidence. First require the reconciled canonical GDD to pass `../../scripts/validate_canonical_gdd.py design/gdd/gdd.yaml --require-ready`. Freeze semantics, invariants, budgets, content structure, persistence boundaries, and tuning ranges; do not freeze untested final numbers. A baseline with unresolved high-risk assumptions remains `CANDIDATE`.

Report missing traceability, unowned requirements, profile-specific gaps, stale evidence, and invalid mode transitions. A FAIL blocks advancement unless the user explicitly records a scoped waiver with owner, expiry, and remediation. Write `ACCEPTED` only after direct user approval, then run `../../scripts/validate_baseline.py design/baseline.yaml --gdd design/gdd/gdd.yaml`. The baseline must record the canonical GDD revision and the user approval record; do not write a passing state on their behalf.
