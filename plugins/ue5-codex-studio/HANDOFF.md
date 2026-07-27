# UE5 Codex Studio Handoff

## Current State

The plugin is installed locally as `ue5-codex-studio@donchitos-game-studios`, version `0.1.0+codex.20260724101749`. Codex CLI `0.145.0` was used for installation and upgrade readback. The repository-local marketplace is `.agents/plugins/marketplace.json`; use the repository root as the local marketplace source.

All 39 public skills are active. The core path is independent of MCP: zero-idea, fiction, design-pack, and brownfield UE intake; external-GDD reconciliation; narrative adaptation; design; work planning; QA; release; and operations. Structured YAML is authoritative. Start with `skills/ue5-start-project`, `ue5-adapt-story`, or `ue5-ingest-project`. A design-pack intake must pass `ue5-reconcile-gdd`; imported approval language is never a baseline acceptance.

## Local Verification

Run from the repository root:

```bash
python3 -m unittest discover -s plugins/ue5-codex-studio/tests -v
python3 plugins/ue5-codex-studio/scripts/validate_studio.py
python3 plugins/ue5-codex-studio/scripts/validate_mcp_security_policy.py plugins/ue5-codex-studio/templates/mcp-security-policy.yaml
python3 /root/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/ue5-codex-studio
git diff --check
```

The suite currently contains 21 behavior tests. It covers plugin/catalog integrity; external-GDD reconciliation and non-inheritance of approval claims; fiction-to-game traceability; text-revision stale propagation; UE brownfield intake; profile delivery; policy, token, drift, and bypass denial; approved artifact provisioning; and immutable marketplace install/rollback command flows. It does not replace a real editor canary. Regenerate the Markdown catalog after changing `catalog/skills.yaml`:

```bash
python3 plugins/ue5-codex-studio/scripts/render_catalog.py
```

For a plugin update, use the cachebuster helper then reinstall from the configured local marketplace. Confirm only with the CLI readback:

```bash
python3 /root/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py plugins/ue5-codex-studio
codex plugin add ue5-codex-studio@donchitos-game-studios --json
codex plugin list --json
```

Use a new Codex thread after reinstalling.

## Intake And Evidence

`scripts/inspect_project_intake.py <root>` inventories arbitrary paths read-only, hashes files, recognizes `.uproject`, `Source`, `Content`, `Config`, and `Plugins`, and marks `.uasset`, `.umap`, `.ubulk`, and `.uexp` as `binary_unknown`. It never infers their semantics from a filename. Validate generated output with `scripts/validate_intake_bundle.py`.

The narrative importer supports TXT, Markdown, Fountain, DOCX, FDX, and text PDFs without OCR fallback. It emits stable `source_span_` IDs. State and evidence rules are in `references/state-contract.md`.

MCP evidence is validated by `scripts/validate_evidence.py`. Every MCP mutation needs backend version, resolved tool, instance ID, catalog generation, schema hash, redacted request hash, timing, execution profile, state, and independent postcondition probes. `UNKNOWN` must not auto-retry; cloud/offline may not report an editor mutation as `SUCCEEDED`.

## MCP Security Boundary

MCP is optional acceleration, never the only workflow path. Editor write automation remains disabled. Do not enable it by merely adding `disabled_tools` in Codex; that is not a server security boundary.

`templates/toolchain-lock.yaml` targets:

- Codex `>=0.145.0,<0.146.0`
- Unreal `5.7.4`, controlled `NodeNestor/UE5UltimateMCP` source commit `40d9c23d4125fc805f0cb669429a652318adaf37`
- Blender `4.5`, `dcc-mcp-blender 0.1.40`, commit `e68a90993e9794d56bb7a9e3bd3c43e2dc7f9dc5`, `dcc-mcp-core 0.19.63`

The UE source archive, Node lockfile, and MIT license are checksum-locked. The generic artifact plan remains blocked for the separate Blender core artifact. Use the dedicated Windows-only UE provisioner for this integration:

```bash
python3 plugins/ue5-codex-studio/scripts/plan_mcp_provision.py
python3 plugins/ue5-codex-studio/scripts/provision_ue5ultimatemcp.py plan --project C:\\Game --ue-root C:\\Program\ Files\\Epic\ Games\\UE_5.7
```

Never place a capability token in tracked UE config. Use an environment variable or an ignored local secret file. MCP endpoints must be loopback.

`provision_ue5ultimatemcp.py install --approve` deploys only to `Plugins/UE5UltimateMCP` after source-hash verification, patching, actual `RunUAT BuildPlugin`, and a project backup. Set `UE5ULTIMATEMCP_TOKEN` from the protected local state before opening the editor. `doctor --accept-catalog --approve` performs token and loopback checks, binds the runtime schema hash, and then registers only the repository-owned stdio adapter. It refuses an existing same-name Codex MCP configuration. `remove --approve` removes that registration and restores the backup.

