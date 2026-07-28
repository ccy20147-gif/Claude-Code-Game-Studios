#!/usr/bin/env python3
"""Derive the next UE5 Codex Studio action from project workflow state."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from validate_project import main as validate_project_main


NEXT_BY_PHASE = {
    "intake": "ue5-start-project",
    "concept": "ue5-conceive-game",
    "gdd": "ue5-reconcile-gdd",
    "baseline": "ue5-accept-baseline",
    "systems": "ue5-map-systems",
    "production": "ue5-plan-work",
    "release": "ue5-release-game",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    args = parser.parse_args()
    saved = sys.argv[:]
    sys.argv = [saved[0], str(args.project), "--require-current"]
    try:
        if validate_project_main() != 0:
            return 2
    finally:
        sys.argv = saved
    project = yaml.safe_load(args.project.read_text(encoding="utf-8"))
    workflow = project["workflow"]
    result = {
        "project_id": project["id"],
        "status": workflow["status"],
        "blockers": workflow["blockers"],
        "pending_decisions": workflow["pending_decisions"],
        "required_next": None,
        "optional_next": [],
    }
    if workflow["status"] == "BLOCKED":
        result["required_next"] = "resolve_blockers"
    elif workflow["status"] == "AWAITING_USER":
        result["required_next"] = "resolve_pending_decisions"
    elif workflow["status"] != "COMPLETE":
        result["required_next"] = workflow.get("active_skill") or NEXT_BY_PHASE[workflow["phase"]]
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
