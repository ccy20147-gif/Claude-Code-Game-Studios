#!/usr/bin/env python3
"""Validate plugin metadata, active skills, schemas, and parity coverage."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
LEGACY_COUNT = 73
SKILL_FRONTMATTER = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL)


def fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def load_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        fail(f"cannot read {path}: {error}")
    if not isinstance(data, dict):
        fail(f"{path} must contain a mapping")
    return data


def main() -> int:
    manifest = json.loads((ROOT / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    if manifest.get("name") != ROOT.name:
        fail("plugin manifest name must match plugin directory")
    if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?", manifest.get("version", "")):
        fail("plugin version must be strict semver")
    if "mcpServers" in manifest or "hooks" in manifest:
        fail("MCP and hooks must be provisioned explicitly, not bundled in v1")

    required_files = (
        "templates/mcp-security-policy.yaml",
        "templates/narrative-registry.yaml",
        "templates/change-ledger.yaml",
        "scripts/mcp_security.py",
        "scripts/run_mcp_guard.py",
        "scripts/validate_mcp_security_policy.py",
        "scripts/validate_asset_registry.py",
        "scripts/validate_blender_gateway_manifest.py",
        "scripts/validate_gltf_asset.py",
        "scripts/validate_generated_mesh.py",
        "scripts/validate_atlascloud_lock.py",
        "scripts/atlascloud_core.py",
        "scripts/atlascloud_session.py",
        "scripts/provision_atlascloud.py",
        "scripts/run_atlascloud_canary.py",
        "scripts/provision_mcp.py",
        "scripts/provision_ue5ultimatemcp.py",
        "scripts/run_ue5ultimatemcp_canary.py",
        "integrations/ue5ultimatemcp/adapter.mjs",
        "integrations/ue5ultimatemcp/policy.json",
        "integrations/ue5ultimatemcp/patches/0001-loopback-token-port.patch",
        "scripts/manage_marketplace_release.py",
        "scripts/validate_narrative_registry.py",
        "scripts/validate_change_ledger.py",
        "scripts/validate_canonical_gdd.py",
        "scripts/validate_baseline.py",
        "templates/canonical-gdd.yaml",
        "templates/asset-registry.yaml",
        "templates/profile-delivery.yaml",
        "templates/release.yaml",
        "templates/dcc-modeling-policy.yaml",
        "templates/blueprint-operation.yaml",
        "templates/dcc-operation.yaml",
        "schemas/profile-delivery.schema.json",
        "schemas/release.schema.json",
        "schemas/blueprint-operation.schema.json",
        "schemas/dcc-operation.schema.json",
        "schemas/package-manifest.schema.json",
        "scripts/schema_validation.py",
        "scripts/validate_project.py",
        "scripts/validate_release.py",
        "scripts/run_ue_automation.py",
        "scripts/build_ue_package.py",
        "scripts/validate_blueprint_operation.py",
        "scripts/validate_dcc_operation.py",
        "scripts/validate_package_manifest.py",
        "scripts/inspect_workflow_state.py",
        "scripts/advance_workflow.py",
        "scripts/check_plugin_install.py",
        "scripts/validate_current_docs.py",
        "integrations/blender-mcp/gateway-manifest.yaml",
        "integrations/atlascloud/model-lock.yaml",
        "integrations/atlascloud/policy.json",
        "integrations/atlascloud/adapter.mjs",
    )
    for relative in required_files:
        if not (ROOT / relative).is_file():
            fail(f"required workflow implementation missing: {relative}")
    security_policy = load_yaml(ROOT / "templates/mcp-security-policy.yaml")
    if security_policy.get("token", {}).get("required") is not True:
        fail("MCP policy must require a capability token")
    if any(backend.get("routes") for backend in security_policy.get("backends", {}).values() if isinstance(backend, dict)):
        fail("template MCP policy must remain default-deny until a canary-approved local policy exists")

    catalog = load_yaml(ROOT / "catalog/skills.yaml")
    skills = catalog.get("skills")
    if not isinstance(skills, list) or len(skills) != 39:
        fail("skills catalog must contain exactly 39 public skills")
    names = [entry.get("name") for entry in skills]
    if len(names) != len(set(names)) or any(not re.fullmatch(r"ue5-[a-z0-9-]+", name or "") for name in names):
        fail("skill names must be unique ue5-prefixed kebab case")
    if any(entry.get("status") != "active" for entry in skills):
        fail("foundation release requires all public skills to be active")

    for entry in skills:
        skill_path = ROOT / "skills" / entry["name"] / "SKILL.md"
        if not skill_path.is_file():
            fail(f"active skill missing: {entry['name']}")
        content = skill_path.read_text(encoding="utf-8")
        match = SKILL_FRONTMATTER.match(content)
        if not match or "TODO" in content:
            fail(f"active skill is incomplete: {entry['name']}")
        frontmatter = yaml.safe_load(match.group("body"))
        if set(frontmatter) != {"name", "description"} or frontmatter["name"] != entry["name"]:
            fail(f"invalid frontmatter: {entry['name']}")
        if not (ROOT / "skills" / entry["name"] / "agents/openai.yaml").is_file():
            fail(f"active skill UI metadata missing: {entry['name']}")

    ledger = load_yaml(ROOT / "catalog/parity-ledger.yaml")
    entries = ledger.get("entries")
    legacy_names = [entry.get("legacy") for entry in entries] if isinstance(entries, list) else []
    if ledger.get("legacy_skill_count") != LEGACY_COUNT or len(legacy_names) != LEGACY_COUNT or len(set(legacy_names)) != LEGACY_COUNT:
        fail("parity ledger must map each of the 73 legacy skills exactly once")
    known_targets = set(names) | {"plugin-ci"}
    if any(entry.get("target") not in known_targets for entry in entries):
        fail("parity ledger references an unknown target")

    for schema in (ROOT / "schemas").glob("*.json"):
        try:
            json.loads(schema.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            fail(f"invalid JSON schema {schema.name}: {error}")
    capabilities = load_yaml(ROOT / "catalog/capabilities.yaml")
    allowed_statuses = set(capabilities.get("statuses", []))
    allowed_availability = set(capabilities.get("availability", []))
    capability_entries = capabilities.get("capabilities", [])
    capability_ids = [entry.get("id") for entry in capability_entries]
    if len(capability_ids) != len(set(capability_ids)):
        fail("capability IDs must be unique")
    if any(entry.get("status") not in allowed_statuses for entry in capability_entries):
        fail("capability has an invalid support status")
    if any(entry.get("availability") not in allowed_availability for entry in capability_entries):
        fail("capability has an invalid runtime availability")
    if any(not entry.get("scope") or "executor" not in entry or not entry.get("fallback") for entry in capability_entries):
        fail("capability must declare scope, executor, and fallback")
    if any(entry.get("status") == "SCRIPT_FALLBACK" and not entry.get("executor") for entry in capability_entries):
        fail("script fallback capability must declare an executor")
    print(f"PASS: {ROOT.name}; {len(names)} catalog skills; {len(legacy_names)} legacy mappings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
