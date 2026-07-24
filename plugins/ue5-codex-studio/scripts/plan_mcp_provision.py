#!/usr/bin/env python3
"""Generate a read-only, approval-gated MCP provisioning plan from a toolchain lock."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse

import yaml


ROOT = Path(__file__).resolve().parents[1]
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")


def issue_if_missing(issues: list[str], value: object, label: str, pattern: re.Pattern[str]) -> None:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        issues.append(f"{label} must be an immutable value matching {pattern.pattern}")


def check_endpoint(issues: list[str], endpoint: object, label: str) -> None:
    if not isinstance(endpoint, str):
        issues.append(f"{label} endpoint is missing")
        return
    parsed = urlparse(endpoint)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        issues.append(f"{label} endpoint must be an HTTP loopback endpoint")


def contains_secret(value: object, path: str = "") -> str | None:
    if isinstance(value, dict):
        for key, nested in value.items():
            found = contains_secret(nested, f"{path}.{key}" if path else str(key))
            if found:
                return found
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            found = contains_secret(nested, f"{path}[{index}]")
            if found:
                return found
    elif any(part in path.lower() for part in ("token", "secret", "password")) and value is not None and value not in ("", "required"):
        return path
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=ROOT / "templates/toolchain-lock.yaml")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    lock_path = args.lock.resolve()
    try:
        raw_lock = lock_path.read_bytes()
        lock = yaml.safe_load(raw_lock)
    except (OSError, yaml.YAMLError) as error:
        raise SystemExit(f"cannot read lock: {error}")
    if not isinstance(lock, dict):
        raise SystemExit("lock must be a YAML mapping")

    issues: list[str] = []
    secret_path = contains_secret(lock)
    if secret_path:
        issues.append(f"tracked lock must not contain a secret ({secret_path})")
    provisioning = lock.get("provisioning")
    if not isinstance(provisioning, dict) or provisioning.get("downloads_embedded") is not False:
        issues.append("lock must declare downloads_embedded: false")
    if not isinstance(provisioning, dict) or provisioning.get("require_security_canary") is not True:
        issues.append("lock must require a security canary")

    unreal = lock.get("unreal", {})
    ue_mcp = unreal.get("mcp", {}) if isinstance(unreal, dict) else {}
    blender = lock.get("blender", {})
    blender_mcp = blender.get("mcp", {}) if isinstance(blender, dict) else {}
    for label, mcp, hashes in (
        ("unreal.mcp", ue_mcp, ("tag", "commit", "artifact_sha256")),
        ("blender.mcp", blender_mcp, ("commit", "wheel_sha256", "core_wheel_sha256")),
    ):
        if not isinstance(mcp, dict):
            issues.append(f"{label} must be a mapping")
            continue
        if label == "unreal.mcp" and not isinstance(mcp.get("tag"), str) or (label == "unreal.mcp" and not mcp["tag"].startswith("v")):
            issues.append("unreal.mcp.tag must be a release tag")
        issue_if_missing(issues, mcp.get("commit"), f"{label}.commit", COMMIT)
        for field in hashes:
            if field not in {"commit", "tag"}:
                issue_if_missing(issues, mcp.get(field), f"{label}.{field}", SHA256)
        check_endpoint(issues, mcp.get("endpoint"), label)
        if mcp.get("server_policy") != "required":
            issues.append(f"{label}.server_policy must be required")

    lock_hash = hashlib.sha256(raw_lock).hexdigest()
    status = "READY_FOR_APPROVAL" if not issues else "BLOCKED"
    plan = {
        "schema_version": 1,
        "kind": "mcp_provision_plan",
        "lock": {"path": str(lock_path), "sha256": lock_hash},
        "status": status,
        "blocking_issues": issues,
        "automatic_actions": [],
        "approval_required_actions": [
            "download each checksum-locked artifact",
            "install or update the local MCP server",
            "write local-only MCP configuration without secrets in tracked files",
            "start loopback services and run authentication, denylist, schema-drift, and readback canaries",
        ],
        "required_runtime_evidence": [
            "Codex MCP configuration readback",
            "server-side action-policy canary",
            "independent post-mutation readback",
            "local-editor execution evidence distinct from cloud/offline work",
        ],
    }
    encoded = yaml.safe_dump(plan, sort_keys=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
        print(f"Wrote read-only provision plan to {args.output}")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
