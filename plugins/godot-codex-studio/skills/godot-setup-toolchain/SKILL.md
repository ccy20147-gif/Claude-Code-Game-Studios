---
name: godot-setup-toolchain
description: Install, update, remove, or diagnose the approval-gated Godot Codex Studio MCP bridge for a native Windows or Linux Godot 4 project. Use when configuring Godot MCP, checking Godot/Node/.NET readiness, or running the editor canary.
---

# Set Up The Godot Toolchain

Read `../../templates/toolchain-lock.yaml` and `../../catalog/capabilities.yaml`. First run `../../scripts/check_toolchain.py`, then run `node ../../scripts/godot-mcp-cli.mjs plan --project <project> --godot <godot> --codex <codex>`. Report the plan without changing state.

Explain the single approval boundary before any mutation. On one explicit approval, run `install --approve` with independent argv values for the project, Godot executable, and Codex executable. It checksum-verifies `@satelliteoflove/godot-mcp@4.1.0`, runs `npm ci --omit=dev --ignore-scripts` in versioned staging, backs up the addon and `project.godot`, adds the managed Codex stdio entry, reads that entry back, and rolls all of it back on failure.

Accept only native Windows or Linux, Godot `>=4.5,<4.8`, and Node 20+. Treat versions other than Godot 4.7.1 as `UNVERIFIED_VERSION`; require a project canary before status is `READY`. For C# projects, require the Godot .NET editor and .NET SDK 8+; use `dotnet build` plus Godot headless validation. GDScript is validated by the Godot editor. `godot_exec` executes GDScript only and must never be presented as a C# executor.

The installed bridge permits automatic reads only. Scene/resource edits, runtime execution, input injection, and `godot_exec` require tool approval. The Godot addon must bind only `127.0.0.1:6550`; reject custom non-loopback endpoints and keep upstream usage logs disabled. Record versions, hashes, project identity, config readback, and canary outcome in the ignored `.godot-codex-studio/toolchain-lock.yaml` without tokens or secrets.
