---
name: ue5-change-design
description: Classify a UE5 game-design or narrative revision and propagate precise stale-state impacts through requirements, localization, VO, levels, tests, and evidence. Use when changing a line, clue, scene, rule, baseline, or game-design document.
---

# Change A Design Safely

Read `../../references/state-contract.md` and the trace graph. Classify the revision as `COPY_EDIT`, `CONTENT_EDIT`, or `STRUCTURAL`. Copy edits update source hashes and review-dependent media; content edits require impact review; structural changes create tombstones or aliases for removed IDs and evaluate save/reference migration.

Use `../../templates/change-ledger.yaml`, then run `../../scripts/validate_change_ledger.py production/change-ledger.yaml`. Mark only downstream dependent nodes stale, including string keys, translations, subtitles, VO takes, cues, sequences, clues, level triggers, work items, tests, and evidence where affected. Never silently delete history, mark stale work complete, or expand an accepted baseline without approval. Present the impacted set and required revalidation before writing `production/change-ledger.yaml` or superseding a baseline.
