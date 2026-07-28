---
name: ue5-start-project
description: Route a new or existing Unreal Engine 5 game project into the correct UE5 Codex Studio workflow. Use when starting from no idea, a story, design files, a UE project, or when the user asks what to do next.
---

# Start A UE5 Project

Run `../../scripts/check_plugin_install.py` first. If it reports `STALE`, `NOT_INSTALLED`, or `DISABLED`, continue read-only diagnosis but require reinstall and a new Codex thread before creating workflow truth. Read `../../references/state-contract.md`, then inspect the workspace without modifying it. If `.ue5-codex-studio/project.yaml` exists, run `../../scripts/inspect_workflow_state.py` and resume its required action rather than re-ingesting the project.

For a new project, classify creative origin, implementation state, lifecycle, execution mode, profiles, source/target locales, and shipping targets. Preserve unknown choices as `unknown` or empty values rather than assuming a genre, platform, or locale. Do not infer `maintenance` or `hotfix` without an accepted production baseline; hotfix also requires a deployed build identity. On approval, create schema version 2 `.ue5-codex-studio/project.yaml`, validate it with `../../scripts/validate_project.py --require-current`, and record assumptions.

Route `empty` to `$ue5-conceive-game`, `narrative` to `$ue5-adapt-story`, and design or implementation inputs to `$ue5-ingest-project`. Every new-source route converges on `$ue5-reconcile-gdd` before baseline acceptance; do not inherit external approval labels. Use `standard` unless the user explicitly selects an isolated prototype, maintenance, or hotfix workflow.
