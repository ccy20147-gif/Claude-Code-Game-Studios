#!/usr/bin/env python3
"""Validate the Godot plugin's public contract and self-contained assets."""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SKILL_FRONTMATTER = re.compile(r"\A---\n(?P<body>.*?)\n---\n", re.DOTALL)
REQUIRED_CAPABILITIES = {
    "godot.project.inspect", "godot.scene.read", "godot.scene.edit", "godot.resource.read",
    "godot.resource.edit", "godot.script.validate", "godot.runtime.observe", "godot.runtime.input",
    "godot.runtime.exec", "godot.test.run", "godot.package.export",
}
EXPECTED_TOOLS = 21


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def yaml_file(path: Path) -> dict:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        fail(f"cannot read {path}: {error}")
    if not isinstance(value, dict):
        fail(f"{path} must contain a mapping")
    return value


def main() -> int:
    manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    if manifest.get("name") != ROOT.name or "mcpServers" in manifest or "hooks" in manifest:
        fail("manifest must be a self-contained explicit-provisioning plugin")
    catalog = yaml_file(ROOT / "catalog" / "skills.yaml").get("skills")
    if not isinstance(catalog, list) or len(catalog) != 39:
        fail("catalog must contain exactly 39 skills")
    names = [entry.get("name") for entry in catalog]
    if len(names) != len(set(names)) or any(not re.fullmatch(r"godot-[a-z0-9-]+", name or "") for name in names):
        fail("skills must have unique godot-prefixed names")
    for name in names:
        skill = ROOT / "skills" / name / "SKILL.md"
        ui = ROOT / "skills" / name / "agents" / "openai.yaml"
        content = skill.read_text(encoding="utf-8") if skill.is_file() else ""
        frontmatter = SKILL_FRONTMATTER.match(content)
        if not frontmatter or "TODO" in content or not ui.is_file():
            fail(f"incomplete skill: {name}")
        metadata = yaml.safe_load(frontmatter.group("body"))
        if set(metadata) != {"name", "description"} or metadata["name"] != name:
            fail(f"invalid skill metadata: {name}")
    lock = yaml_file(ROOT / "templates" / "toolchain-lock.yaml")
    if lock.get("godot", {}).get("verified_version") != "4.7.1" or lock.get("mcp", {}).get("version") != "4.1.0":
        fail("Godot and MCP versions are not locked")
    if lock["mcp"].get("tarball_sha256") != "3f6df8842219ba6ca763cb310019147dbb16cd695a48d7316a727de2d38705a9":
        fail("MCP SHA-256 is not locked")
    package_lock = json.loads((ROOT / "mcp" / "package-lock.json").read_text(encoding="utf-8"))
    package = package_lock["packages"].get("node_modules/@satelliteoflove/godot-mcp", {})
    if package.get("version") != "4.1.0" or not package.get("integrity"):
        fail("npm lock does not pin Godot MCP integrity")
    tools = json.loads((ROOT / "mcp-tools.json").read_text(encoding="utf-8")).get("tools", [])
    if len(tools) != EXPECTED_TOOLS or len(set(tools)) != EXPECTED_TOOLS or "godot_exec" not in tools:
        fail("upstream MCP tool catalog must expose all 21 tools including godot_exec")
    capabilities = yaml_file(ROOT / "catalog" / "capabilities.yaml").get("capabilities", [])
    if not REQUIRED_CAPABILITIES.issubset({entry.get("id") for entry in capabilities}):
        fail("Godot capability catalog is incomplete")
    print(f"PASS: {ROOT.name}; 39 skills; {EXPECTED_TOOLS} MCP tools")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
