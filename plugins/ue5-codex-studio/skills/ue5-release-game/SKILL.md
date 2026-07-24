---
name: ue5-release-game
description: Prepare, validate, approve, and document a UE5 game release with immutable build identity, platform evidence, player communications, and rollback readiness. Use for milestone, beta, early-access, or public release candidates.
---

# Release A UE5 Game

Create a release record in `production/releases` with immutable source revision, engine and toolchain lock, package hashes, target platforms, distribution channel, known issues, owner, approval authority, rollback artifact, and go/no-go criteria. Run the accepted release checklist: fresh install and launch, target-platform packaging, smoke and regression, save compatibility, performance, security, accessibility, localization, asset/content rights, and required legal/store checks.

Release only when each required gate is `PASS` or has a scoped, expiring waiver with owner and remediation. Generate changelog and player-facing notes from accepted issue and work records; do not invent shipped behavior. Before an external distribution event is evidenced, report `READY_TO_RELEASE`, not `RELEASED`; after release, hand off monitored risks, support paths, and rollback triggers to `$ue5-operate-game`.
