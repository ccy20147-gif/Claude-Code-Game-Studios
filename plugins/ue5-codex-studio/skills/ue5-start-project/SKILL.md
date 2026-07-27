---
name: ue5-start-project
description: Route a new or existing Unreal Engine 5 game project into the correct UE5 Codex Studio workflow. Use when starting from no idea, a story, design files, a UE project, or when the user asks what to do next.
---

# Start A UE5 Project

Read `../../references/state-contract.md` before creating state. Inspect the workspace without modifying it, then classify these independent axes: creative origin, implementation state, lifecycle, execution mode, profiles, source/target locales, and shipping targets.

Do not infer `maintenance` or `hotfix` without an accepted production baseline; hotfix also requires a deployed build identity. Present the resulting project profile and the recommended active skill. On approval, create `.ue5-codex-studio/project.yaml` from `../../templates/project.yaml` and record all assumptions.

Route `empty` to `$ue5-conceive-game`, `narrative` to `$ue5-adapt-story`, and design or implementation inputs to `$ue5-ingest-project`. A design pack continues through `$ue5-reconcile-gdd` before baseline acceptance; do not inherit its internal review labels. Use `standard` unless the user explicitly selects an isolated prototype, maintenance, or hotfix workflow.
