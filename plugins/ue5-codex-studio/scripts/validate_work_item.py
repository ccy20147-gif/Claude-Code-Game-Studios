#!/usr/bin/env python3
"""Validate a work item and its accepted-baseline references."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from schema_validation import load_yaml, sha256_file, validate_schema


REQUIRED_READY_FIELDS = ("requirements", "deliverables", "acceptance_evidence")


def fail(message: str, code: int = 1) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work_item", type=Path)
    parser.add_argument("--project-root", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--capabilities", type=Path)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    try:
        item = load_yaml(args.work_item)
    except (OSError, ValueError) as error:
        return fail(str(error))
    version = item.get("schema_version")
    if version not in {1, 2}:
        return fail("work item must declare schema version 1 or 2")
    if version == 1 and args.require_ready:
        return fail("LEGACY_SCHEMA_READ_ONLY: schema version 2 is required for a READY gate", 2)
    if version == 2:
        errors = validate_schema(item, "work-item.schema.json")
        if errors:
            return fail("; ".join(errors))
    if not isinstance(item.get("id"), str) or not item["id"].startswith("work_"):
        return fail("work item ID must start with work_")
    if item.get("status") == "READY":
        missing = [field for field in REQUIRED_READY_FIELDS if not item.get(field)]
        if missing:
            return fail(f"READY work item missing {', '.join(missing)}")
        if item["id"] in item.get("dependencies", []):
            return fail("work item cannot depend on itself")
    if args.require_ready and item.get("status") != "READY":
        return fail("work item must be READY")
    if not args.require_ready:
        print("PASS: work item is structurally valid")
        return 0
    baseline_path = args.baseline or (args.project_root / "design" / "baseline.yaml" if args.project_root else None)
    capabilities_path = args.capabilities or Path(__file__).resolve().parents[1] / "catalog" / "capabilities.yaml"
    if baseline_path is None or not baseline_path.is_file() or not capabilities_path.is_file():
        return fail("READY validation requires --project-root or an explicit baseline path")
    try:
        baseline = load_yaml(baseline_path)
        capabilities = load_yaml(capabilities_path)
    except (OSError, ValueError) as error:
        return fail(str(error))
    if baseline.get("schema_version") != 2 or baseline.get("status") != "ACCEPTED":
        return fail("READY work item requires an accepted schema version 2 baseline")
    reference = item.get("baseline")
    if not isinstance(reference, dict) or reference.get("id") != baseline.get("id") or reference.get("revision") != baseline.get("revision") or reference.get("sha256") != sha256_file(baseline_path):
        return fail("work item baseline reference does not match the current accepted baseline")
    requirements = set(baseline.get("requirements", []))
    if not set(item.get("requirements", [])).issubset(requirements):
        return fail("work item references requirements outside the accepted baseline")
    supported = {entry.get("id"): entry for entry in capabilities.get("capabilities", []) if isinstance(entry, dict)}
    for capability_id in item.get("capabilities", []):
        capability = supported.get(capability_id)
        if not capability or capability.get("status") == "UNSUPPORTED" or capability.get("availability") in {"BLOCKED", "UNSUPPORTED"}:
            return fail(f"work item capability is not ready: {capability_id}")
    print("PASS: READY work item traceability is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
