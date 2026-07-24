---
name: ue5-ingest-project
description: Inspect existing game design files, source code, or Unreal Engine 5 projects and convert them into a traceable UE5 Codex Studio intake bundle. Use when adopting a design pack, prototype, or brownfield UE5 project.
---

# Ingest A Project

Read `../../references/state-contract.md`. Begin with `../../scripts/inspect_project_intake.py <root>`; it is read-only unless an explicit generated output path is supplied. Inventory user files, preserve their hashes, and detect UE structures including `.uproject`, `Source`, `Content`, `Config`, and `Plugins`. Treat unreadable binary assets as `UNKNOWN`; use an approved Asset Registry or MCP read operation later, never claim their contents from filenames.

Produce a source manifest and intake bundle with provenance, implementation facts, design intent, conflicts, confidence, and open questions. Never overwrite user documents or silently make implementation match prose. Present conflicts and a proposed authority map first; write generated intake artifacts only after approval. Route a fiction source to `$ue5-adapt-story`, design gaps to `$ue5-map-systems`, and an accepted bundle to `$ue5-accept-baseline`.
