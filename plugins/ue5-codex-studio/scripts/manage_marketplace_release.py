#!/usr/bin/env python3
"""Install or roll back a plugin from an immutable Git marketplace lock.

All mutations require ``--approve``.  This script treats the Codex CLI
readback as installation truth; cache directories are never used as evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def load_lock(lock_path: Path, manifest_path: Path) -> dict[str, Any]:
    try:
        lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, yaml.YAMLError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot read marketplace lock or manifest: {error}") from error
    if not isinstance(lock, dict) or not isinstance(lock.get("marketplace"), dict) or not isinstance(lock.get("plugin"), dict):
        raise ValueError("marketplace lock requires marketplace and plugin mappings")
    repository = lock["marketplace"].get("repository")
    commit = lock["marketplace"].get("commit")
    if not isinstance(repository, str) or not repository.startswith("https://"):
        raise ValueError("marketplace repository must use HTTPS")
    if not isinstance(commit, str) or len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
        raise ValueError("marketplace commit must be a 40-character lowercase SHA")
    if lock["plugin"].get("name") != manifest.get("name") or lock["plugin"].get("version") != manifest.get("version"):
        raise ValueError("marketplace lock plugin identity does not match manifest")
    if lock["plugin"].get("manifest_sha256") != hashlib.sha256(manifest_bytes).hexdigest():
        raise ValueError("marketplace lock manifest hash does not match manifest")
    return lock


def command_text(command: list[str]) -> str:
    return " ".join(json.dumps(part) for part in command)


def invoke(command: list[str], dry_run: bool) -> Any:
    print(command_text(command))
    if dry_run:
        return None
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ValueError(f"command failed ({result.returncode}): {result.stderr.strip() or result.stdout.strip()}")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ValueError(f"command did not return JSON: {command_text(command)}") from error


def marketplace_present(payload: object, name: str) -> bool:
    candidates: object = payload.get("marketplaces", []) if isinstance(payload, dict) else payload
    if not isinstance(candidates, list):
        return False
    return any(isinstance(item, dict) and item.get("name") == name for item in candidates)


def plugin_installed(payload: object, lock: dict[str, Any], marketplace_name: str) -> bool:
    candidates: object = payload.get("installed", []) if isinstance(payload, dict) else []
    if not isinstance(candidates, list):
        return False
    plugin = lock["plugin"]
    return any(
        isinstance(item, dict)
        and item.get("name") == plugin["name"]
        and item.get("marketplaceName") == marketplace_name
        and item.get("version") == plugin["version"]
        and item.get("installed") is True
        and item.get("enabled") is True
        for item in candidates
    )


def replace_source(codex: str, marketplace_name: str, current: dict[str, Any], target: dict[str, Any], dry_run: bool) -> None:
    current_plugin = current["plugin"]["name"]
    invoke([codex, "plugin", "remove", f"{current_plugin}@{marketplace_name}", "--json"], dry_run)
    invoke([codex, "plugin", "marketplace", "remove", marketplace_name, "--json"], dry_run)
    invoke([codex, "plugin", "marketplace", "add", target["marketplace"]["repository"], "--ref", target["marketplace"]["commit"], "--json"], dry_run)


def install(codex: str, marketplace_name: str, lock: dict[str, Any], replace: bool, dry_run: bool) -> None:
    current = invoke([codex, "plugin", "marketplace", "list", "--json"], dry_run)
    if marketplace_present(current, marketplace_name):
        if not replace:
            raise ValueError("configured marketplace exists; pass --replace-marketplace after reviewing the target lock")
        invoke([codex, "plugin", "remove", f"{lock['plugin']['name']}@{marketplace_name}", "--json"], dry_run)
        invoke([codex, "plugin", "marketplace", "remove", marketplace_name, "--json"], dry_run)
    invoke([codex, "plugin", "marketplace", "add", lock["marketplace"]["repository"], "--ref", lock["marketplace"]["commit"], "--json"], dry_run)
    invoke([codex, "plugin", "add", f"{lock['plugin']['name']}@{marketplace_name}", "--json"], dry_run)
    readback = invoke([codex, "plugin", "list", "--json"], dry_run)
    if not dry_run and not plugin_installed(readback, lock, marketplace_name):
        raise ValueError("Codex CLI readback did not confirm the locked plugin is installed and enabled")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "rollback"))
    parser.add_argument("--lock", type=Path, required=True, help="target immutable marketplace lock")
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--marketplace-name", required=True)
    parser.add_argument("--previous-lock", type=Path, help="required for rollback")
    parser.add_argument("--previous-manifest", type=Path, help="manifest belonging to --previous-lock")
    parser.add_argument("--approve", action="store_true")
    parser.add_argument("--replace-marketplace", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--codex-bin", default="codex")
    args = parser.parse_args()
    if not args.approve:
        return fail("marketplace mutation requires explicit --approve")
    try:
        target = load_lock(args.lock, args.manifest)
        if args.action == "install":
            install(args.codex_bin, args.marketplace_name, target, args.replace_marketplace, args.dry_run)
        else:
            if args.previous_lock is None or args.previous_manifest is None:
                raise ValueError("rollback requires --previous-lock and --previous-manifest")
            previous = load_lock(args.previous_lock, args.previous_manifest)
            replace_source(args.codex_bin, args.marketplace_name, target, previous, args.dry_run)
            invoke([args.codex_bin, "plugin", "add", f"{previous['plugin']['name']}@{args.marketplace_name}", "--json"], args.dry_run)
            readback = invoke([args.codex_bin, "plugin", "list", "--json"], args.dry_run)
            if not args.dry_run and not plugin_installed(readback, previous, args.marketplace_name):
                raise ValueError("Codex CLI readback did not confirm rollback target")
    except ValueError as error:
        return fail(str(error))
    print(f"PASS: {args.action} flow completed against immutable marketplace lock")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
