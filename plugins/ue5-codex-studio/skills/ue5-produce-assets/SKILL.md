---
name: ue5-produce-assets
description: Produce, integrate, and quality-check approved UE5 visual, animation, VFX, UI, and technical-art assets with source, rights, performance, and runtime evidence. Use after asset specifications are accepted and a production work item is ready.
---

# Produce UE5 Assets

Read the accepted asset manifest, art bible, work item, and target-platform budget before production. For every deliverable record stable asset ID, source or generation provenance, rights, author, version, import settings, dependencies, LOD/material/texture budget, and destination UE asset. A generated image, mesh, or cloud output is `PENDING_LOCAL_VALIDATION` until it is checked locally and its import is observed.

Separate source creation from UE integration. Validate naming, scale, pivots, collision, animation/VFX behavior, materials, references, and runtime performance in the intended representative journey. Require independent editor readback and package/runtime evidence for an asset that changes gameplay, readability, accessibility, or performance. Do not use Blender or UE MCP write automation until its server-side action boundary is approved and canaried.

The controlled AtlasCloud path exposes only locked GPT Image 2 text-to-image, approval-required GPT Image 2 editing, and Hunyuan 3D Pro image-to-3D. Start its credential session at runtime so the API key remains process-local. Treat downloaded images and meshes as immutable candidates, validate cloud-generation evidence, and run `validate_generated_mesh.py` before DCC work. The stricter `validate_gltf_asset.py` applies only after retopology, UV, LOD, material, collision, and any rigging work is complete.
