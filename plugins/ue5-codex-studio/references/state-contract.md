# State Contract

Treat YAML under `.ue5-codex-studio/`, `intake/`, `design/`, and `production/` as workflow truth. Markdown is a source or view and cannot override structured records.

Use stable IDs: `source_span_`, `adapt_`, `req_`, `character_`, `beat_`, `line_`, `clue_`, `cue_`, `system_`, `work_`, and `evidence_`. Do not renumber an ID because prose changes or a file moves. Model a deletion with a tombstone and an optional replacement alias.

The trace chain is `source_span -> adaptation_decision -> game_requirement -> design/ADR/work_item -> capability -> evidence`. A capability record must distinguish its static support status from runtime availability. An editor mutation needs evidence at the required level: `ACK`, `OBSERVED`, `PERSISTED`, or `RUNTIME`. A timeout is `UNKNOWN`, not a failed mutation that can be blindly retried.

Plan editor work through a stable `operation_` record with `capability_id`, intent, execution profile, preconditions, and required evidence; do not persist a dynamic MCP tool slug in design state. An operation backed by `THIN_MCP_EXTENSION` can become `READY` only with an approval record, a passing server-side policy canary, fail-closed schema-drift handling, and independent readback. Dynamic tool resolution belongs only in evidence with its backend version, instance ID, catalog generation, and schema hash.

Profiles are orthogonal: experience (`systemic`, `linear`, `hybrid`), presentation (`2d`, `2.5d`, `3d`), investigation (`none`, `clue-graph`, `spatial`), runtime (`single`, `multiplayer`), and operations (packaged plus optional live-service/moddable). The project profile also stores independent music, SFX, text-dialogue, source-VO, and localized-VO flags.

Do not enter maintenance without a production baseline. Do not enter hotfix without a deployed build identity. A `FAIL` gate needs an explicit waiver with scope, rationale, expiry, owner, and remediation; `solo` review does not waive objective evidence.
