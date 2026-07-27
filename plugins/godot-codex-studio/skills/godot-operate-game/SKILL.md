---
name: godot-operate-game
description: Plan and run post-release Godot 4 game operations, player support, telemetry governance, maintenance, live events, and rollback escalation. Use after a release is deployed or when preparing a live-service or supported shipped game.
---

# Operate A Godot 4 Game

Require deployed build identity and production baseline before starting operations. Define support channels, incident severity and response ownership, health signals, privacy and retention limits, telemetry consent, alert thresholds, maintenance cadence, content/event approval path, rollback triggers, and player communication templates. Treat telemetry as an optional observability input, not a substitute for consent or reproducible player reports.

Maintain operational records under `production/operations` with observation time, build, platform, signal source, confidence, impact, owner, decision, and follow-up. Route a released-build defect to `$godot-hotfix-game`; route planned work to `$godot-plan-work`; route scope changes through `$godot-change-design`. Do not report a live metric, deployment, or player outcome without external evidence; use `UNKNOWN` for timeouts or incomplete observations.
