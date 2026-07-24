---
name: ue5-design-audio
description: Create a provider-neutral game audio and voice design, including cues, mixing, accessibility, localization, and UE integration requirements. Use for music, SFX, dialogue, voice-over, audio bibles, or adaptive sound design.
---

# Design Audio And Voice

Use `../../templates/audio-bible.yaml` and run `../../scripts/validate_audio_bible.py`. Define buses, loudness targets, adaptive music rules, cue ownership, gameplay triggers, captions, visual alternatives for critical audio, and rights/provenance. Keep `cue_id` separate from media filenames.

For VO, link `line_id -> locale -> approved translation -> take -> cue -> UE asset`. Require performer or synthesis consent, pronunciation, technical QC, subtitle timing, and lip-sync state before release. Music/SFX/VO production remains provider-neutral and `MANUAL_REQUIRED` until a concrete provider is approved; do not claim that MetaSounds or MCP completes recording or mastering.
