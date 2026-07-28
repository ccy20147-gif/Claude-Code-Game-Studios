#!/usr/bin/env python3
"""Provision the controlled AtlasCloud asset MCP without storing its API key."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml

from atlascloud_core import AtlasError, Contract


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "integrations" / "atlascloud"
LOCK = INTEGRATION / "model-lock.yaml"
ADAPTER = INTEGRATION / "adapter.mjs"
MCP_NAME = "atlascloud-assets-controlled"
STATE_RELATIVE = Path(".ue5-codex-studio") / "atlascloud-session.json"
IGNORE_LINES = (
    ".ue5-codex-studio/atlascloud-session.json",
    ".ue5-codex-studio/atlascloud/jobs/",
)


class ProvisionError(RuntimeError):
    pass


def run(argv: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(argv, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ProvisionError(f"command failed: {' '.join(argv[:3])}")
    return result


def codex_config(codex: str) -> dict[str, Any] | None:
    result = subprocess.run([codex, "mcp", "get", MCP_NAME, "--json"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ProvisionError("Codex MCP readback was not JSON") from error
    if not isinstance(value, dict):
        raise ProvisionError("Codex MCP readback was not an object")
    return value


def state_path(project: Path, explicit: Path | None) -> Path:
    value = (explicit or project / STATE_RELATIVE).resolve()
    project = project.resolve()
    if value != project and project not in value.parents:
        raise ProvisionError("AtlasCloud session state must remain inside the project")
    return value


def session_health(state_file: Path, contract: Contract) -> dict[str, Any]:
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProvisionError("AtlasCloud session state is absent or invalid; start a runtime session first") from error
    endpoint = state.get("endpoint")
    token = state.get("token")
    if not isinstance(endpoint, str) or not endpoint.startswith("http://127.0.0.1:") or not isinstance(token, str):
        raise ProvisionError("AtlasCloud session state is not loopback-bound")
    if state.get("contract_sha256") != contract.sha256:
        raise ProvisionError("AtlasCloud session state has a different model contract")
    request = urllib.request.Request(endpoint + "/health", headers={"X-Atlas-Session-Token": token, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            health = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, json.JSONDecodeError) as error:
        raise ProvisionError("cannot authenticate the local AtlasCloud session") from error
    if not isinstance(health, dict) or health.get("contract_sha256") != contract.sha256:
        raise ProvisionError("AtlasCloud session health has contract drift")
    return health


def preflight(project: Path, codex: str, state_file: Path, contract: Contract) -> dict[str, Any]:
    node = shutil.which("node")
    codex_path = shutil.which(codex) if not Path(codex).is_file() else str(Path(codex).resolve())
    existing = codex_config(codex) if codex_path else None
    return {
        "schema_version": 1,
        "status": "READY" if project.is_dir() and node and codex_path and existing is None else "BLOCKED",
        "project": str(project),
        "state_file": str(state_file),
        "session_running": state_file.is_file(),
        "contract_sha256": contract.sha256,
        "models": sorted(contract.models),
        "node": node,
        "codex": codex_path,
        "configuration_conflict": existing is not None,
    }


def update_gitignore(project: Path) -> tuple[Path, str | None]:
    path = project / ".gitignore"
    previous = path.read_text(encoding="utf-8") if path.exists() else None
    content = previous or ""
    additions = [line for line in IGNORE_LINES if line not in {item.strip() for item in content.splitlines()}]
    if additions:
        separator = "" if not content or content.endswith("\n") else "\n"
        path.write_text(content + separator + "\n".join(additions) + "\n", encoding="utf-8")
    return path, previous


def restore_gitignore(path: Path, previous: str | None) -> None:
    if previous is None:
        path.unlink(missing_ok=True)
    else:
        path.write_text(previous, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("plan", "install", "doctor", "remove"))
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--state-file", type=Path)
    parser.add_argument("--lock", type=Path, default=LOCK)
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--approve", action="store_true")
    args = parser.parse_args()
    project = args.project.resolve()
    state_file = state_path(project, args.state_file)
    try:
        contract = Contract(args.lock)
        if args.command == "plan":
            print(yaml.safe_dump(preflight(project, args.codex, state_file, contract), sort_keys=False), end="")
            return 0
        if args.command == "doctor":
            health = session_health(state_file, contract)
            config = codex_config(args.codex)
            print(json.dumps({"status": "PASS", "session": health, "codex_registered": config is not None}, indent=2))
            return 0
        if not args.approve:
            raise ProvisionError(f"{args.command} requires --approve")
        if args.command == "remove":
            if codex_config(args.codex) is not None:
                run([args.codex, "mcp", "remove", MCP_NAME])
            print("PASS: removed controlled AtlasCloud MCP registration; the running credential session was not terminated")
            return 0
        report = preflight(project, args.codex, state_file, contract)
        if report["configuration_conflict"]:
            raise ProvisionError(f"Codex MCP configuration {MCP_NAME} already exists; refusing to overwrite")
        if not project.is_dir() or not report["node"] or not report["codex"]:
            raise ProvisionError("project, Node.js, and Codex CLI are required")
        session_health(state_file, contract)
        ignore_path, previous_ignore = update_gitignore(project)
        try:
            run([args.codex, "mcp", "add", MCP_NAME, "--", "node", str(ADAPTER), "--state-file", str(state_file)])
            if codex_config(args.codex) is None:
                raise ProvisionError("Codex MCP configuration readback failed")
        except ProvisionError:
            restore_gitignore(ignore_path, previous_ignore)
            if codex_config(args.codex) is not None:
                subprocess.run([args.codex, "mcp", "remove", MCP_NAME], capture_output=True, text=True, check=False)
            raise
        print("PASS: registered controlled AtlasCloud MCP. Start a new Codex thread while the runtime session remains active.")
        return 0
    except (AtlasError, OSError, ProvisionError, KeyError, TypeError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
