---
name: ue5-audit-accessibility
description: Audit UE5 player journeys for accessible input, text, visual, audio, cognitive, motion, and failure-recovery behavior with runtime evidence. Use while designing UX, validating a vertical slice, addressing accessibility feedback, or preparing release.
---

# Audit UE5 Accessibility

Audit representative journeys from first launch through settings, tutorial, core loop, failure/recovery, and credits or completion. Cover remapping and hold/toggle alternatives, readable scalable text, contrast and non-color signals, captions/subtitles and audio controls, motion and camera options, pacing, clear objectives, recoverable errors, and save behavior. Treat genre-specific needs such as clue recall, time pressure, stealth, combat, or systemic simulation as first-class scenarios.

Write `production/accessibility` findings with journey, affected capability, platform, reproduction steps, build identity, evidence, severity, owner, and acceptance retest. Do not claim support because a setting exists: demonstrate its effect in packaged runtime. Escalate blocked core progression and data-loss risks before cosmetic deviations; route design changes through `$ue5-change-design`.
