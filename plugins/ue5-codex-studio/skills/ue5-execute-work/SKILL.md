---
name: ue5-execute-work
description: Implement and complete an approved UE5 work item with scoped changes, capability preflight, review, and normalized evidence. Use after a work item is READY and its baseline revision is current.
---

# Execute Work

Read the work item, baseline, requirements, architecture, and control constraints. Verify the item is `READY`, matches the current baseline revision, and has no unresolved capability or security blocker. Implement within the approved scope, then run the required tests and collect evidence.

For an MCP mutation, use the native Codex tool, perform independent readback, and save/reload or run runtime verification as required. A timeout is `UNKNOWN`; do not retry blindly. Mark `DONE` only when every acceptance condition has evidence. Return scope growth, stale requirements, or missing external evidence to `BLOCKED` or `PENDING_LOCAL_VALIDATION`.
