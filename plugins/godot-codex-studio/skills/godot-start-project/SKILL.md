---
name: godot-start-project
description: Route a new or existing Godot 4 game project into the correct Godot 4 Codex Studio workflow. Use when starting from no idea, a story, design files, a Godot project, or when the user asks what to do next.
---

# Start A Godot 4 Project

Read `../../references/state-contract.md` before creating state. Inspect the workspace without modifying it, then classify these independent axes: creative origin, implementation state, lifecycle, execution mode, profiles, source/target locales, and shipping targets.

Do not infer `maintenance` or `hotfix` without an accepted production baseline; hotfix also requires a deployed build identity. Present the resulting project profile and the recommended active skill. On approval, create `.godot-codex-studio/project.yaml` from `../../templates/project.yaml` and record all assumptions.

Route `empty` to `$godot-conceive-game`, `narrative` to `$godot-adapt-story`, and design or implementation inputs to `$godot-ingest-project`. A design pack continues through `$godot-reconcile-gdd` before baseline acceptance; do not inherit its internal review labels. Use `standard` unless the user explicitly selects an isolated prototype, maintenance, or hotfix workflow.
