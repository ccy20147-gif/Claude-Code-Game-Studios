---
name: ue5-spec-assets
description: Convert approved UE5 art, level, narrative, and audio requirements into traceable asset specifications and import contracts. Use before producing models, textures, sprites, animation, audio, or other game assets.
---

# Specify Assets

Read the art bible, level specs, and baseline. Assign stable `asset_id` values and define source requirement, owner, format, license/provenance, platform budget, import settings, scale/pivot/axis, LOD/collision, naming, reimport behavior, and acceptance evidence.

For audio, preserve `line_id` and `cue_id` links rather than encoding semantics in filenames. For 2D assets, declare pixels-per-unit, filter/compression, atlas, pivot, collision, and tile seam constraints. Consult `../../catalog/capabilities.yaml`; an import or editor write may still be manual or require a thin MCP extension.
