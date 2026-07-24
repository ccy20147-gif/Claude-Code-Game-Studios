---
name: ue5-design-architecture
description: Define and review UE5 technical architecture and ADRs from accepted game requirements. Use for module boundaries, Blueprint/C++ choices, persistence, networking, build pipelines, data ownership, and engine integration decisions.
---

# Design UE5 Architecture

Create one ADR per consequential decision with requirement IDs, alternatives, consequences, UE 5.7.4 compatibility, migration/rollback, test evidence, and status. Define module boundaries, data ownership, Blueprint/C++ seams, asset/data validation, build/cook/package route, and security boundaries.

Do not encode unsafe MCP access as an architecture shortcut. UE and Blender editor writes must reference operation-level capabilities and their required evidence. Accepted ADRs produce a compact control manifest for later work items; architecture changes use `$ue5-change-design` and may supersede the baseline.
