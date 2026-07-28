#!/usr/bin/env python3
"""Validate normalized evidence records, including strict MCP mutation evidence."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml


LEVELS = {"ACK", "OBSERVED", "PERSISTED", "RUNTIME"}
RESULTS = {"PASS", "FAIL", "UNKNOWN", "PENDING_LOCAL_VALIDATION"}
SHA256 = re.compile(r"[0-9a-f]{64}$")
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
CLOUD_REQUIRED = {
    "provider",
    "model",
    "prediction_id",
    "capability_id",
    "contract_sha256",
    "redacted_request_hash",
    "output_artifacts",
    "started_at",
    "finished_at",
    "state",
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
    if record.get("kind") == "cloud_generation":
        missing = sorted(field for field in CLOUD_REQUIRED if not record.get(field))
        if missing:
            return fail(f"cloud generation evidence missing {', '.join(missing)}")
        if record.get("provider") != "atlascloud" or record.get("execution_profile") != "cloud":
            return fail("cloud generation evidence has an invalid provider or execution profile")
        if not SHA256.fullmatch(str(record.get("contract_sha256", ""))) or not SHA256.fullmatch(str(record.get("redacted_request_hash", ""))):
            return fail("cloud generation contract and request hashes must be SHA-256")
        if record.get("state") == "SUCCEEDED" and record.get("result") != "PENDING_LOCAL_VALIDATION":
            return fail("cloud output must remain PENDING_LOCAL_VALIDATION")
        artifacts = record.get("output_artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            return fail("cloud generation evidence needs output artifacts")
        for artifact in artifacts:
            if not isinstance(artifact, dict) or not artifact.get("path") or not SHA256.fullmatch(str(artifact.get("sha256", ""))):
                return fail("cloud generation output artifacts need path and SHA-256")
        print("PASS: cloud generation evidence is valid")
        return 0
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
