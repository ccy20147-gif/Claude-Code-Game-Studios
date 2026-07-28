---
name: ue5-accept-baseline
description: Validate and accept a versioned UE5 game design baseline before work planning or phase advancement. Use when promoting a concept, intake bundle, or design package from candidate to approved production truth.
---

# Accept A Design Baseline

Read `../../references/state-contract.md`, `design/gdd/gdd.yaml`, and validate schema version 2 `design/baseline.yaml`. An imported GDD, link, or its internal approval language is never baseline evidence. First require the canonical GDD to pass `../../scripts/validate_canonical_gdd.py design/gdd/gdd.yaml --require-ready`. Create `design/profile-delivery.yaml` from its template and link the current project profile hash. Freeze semantics, invariants, budgets, content structure, persistence boundaries, and tuning ranges; do not freeze untested final numbers. A baseline with unresolved high-risk assumptions remains `CANDIDATE`.

Report missing traceability, unowned requirements, profile-specific gaps, stale evidence, and invalid mode transitions. A FAIL blocks advancement unless the user explicitly records a scoped waiver with owner, expiry, and remediation. Write `ACCEPTED` only after direct user approval, then run `../../scripts/validate_baseline.py design/baseline.yaml --require-accepted --profile-delivery design/profile-delivery.yaml --require-profile-delivery`. Record the canonical GDD ID, revision, and SHA-256; do not write a passing state on the user's behalf.
