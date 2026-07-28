#!/usr/bin/env python3
"""Advance a schema version 2 project workflow after an explicit approval."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

import yaml

from schema_validation import load_yaml, validate_schema


ORDER = {"intake": 0, "concept": 1, "gdd": 2, "baseline": 3, "systems": 4, "production": 5, "release": 6}


def fail(message: str, code: int = 1) -> int:
    print(f"FAIL: {message}")
    return code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--phase", choices=ORDER)
    parser.add_argument("--status", choices=["READY", "IN_PROGRESS", "AWAITING_USER", "BLOCKED", "COMPLETE"], required=True)
    parser.add_argument("--active-skill")
    parser.add_argument("--reason", required=True)
    parser.add_argument("--approve", action="store_true")
    args = parser.parse_args()
    if not args.approve:
        return fail("workflow advancement requires --approve")
    try:
        project = load_yaml(args.project)
    except (OSError, ValueError) as error:
        return fail(str(error))
    if project.get("schema_version") != 2:
        return fail("LEGACY_SCHEMA_READ_ONLY: workflow advancement requires schema version 2", 2)
    workflow = project["workflow"]
    phase = args.phase or workflow["phase"]
    if ORDER[phase] < ORDER[workflow["phase"]] or ORDER[phase] > ORDER[workflow["phase"]] + 1:
        return fail("workflow phase transition must stay in order")
    previous = {"phase": workflow["phase"], "status": workflow["status"], "active_skill": workflow.get("active_skill")}
    workflow["phase"] = phase
    workflow["status"] = args.status
    workflow["active_skill"] = args.active_skill
    workflow["transitions"].append({
        "at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "from": previous,
        "to": {"phase": phase, "status": args.status, "active_skill": args.active_skill},
        "reason": args.reason,
    })
    errors = validate_schema(project, "project.schema.json")
    if errors:
        return fail("; ".join(errors))
    temporary = args.project.with_suffix(args.project.suffix + ".tmp")
    temporary.write_text(yaml.safe_dump(project, allow_unicode=True, sort_keys=False), encoding="utf-8")
    temporary.replace(args.project)
    print(f"PASS: advanced {project['id']} to {phase}/{args.status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
