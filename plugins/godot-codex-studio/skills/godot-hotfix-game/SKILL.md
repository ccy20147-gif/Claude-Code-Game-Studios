---
name: godot-hotfix-game
description: Triage, implement, validate, and document a Godot 4 hotfix from a deployed build with rollback readiness. Use only for a live issue against a released build.
---

# Run A Hotfix

Require deployed build identity, reproducible issue evidence, severity, affected platforms, rollback artifact, owner, and observation window before implementation. A hotfix is not valid for an unreleased project; route that work through maintenance or standard production.

Validate the fix against the deployed base, prove the regression no longer reproduces in the release candidate, run adjacent regression and target-platform cook/package checks, and record post-deploy health observations. Without external deployment evidence report `READY_TO_DEPLOY`, never `DEPLOYED`. Reconcile the accepted baseline and outstanding debt after the incident.