The adapter exposes health, discovery, level/Actor reads, viewport capture, and canary-map-only Actor creation/deletion. It never registers the upstream dynamic Node bridge or its high-risk tools. A self-hosted Windows UE 5.7 runner must run `scripts/run_ue5ultimatemcp_canary.py` with a dedicated `/Game/__CodexCanary_*` map and save/reload evidence before enabling write automation beyond this canary.

`templates/dcc-modeling-policy.yaml` is the Blender/DCC activation contract. It allows only creating new meshes, sculpts, and new imports by default. Any existing-asset edit or deletion requires a Codex writes approval record. This policy remains inactive until the Blender gateway is checksum-locked, filters stable `(skill_name, backend_tool)` identities, and passes a DCC canary; it does not authorize raw scripts, addon installation, or exports outside the project workspace.

`scripts/provision_mcp.py` is the approved second stage. It requires all three reviewed artifact paths (`unreal`, `blender-adapter`, and `blender-core`), matching immutable hashes, `--approve`, an explicit install root, and an explicit local state file. HTTPS download additionally needs `--allow-download`. It never writes credentials. `--start-services` is refused unless the local lock adds reviewed loopback service argv/health records. Copy `templates/local-toolchain.gitignore` into the target project before choosing a local state path.

## Required Upstream Extensions

`templates/mcp-security-policy.yaml`, `scripts/mcp_security.py`, and `scripts/run_mcp_guard.py` implement the default-deny enforcement contract: a capability token, explicit route, instance ID, catalog generation, schema hash, and mutation approval are mandatory. The template permits no routes. A deployed local policy may add a route only after a server-policy canary; it must never wildcard dynamic tool slugs.

The guard is an HTTP boundary, not permission to leave an upstream listener exposed. Create local forks or maintained local branches before enabling writes; bind the upstream listener privately and enforce its own token there as well.

For UE MCP, enforce token absence as fail-closed and apply a server-side action allowlist. Keep `execute_python`, console command paths, `run_ubt`, `manage_tools` enable/reset paths, `inspect.set_property`, and `add_mass_spawner` denied until explicitly repaired and canaried. Record ACK, independent readback, saved state, and runtime evidence as appropriate.

For Blender MCP, enforce a gateway policy before generic `call` dispatch using stable `(backend, skill_name, backend_tool)` identities. Default deny all writes; discovery may remain available. Bind each mutation to the current instance ID, capability catalog generation, and schema hash. Fail closed on schema drift, instance change, timeout, or disconnect.

## Complete In The Full Environment

1. Build the secure UE and Blender forks, lock all artifacts and transitive wheel hashes, and update the lock file. Wire the upstream dispatch to the same policy contract before it accepts traffic.
2. Run missing-token, wrong-token, correct-token, dangerous-action, gateway-bypass, schema-drift, multi-instance, and timeout-to-UNKNOWN canaries.
3. Add Windows and Linux UE 5.7.4 fixtures. Test asset read, safe mutation, independent readback, save/reload, packaged runtime, and rollback.
4. Add Blender 4.5 fixture tests for discovery, approved write, readback, and denylisted gateway calls.
5. Enable only proven capability IDs in `catalog/capabilities.yaml`; retain fallbacks for every unavailable backend action.
6. Run the real immutable Git marketplace installation and rollback canary. `scripts/manage_marketplace_release.py` implements the approved flow and validates CLI readback; do not treat cache files as installation truth. A rollback requires the previous lock and the exact previous manifest.

`templates/marketplace-lock.yaml` and `scripts/validate_marketplace_lock.py` are the static release-lock contract. Fill the lock only from a committed manifest and validate it before immutable Git marketplace installation; the development-local marketplace is intentionally not release evidence. Then use `scripts/manage_marketplace_release.py install --approve ...` and validate its CLI readback. Use `rollback --approve --previous-lock ... --previous-manifest ...` only after reviewing the target state.

## Important Constraints

- Preserve `.claude` as source/reference; do not migrate its runtime.
- Do not make baseline, scope, or creative acceptance decisions without user approval.
- Cloud-generated results are `PENDING_LOCAL_VALIDATION` until local evidence exists.
- A `FAIL` gate needs an explicit scoped, expiring waiver. A solo review does not waive objective evidence.
- `$ue5-adapt-story` writes a validated narrative registry with source-span coverage, adaptation decisions, character/beat IDs, game requirements, and a playable core loop. `$ue5-change-design` writes a validated ledger that marks affected text, localization, VO, cinematics, clues, level triggers, tests, and evidence stale.
