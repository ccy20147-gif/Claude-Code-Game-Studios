#!/usr/bin/env python3
"""Validate immutable marketplace release-lock metadata."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml


COMMIT = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lock", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    try:
        lock = yaml.safe_load(args.lock.read_text(encoding="utf-8"))
        manifest_bytes = args.manifest.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, yaml.YAMLError, json.JSONDecodeError) as error:
        return fail(f"cannot read lock or manifest: {error}")
    if not isinstance(lock, dict) or not isinstance(lock.get("marketplace"), dict) or not isinstance(lock.get("plugin"), dict):
        return fail("lock requires marketplace and plugin mappings")
    marketplace, plugin = lock["marketplace"], lock["plugin"]
    if not isinstance(marketplace.get("repository"), str) or not marketplace["repository"].startswith("https://"):
        return fail("marketplace repository must be HTTPS")
    if not isinstance(marketplace.get("commit"), str) or not COMMIT.fullmatch(marketplace["commit"]):
        return fail("marketplace commit must be a 40-character immutable SHA")
    if plugin.get("name") != manifest.get("name") or plugin.get("version") != manifest.get("version"):
        return fail("lock plugin identity must match manifest")
    actual_hash = hashlib.sha256(manifest_bytes).hexdigest()
    if not isinstance(plugin.get("manifest_sha256"), str) or not SHA256.fullmatch(plugin["manifest_sha256"]):
        return fail("lock manifest_sha256 must be SHA-256")
    if plugin["manifest_sha256"] != actual_hash:
        return fail("lock manifest_sha256 does not match manifest")
    print("PASS: marketplace lock is immutable and matches manifest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
