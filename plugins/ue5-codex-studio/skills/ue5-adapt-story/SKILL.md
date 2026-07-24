---
name: ue5-adapt-story
description: Convert a novel, screenplay, Fountain script, DOCX, text PDF, or FDX file into a traceable UE5 game-design intake bundle. Use when adapting fiction into gameplay, narrative, characters, levels, clues, audio, and downstream production work.
---

# Adapt Fiction Into A Game

Read `../../references/state-contract.md`. Use `../../scripts/import_narrative.py SOURCE --output intake/source-spans.yaml` to normalize supported input into source spans before analysis. Do not OCR scans, guess unreadable pages, or present partial extraction as complete.

Build `design/narrative-registry.yaml` from `../../templates/narrative-registry.yaml`, then run `../../scripts/validate_narrative_registry.py design/narrative-registry.yaml --source intake/source-spans.yaml`. Its coverage must account for every chapter or scene as `mapped`, `excluded`, or `deferred`. Extract canon facts, timeline, characters, beats, locations, conflicts, interactive affordances, state variables, and audio/VO implications. Keep each requirement traceable to a source span.

Separate canon from adaptation. Record every departure as `preserve`, `compress`, `reorder`, `cut`, or `invent`; require explicit approval for `invent`. Define player actions, success, failure/cost, and feedback before calling an adaptation gameable. Offer gameplay candidates and profile choices, then write the source manifest, narrative registry, and intake bundle after approval. Route mystery games to `$ue5-design-investigation`, then use `$ue5-map-systems` and `$ue5-accept-baseline`.
