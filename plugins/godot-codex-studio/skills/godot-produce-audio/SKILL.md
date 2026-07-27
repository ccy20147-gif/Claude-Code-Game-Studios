---
name: godot-produce-audio
description: Produce and integrate approved game music, SFX, dialogue, and voice-over through a traceable provider-neutral workflow. Use after audio design is accepted and production assets or takes are ready.
---

# Produce Audio And Voice

Read the audio bible and work item. Track source, license or consent, contributor, version, technical QC, loudness, and delivery file for every asset. Preserve `line_id -> locale -> approved translation -> take -> cue_id -> Godot asset` links; a changed line or translation becomes stale through `$godot-change-design`.

Do not represent a generated clip, TTS output, or MCP cue edit as a finished voice production. Require approved rights, take QC, subtitle timing, lip-sync state where applicable, and in-game trigger/readback evidence. Keep raw recordings and packaged builds in the configured evidence store, not ordinary Git.
