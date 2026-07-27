---
name: godot-audit-security
description: Audit Godot 4 game and automation security, including save tampering, network authority, secrets, MCP action exposure, and release risks. Use before public release, multiplayer work, MCP provisioning, or when assessing a security concern.
---

# Audit Security

Perform a read-only audit first. Report severity, exploit path, affected build, evidence, owner, mitigation, and retest requirement. Check Autoload + user:// trust boundaries, replication authority, input validation, secret storage, logs, artifact provenance, and third-party asset/voice rights.

For MCP, require loopback, non-default secret handling, server-side action allowlists, schema-drift fail closed behavior, and independent mutation readback. Codex `disabled_tools` is not a sufficient security boundary. Never place capability tokens in tracked `DefaultGame.ini`; token absence must fail closed.
