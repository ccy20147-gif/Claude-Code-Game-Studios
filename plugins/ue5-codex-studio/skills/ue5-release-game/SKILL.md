---
name: ue5-release-game
description: Prepare, validate, approve, and document a UE5 game release with immutable build identity, platform evidence, player communications, and rollback readiness. Use for milestone, beta, early-access, or public release candidates.
---

# Release A UE5 Game

Create `production/releases/RELEASE.yaml` from `../../templates/release.yaml` with immutable source revision, baseline and toolchain hashes, package hashes, target platforms, known issues, rollback artifact, gates, evidence, and scoped waivers. Run `../../scripts/validate_release.py RELEASE.yaml --require-ready`. Run the accepted release checklist: fresh install and launch, target-platform packaging, smoke and regression, save compatibility, performance, security, accessibility, localization, asset/content rights, and legal checks.

Release records may end only at `READY_TO_RELEASE`; this plugin does not submit to a store, deploy a build, or record `RELEASED`. Each required gate must be `PASS` or have a scoped, expiring waiver with owner and remediation. Generate changelog and player-facing notes from accepted issue and work records; do not invent shipped behavior. `$ue5-operate-game` remains available only after externally evidenced deployment.
