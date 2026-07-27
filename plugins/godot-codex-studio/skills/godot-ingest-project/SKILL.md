---
name: godot-ingest-project
description: Inspect existing game design files, source code, web links, or Godot 4 projects and convert them into a traceable Godot Codex Studio intake bundle. Use when adopting a design pack, prototype, or brownfield Godot project.
---

# Ingest A Godot Project

Read `../../references/state-contract.md`. Begin with `../../scripts/inspect_project_intake.py <root> --output <bundle>`; it is read-only except for the named generated bundle. Detect `project.godot`, `.tscn`, `.tres`, `.res`, GDScript, C#, export presets, and addons. Treat resources requiring the editor as `UNKNOWN`; never infer their semantic contents from paths or filenames.

Produce source provenance, implementation facts, design intent, conflicts, confidence, and open questions. Preserve any external `approved` or `passed` statement only as an unverified source claim. It cannot set baseline status or skip GDD reconciliation. Present conflicts and a proposed authority map before writing generated intake artifacts.

Route fiction to `$godot-adapt-story`. Route every design pack or hybrid design input through `$godot-reconcile-gdd` before `$godot-accept-baseline`. An intake bundle is review evidence, never an accepted design baseline.
