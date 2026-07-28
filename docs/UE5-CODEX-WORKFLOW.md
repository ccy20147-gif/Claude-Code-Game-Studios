# UE5 Codex Studio Workflow

Use this guide for the current `ue5-codex-studio` plugin. It is the authoritative user-facing workflow; `WORKFLOW-GUIDE.md` documents the archived Claude Code slash-command system.

## Start And Resume

Begin with `$ue5-start-project`. It first reports whether the installed plugin matches the repository version, then either resumes `.ue5-codex-studio/project.yaml` or creates a schema version 2 project state after approval.

The project state records its current phase, blockers, pending decisions, artifact references, and active work. Run `$ue5-start-project` again after an interruption; do not re-run intake manually unless the inspector identifies intake as the required action.

## Core New-Project Path

```
empty -> conceive -> reconcile-gdd -> accept-baseline -> map-systems -> plan-work -> READY work item
story -> adapt-story -> reconcile-gdd -> accept-baseline -> map-systems -> plan-work -> READY work item
design/UE project -> ingest -> reconcile-gdd -> accept-baseline -> map-systems -> plan-work -> READY work item
```

`$ue5-reconcile-gdd` builds the same canonical GDD from concepts, narrative intake, implementation facts, external design documents, or hybrid input. A source file's approval language never accepts a baseline.

## Review And Automation Boundaries

`solo` and `lean` modes save reversible work as `DRAFT` and show assumptions. Concept selection, baseline acceptance, scope expansion, paid generation, waivers, and external operations always require explicit approval.

The current release target is `READY_TO_RELEASE`, not store submission or deployment. Editor, DCC, and packaging capabilities must be treated according to their runtime availability in `catalog/capabilities.yaml`; `CANARY_ONLY`, `BLOCKED`, and `MANUAL` capabilities are not general automation.
