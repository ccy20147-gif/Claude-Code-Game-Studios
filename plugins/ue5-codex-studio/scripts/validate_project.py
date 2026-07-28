#!/usr/bin/env python3
"""Validate the resumable UE5 Codex Studio project state."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from schema_validation import load_yaml, validate_schema


def fail(message: str, code: int = 1) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--require-current", action="store_true")
    args = parser.parse_args()
    try:
        project = load_yaml(args.project)
    except (OSError, ValueError) as error:
        return fail(str(error))
    if project.get("schema_version") != 2:
        return fail("LEGACY_SCHEMA_READ_ONLY: project schema version 2 is required", 2)
    errors = validate_schema(project, "project.schema.json")
    if errors:
        return fail("; ".join(errors))
    workflow = project["workflow"]
    if args.require_current and workflow["status"] in {"READY", "IN_PROGRESS"} and not workflow.get("active_skill"):
        return fail("active workflow requires active_skill")
    print("PASS: project workflow state is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
