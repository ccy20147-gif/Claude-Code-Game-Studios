---
name: ue5-accept-baseline
description: Validate and accept a versioned UE5 game design baseline before work planning or phase advancement. Use when promoting a concept, intake bundle, or design package from candidate to approved production truth.
---

# Accept A Design Baseline

Read `../../references/state-contract.md` and validate `../../schemas/baseline.schema.json`. Freeze semantics, invariants, budgets, content structure, persistence boundaries, and tuning ranges; do not freeze untested final numbers. A baseline with unresolved high-risk assumptions remains `CANDIDATE`.

Report missing traceability, unowned requirements, profile-specific gaps, stale evidence, and invalid mode transitions. A FAIL blocks advancement unless the user explicitly records a scoped waiver with owner, expiry, and remediation. Write `ACCEPTED` status only after direct user approval.
