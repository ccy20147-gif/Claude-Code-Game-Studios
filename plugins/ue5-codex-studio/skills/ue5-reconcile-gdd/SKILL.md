---
name: ue5-reconcile-gdd
description: Reconcile external GDD documents, design packs, and readable design links into the canonical UE5 Codex Studio GDD before baseline acceptance. Use after importing existing design material, when an external document claims approval, or when gaps and conflicts need iterative user decisions.
---

# Reconcile An Imported GDD

Read `../../references/state-contract.md` and start from the intake bundle. Read every accessible user-provided GDD document and the content of every accessible design link, not merely filenames, headings, or status labels. Record each extracted statement with its source reference and local section/anchor. Use `../../templates/canonical-gdd.yaml` to create `design/gdd/gdd.yaml`; preserve source files and never overwrite them.

Treat every external status, sign-off, review result, and "passed baseline" statement as an `external_claim` with disposition `UNVERIFIED`, `IGNORED`, or `REJECTED`. It is evidence about the source, not Codex Studio approval. For a supplied URL, read it only when accessible, record the resolved URL, retrieval time, and content fingerprint in `source_refs`; when access is unavailable or requires credentials, ask the user for an export or the relevant text instead of inventing content.

Extract and reconcile the nine canonical sections: vision, core loop, scope, systems, content, UX/accessibility, art/audio, technical, and validation. Link each extracted statement to a source reference. Mark a section `NOT_APPLICABLE` or `DEFERRED` only with a user decision record; never use either status to hide a missing decision.

Ask focused questions in dependency order. Offer 2-4 materially different options where useful and always allow a user-supplied answer. Do not set a round limit: keep `questions` open and continue across as many turns as needed. If the user pauses, preserve the open questions and keep the GDD `DRAFT` or `RECONCILING`; do not advance it. Confirm each answer, update only the affected section, and show the changed requirement or scope implication.

Before proposing baseline review, run:

```bash
python3 ../../scripts/validate_canonical_gdd.py design/gdd/gdd.yaml --require-ready
```

Set `READY_FOR_BASELINE` only when every section is confirmed or explicitly decided, no question is open, every external claim is resolved or ignored, and the user directly confirms the reconciled GDD. Then route to `$ue5-accept-baseline`. Use `$ue5-design-system`, `$ue5-design-narrative`, `$ue5-design-level`, `$ue5-design-art`, `$ue5-design-audio`, and `$ue5-design-ux` after baseline acceptance to expand the relevant canonical decisions into detailed specs.
