#!/usr/bin/env python3
"""Validate normalized evidence records, including strict MCP mutation evidence."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


LEVELS = {"ACK", "OBSERVED", "PERSISTED", "RUNTIME"}
RESULTS = {"PASS", "FAIL", "UNKNOWN", "PENDING_LOCAL_VALIDATION"}
MCP_STATES = {"SUCCEEDED", "FAILED", "UNKNOWN", "SKIPPED"}
MCP_REQUIRED = {
    "run_id",
    "capability_id",
    "backend_version",
    "resolved_tool",
    "instance_id",
    "catalog_generation",
    "schema_hash",
    "redacted_request_hash",
    "started_at",
    "finished_at",
    "state",
    "postcondition_probes",
    "execution_profile",
}


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    try:
        record = yaml.safe_load(args.evidence.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        return fail(f"cannot read evidence: {error}")
    if not isinstance(record, dict):
        return fail("evidence must be a mapping")
    if not isinstance(record.get("id"), str) or not record["id"].startswith("evidence_"):
        return fail("evidence ID must start with evidence_")
    if record.get("level") not in LEVELS or record.get("result") not in RESULTS:
        return fail("evidence has an invalid level or result")
    if record.get("kind") != "mcp_mutation":
        print("PASS: evidence is valid")
        return 0

    missing = sorted(field for field in MCP_REQUIRED if not record.get(field))
    if missing:
        return fail(f"MCP mutation evidence missing {', '.join(missing)}")
    if record["state"] not in MCP_STATES:
        return fail("MCP mutation has an invalid state")
    if record["execution_profile"] not in {"local-editor", "cloud", "offline"}:
        return fail("MCP mutation has an invalid execution profile")
    if not isinstance(record["postcondition_probes"], list):
        return fail("MCP mutation postcondition_probes must be a list")
    if record["state"] == "UNKNOWN" and record.get("automatic_retry"):
        return fail("UNKNOWN MCP mutation must not be retried automatically")
    if record["state"] == "SUCCEEDED" and not record["postcondition_probes"]:
        return fail("SUCCEEDED MCP mutation requires independent postcondition probes")
    if record["execution_profile"] != "local-editor" and record["state"] == "SUCCEEDED":
        return fail("cloud/offline MCP mutation cannot be reported as SUCCEEDED")
    print("PASS: MCP mutation evidence is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
