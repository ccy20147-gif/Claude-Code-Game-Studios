---
name: godot-localize-content
description: Manage Godot 4 game localization across strings, subtitles, UI, cultural review, and localized voice production. Use when adding locales, translating content, freezing strings, or validating localization coverage.
---

# Localize Game Content

Use stable text and line IDs, never source-language strings or filenames, as translation keys. Record source locale, target locales, review state, context, character/scene, max UI space, and content lock state. Treat localized VO as a derived production chain after approved translation, not as a separate unlinked recording task.

On a text revision, mark only affected translations, subtitles, takes, lip-sync, sequences, and tests stale. Block release when a shipping locale has missing/orphan mandatory strings, unapproved required takes, or a string-freeze violation without an explicit waiver.
