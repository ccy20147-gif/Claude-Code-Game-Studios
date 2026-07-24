---
name: ue5-setup-toolchain
description: Check and prepare the UE5 Codex Studio toolchain for Unreal Engine, Blender, Codex, and optional local MCP automation. Use when configuring a workstation, checking tool versions, or planning approved MCP provisioning.
---

# Set Up The UE5 Toolchain

Read `../../templates/toolchain-lock.yaml` and `../../catalog/capabilities.yaml`. Run `../../scripts/check_toolchain.py` first and report the machine's actual state. The core workflow supports Windows and Linux; macOS is out of scope.

Keep editor automation disabled until its server-side security extension, checksum-locked artifact, configuration readback, and canary have passed. Do not treat Codex client `disabled_tools` as a security boundary. UE must fail closed when its capability token is missing, and Blender's generic gateway `call` must remain disabled until the server filters stable backend/skill/tool identities.

Only after the user approves the two-stage provision operation may a later provisioning implementation download artifacts or update project configuration. Record the installed versions, checksums, endpoint, canary result, and automation status in `.ue5-codex-studio/toolchain-lock.yaml`.
