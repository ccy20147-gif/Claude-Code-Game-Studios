#!/usr/bin/env python3
"""Validate a stable capability operation before an editor-backed action is queued."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
EXECUTION_PROFILES = {"local-editor", "cloud", "offline"}
STATUSES = {"PLANNED", "BLOCKED", "READY"}


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", type=Path)
    parser.add_argument("--capabilities", type=Path, default=ROOT / "catalog/capabilities.yaml")
    args = parser.parse_args()
    try:
        operation = yaml.safe_load(args.operation.read_text(encoding="utf-8"))
        catalog = yaml.safe_load(args.capabilities.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        return fail(f"cannot read input: {error}")
    if not isinstance(operation, dict) or not isinstance(catalog, dict):
        return fail("operation and capability catalog must be mappings")
    if not isinstance(operation.get("id"), str) or not operation["id"].startswith("operation_"):
        return fail("operation ID must start with operation_")
    if not isinstance(operation.get("intent"), str) or not operation["intent"].strip():
        return fail("operation must declare a stable intent")
    if operation.get("execution_profile") not in EXECUTION_PROFILES:
        return fail("operation has an invalid execution profile")
    if operation.get("status") not in STATUSES:
        return fail("operation has an invalid status")
    capabilities = {entry.get("id"): entry for entry in catalog.get("capabilities", []) if isinstance(entry, dict)}
    capability = capabilities.get(operation.get("capability_id"))
    if capability is None:
        return fail("operation references an unknown capability")
    support = capability.get("status")
    if support == "UNSUPPORTED" and operation["status"] != "BLOCKED":
        return fail("unsupported capability must remain BLOCKED")
    if support == "THIN_MCP_EXTENSION" and operation["status"] == "READY":
        requirements = (
            ("approval_record", None),
            ("server_policy_canary", "PASS"),
            ("schema_drift_policy", "fail_closed"),
            ("readback_required", True),
        )
        missing = []
        for field, expected in requirements:
            valid = bool(operation.get(field)) if expected is None else operation.get(field) == expected
            if not valid:
                missing.append(field)
        if missing:
            return fail(f"READY MCP operation missing safe activation conditions: {', '.join(missing)}")
        if operation["execution_profile"] != "local-editor":
            return fail("READY MCP operation requires local-editor execution")
    if operation["status"] == "READY" and not operation.get("required_evidence"):
        return fail("READY operation must declare required evidence")
    print(f"PASS: {operation['id']} may remain {operation['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
