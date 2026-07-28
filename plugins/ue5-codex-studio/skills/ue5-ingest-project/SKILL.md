---
name: ue5-ingest-project
description: Inspect existing game design files, source code, web links, or Unreal Engine 5 projects and convert them into a traceable UE5 Codex Studio intake bundle. Use when adopting a design pack, prototype, or brownfield UE5 project.
---

# Ingest A Project

Read `../../references/state-contract.md`. Begin with `../../scripts/inspect_project_intake.py <root>`; it is read-only unless an explicit generated output path is supplied. Inventory user files, preserve their hashes, and detect UE structures including `.uproject`, `Source`, `Content`, `Config`, and `Plugins`. Treat unreadable binary assets as `UNKNOWN`; use an approved Asset Registry or MCP read operation later, never claim their contents from filenames.

Produce a source manifest and intake bundle with provenance, implementation facts, design intent, conflicts, confidence, and open questions. Preserve any external `approved` or `passed` statement as an unverified source claim; it cannot set baseline status or skip GDD work. Never overwrite user documents or silently make implementation match prose. Present conflicts and a proposed authority map first; write generated intake artifacts only after approval.

Route fiction to `$ue5-adapt-story`. Route design packs, design links, hybrid input, and implementation-only projects through `$ue5-reconcile-gdd` with the detected or user-confirmed source kind before `$ue5-accept-baseline`; use `$ue5-map-systems` only after the reconciled GDD is accepted. An intake bundle is evidence for review, not an accepted design baseline.
