---
name: ue5-plan-persistence
description: Design UE5 SaveGame and content-state persistence with stable IDs, migration paths, corruption handling, and compatibility tests. Use for saves, quests, narrative state, simulation state, versioned content, or schema migrations.
---

# Plan Persistence

Use `../../templates/persistence.yaml` and run `../../scripts/validate_persistence.py`. Define save ownership, stable references, serialization boundaries, schema version, migration operations, corruption behavior, checkpoint policy, and observability. Do not serialize display names or file paths as authoritative IDs.

For released games, require tested paths from the previous two schema versions to the current version, plus corruption and missing-content behavior. A structural content deletion must leave a tombstone or alias and pass through `$ue5-change-design` before any save claim is accepted.
