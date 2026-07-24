#!/usr/bin/env python3
"""Perform approved, hash-verified local MCP artifact provisioning.

This script deliberately does not know vendor download URLs.  The operator
supplies reviewed artifact paths (or explicitly enables HTTPS download) that
match the immutable toolchain lock.  It never stores secrets and defaults to
not starting any service.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_FIELDS = {
    "unreal": ("unreal", "mcp", "artifact_sha256"),
    "blender-adapter": ("blender", "mcp", "wheel_sha256"),
    "blender-core": ("blender", "mcp", "core_wheel_sha256"),
}
SECRET_MARKERS = ("token", "secret", "password", "authorization", "api_key")


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1_048_576), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_lock(lock: dict[str, Any], name: str) -> str:
    keys = ARTIFACT_FIELDS[name]
    value: object = lock
    for key in keys:
        if not isinstance(value, dict):
            raise ValueError(f"toolchain lock missing {'/'.join(keys)}")
        value = value.get(key)
    if not isinstance(value, str) or len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError(f"toolchain lock needs immutable SHA-256 for {name}")
    return value


def parse_artifacts(values: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for value in values:
        name, separator, source = value.partition("=")
        if separator != "=" or name not in ARTIFACT_FIELDS or not source:
            raise ValueError(f"artifact must be one of {', '.join(ARTIFACT_FIELDS)}=PATH_OR_HTTPS_URL")
        if name in parsed:
            raise ValueError(f"artifact {name} was supplied more than once")
        parsed[name] = source
    missing = set(ARTIFACT_FIELDS) - set(parsed)
    if missing:
        raise ValueError("missing artifacts: " + ", ".join(sorted(missing)))
    return parsed


def materialize(source: str, destination_dir: Path, allow_download: bool) -> Path:
    parsed = urllib.parse.urlparse(source)
    if parsed.scheme:
        if parsed.scheme != "https" or not allow_download:
            raise ValueError("remote artifacts require --allow-download and an HTTPS URL")
        destination_dir.mkdir(parents=True, exist_ok=True)
        name = Path(parsed.path).name or "artifact.bin"
        target = destination_dir / name
        with urllib.request.urlopen(source, timeout=120) as response, target.open("wb") as stream:
            shutil.copyfileobj(response, stream)
        return target
    source_path = Path(source).expanduser().resolve()
    if not source_path.is_file():
        raise ValueError(f"artifact source is not a file: {source_path}")
    return source_path


def assert_no_secrets(value: object, path: str = "") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if any(marker in str(key).lower() for marker in SECRET_MARKERS):
                raise ValueError(f"secret-like key is not allowed in generated state: {path}{key}")
            assert_no_secrets(child, f"{path}{key}.")
    elif isinstance(value, list):
        for child in value:
            assert_no_secrets(child, path)


def loopback_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}


def run_services(lock: dict[str, Any]) -> list[dict[str, Any]]:
    provisioning = lock.get("provisioning")
    services = provisioning.get("services") if isinstance(provisioning, dict) else None
    if not isinstance(services, list) or not services:
        raise ValueError("toolchain lock needs provisioning.services before --start-services")
    records = []
    for service in services:
        if not isinstance(service, dict):
            raise ValueError("service entries must be mappings")
        identifier, command, health_url = service.get("id"), service.get("command"), service.get("health_url")
        if not isinstance(identifier, str) or not identifier or not isinstance(command, list) or not all(isinstance(item, str) and item for item in command):
            raise ValueError("service needs id and a non-empty argv command")
        if not loopback_url(health_url):
            raise ValueError(f"service {identifier} needs a loopback health_url")
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            with urllib.request.urlopen(health_url, timeout=10) as response:
                if not 200 <= response.status < 300:
                    raise ValueError(f"service {identifier} health returned {response.status}")
        except Exception:
            process.terminate()
            raise
        records.append({"id": identifier, "pid": process.pid, "health_url": health_url, "status": "HEALTHY"})
    return records


def atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    assert_no_secrets(value)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        yaml.safe_dump(value, stream, sort_keys=False)
        temporary = Path(stream.name)
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=ROOT / "templates/toolchain-lock.yaml")
    parser.add_argument("--install-root", type=Path, required=True)
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--artifact", action="append", default=[], metavar="NAME=PATH_OR_HTTPS_URL")
    parser.add_argument("--approve", action="store_true", help="allow artifact copy/download and state write")
    parser.add_argument("--allow-download", action="store_true", help="allow explicitly supplied HTTPS artifact sources")
    parser.add_argument("--start-services", action="store_true", help="start only lock-declared services and check loopback health")
    args = parser.parse_args()
    if not args.approve:
        return fail("provisioning requires explicit --approve")
    try:
        lock = yaml.safe_load(args.lock.read_text(encoding="utf-8"))
        if not isinstance(lock, dict):
            raise ValueError("toolchain lock must be a mapping")
        if lock.get("provisioning", {}).get("require_sha256") is not True:
            raise ValueError("toolchain lock must require SHA-256")
        sources = parse_artifacts(args.artifact)
        expected_hashes = {name: artifact_lock(lock, name) for name in ARTIFACT_FIELDS}
        install_root = args.install_root.resolve()
        records = []
        for name, source in sorted(sources.items()):
            materialized = materialize(source, install_root / ".downloads", args.allow_download)
            actual_hash = sha256(materialized)
            if actual_hash != expected_hashes[name]:
                raise ValueError(f"checksum mismatch for {name}")
            destination = install_root / "artifacts" / name / materialized.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists() and sha256(destination) != actual_hash:
                raise ValueError(f"refusing to overwrite a different artifact: {destination}")
            if not destination.exists():
                shutil.copy2(materialized, destination)
            records.append({"id": name, "path": str(destination), "sha256": actual_hash, "status": "VERIFIED"})
        services = run_services(lock) if args.start_services else []
        state = {
            "schema_version": 1,
            "automation_status": "CANARIED" if services else "ARTIFACTS_VERIFIED",
            "artifacts": records,
            "services": services,
            "credential_handling": "environment_only",
        }
        atomic_write(args.state_file.resolve(), state)
    except (OSError, ValueError, yaml.YAMLError, urllib.error.URLError) as error:
        return fail(str(error))
    print(f"PASS: provisioned {len(records)} verified artifacts; state written to {args.state_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
