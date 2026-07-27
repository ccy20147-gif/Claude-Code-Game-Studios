---
name: godot-design-narrative
description: Build a playable narrative specification from a story intake, including beats, characters, scenes, dialogue state, and content dependencies. Use for narrative adventures, quests, branching story, dialogue, or lore systems.
---

# Design A Playable Narrative

Read `../../references/state-contract.md`, source spans, adaptation decisions, and the accepted baseline. Keep `character_id`, `beat_id`, `scene_id`, and `line_id` stable. Describe the player's agency at each beat, state changes, fail/return paths, pacing target, entry/exit conditions, localization scope, and audio/VO implications.

Do not make plot text the only source of gameplay behavior. Tie each interactive scene to requirements, systems, level placement, and tests. Preserve spoilers in the main graph; create a separate fresh-tester export with only visible information when the project has an investigation profile. Write narrative records only after approval.
