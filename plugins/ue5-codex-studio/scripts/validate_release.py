#!/usr/bin/env python3
"""Validate a game release record through READY_TO_RELEASE without deployment."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import sys
from pathlib import Path

from schema_validation import load_yaml, validate_schema


REQUIRED_GATES = {
    "fresh_install", "smoke_regression", "save_compatibility", "performance",
    "security", "accessibility", "localization", "content_rights", "legal",
}


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release", type=Path)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    try:
        release = load_yaml(args.release)
    except (OSError, ValueError) as error:
        return fail(str(error))
    errors = validate_schema(release, "release.schema.json")
    if errors:
        return fail("; ".join(errors))
    if args.require_ready and release["status"] != "READY_TO_RELEASE":
        return fail("release must be READY_TO_RELEASE")
    if release["status"] != "READY_TO_RELEASE":
        print("PASS: release record is structurally valid but not ready")
        return 0
    if not release.get("source_revision"):
        errors.append("ready release requires source_revision")
    baseline = release["baseline"]
    if not baseline.get("id") or not baseline.get("revision") or not baseline.get("sha256"):
        errors.append("ready release requires an immutable baseline reference")
    if not release.get("toolchain_sha256"):
        errors.append("ready release requires toolchain SHA-256")
    if not release["targets"] or any(not target.get("platform") or not target.get("package_sha256") for target in release["targets"]):
        errors.append("ready release requires a package hash for every target")
    statuses = {gate["id"]: gate for gate in release["gates"]}
    missing = REQUIRED_GATES - set(statuses)
    if missing:
        errors.append("ready release is missing gates: " + ", ".join(sorted(missing)))
    for gate_id, gate in statuses.items():
        if gate["status"] not in {"PASS", "WAIVED"}:
            errors.append(f"release gate {gate_id} is not PASS or WAIVED")
        if not gate["evidence"]:
            errors.append(f"release gate {gate_id} has no evidence")
    now = datetime.now(timezone.utc)
    waiver_ids = set()
    for waiver in release["waivers"]:
        required = ("id", "scope", "rationale", "expiry", "owner", "remediation")
        if any(not waiver.get(field) for field in required):
            errors.append("release waiver is incomplete")
            continue
        waiver_ids.add(waiver["id"])
        try:
            expiry = datetime.fromisoformat(str(waiver["expiry"]).replace("Z", "+00:00"))
            if expiry <= now:
                errors.append(f"release waiver {waiver['id']} is expired")
        except ValueError:
            errors.append(f"release waiver {waiver['id']} has invalid expiry")
    for gate in statuses.values():
        if gate["status"] == "WAIVED" and gate.get("waiver_id") not in waiver_ids:
            errors.append(f"waived gate {gate['id']} lacks a valid waiver")
    rollback = release["rollback"]
    if not rollback.get("artifact") or not rollback.get("sha256"):
        errors.append("ready release requires a rollback artifact and SHA-256")
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PASS: release is READY_TO_RELEASE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
