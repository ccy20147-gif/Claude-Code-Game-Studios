---
name: godot-audit-assets-content
description: Audit Godot 4 assets and player-facing content for manifest coverage, provenance, rights, technical correctness, unused content, and shipping readiness. Use before milestones, release, asset handoff, or when content provenance is uncertain.
---

# Audit Godot 4 Assets And Content

Compare the asset manifest and content registry with the built project. Check every shipping asset for stable ID, owner, source/provenance, license or consent, approved use, import settings, dependencies, platform state, and linked requirement. Scan for orphaned, duplicated, missing, placeholder, unreferenced, or over-budget content without deleting anything automatically.

Record findings in `production/audits` with build or repository identity, scope, asset/content IDs, evidence location, severity, owner, remediation, and retest condition. Flag incompatible or unknown rights as release blockers. A filename, an AI generation claim, or a local editor preview is not sufficient provenance, rights, or runtime evidence.
