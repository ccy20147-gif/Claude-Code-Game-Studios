# Codex UE Game Studios

Structured UE5 game-development workflows for Codex.

Codex UE Game Studios is a local Codex plugin for taking a game from an empty
brief, a novel or screenplay, an existing design pack, or an existing Unreal
Engine project through traceable design, production, QA, release, and
operations work.

The repository retains `.claude/` as source and historical reference material.
It is not required by, and is not installed as, the Codex runtime.

## What It Provides

- 38 Codex skills covering intake, narrative adaptation, systems, levels, art,
  audio, UX, architecture, implementation, QA, release, and live operations.
- Fiction-to-game planning with stable source spans, adaptation decisions,
  characters, beats, game requirements, and a playable core-loop contract.
- Existing-project intake that recognizes standard UE directories without
  pretending that binary assets have been semantically inspected.
- Conditional delivery gates for narrative adventures, detective mysteries,
  systemic sandboxes, and 2D, 2.5D, or 3D projects.
- Controlled text-revision propagation across strings, translations, subtitles,
  voice takes, cinematics, clues, level triggers, tests, and evidence.
- Provider-neutral music, SFX, and voice production contracts.

## Install

Requirements:

- Codex CLI `>=0.145.0,<0.146.0`
- Python 3 with PyYAML
- Git

```bash
git clone https://github.com/ccy20147-gif/codex-ue-game-studios.git
cd codex-ue-game-studios
codex plugin marketplace add . --json
codex plugin add ue5-codex-studio@donchitos-game-studios --json
codex plugin list --json
```

The final command must report the plugin as both `installed` and `enabled`.
Start a new Codex thread after installation.

## Start A Project

Use the relevant skill directly in Codex:

```text
$ue5-start-project
$ue5-adapt-story
$ue5-ingest-project
```

`$ue5-start-project` routes the project according to its creative origin and
implementation state. `$ue5-adapt-story` supports TXT, Markdown, Fountain,
DOCX, FDX, and text PDFs. `$ue5-ingest-project` is for existing design assets
or UE projects.

## Editor Automation

Unreal and Blender MCP automation is optional and disabled by default. The
core design and production workflow does not depend on it.

Before enabling a write route, use the default-deny policy template and pass
the server-policy, token, schema-drift, multi-instance, independent-readback,
save/reload, and runtime canaries. Do not rely on Codex `disabled_tools` as a
security boundary, and never commit credentials to UE config or this repository.

The plugin includes a policy guard, approved hash-verified artifact
provisioning, and immutable marketplace install/rollback tooling. Full
instructions and the remaining real-editor gates are in
[plugins/ue5-codex-studio/HANDOFF.md](plugins/ue5-codex-studio/HANDOFF.md).

## Verify A Checkout

```bash
python3 -m unittest discover -s plugins/ue5-codex-studio/tests -v
python3 plugins/ue5-codex-studio/scripts/validate_studio.py
python3 plugins/ue5-codex-studio/scripts/validate_mcp_security_policy.py \
  plugins/ue5-codex-studio/templates/mcp-security-policy.yaml
python3 /root/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py \
  plugins/ue5-codex-studio
```

## Repository Layout

```text
.agents/plugins/marketplace.json    Repository-local Codex marketplace
plugins/ue5-codex-studio/           Plugin, skills, contracts, scripts, tests
.claude/                            Original Claude Code source/reference material
```

## License

[MIT](LICENSE)
