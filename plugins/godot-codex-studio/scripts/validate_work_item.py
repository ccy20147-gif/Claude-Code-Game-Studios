#!/usr/bin/env python3
"""Validate that a work item can enter READY without missing traceability."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


REQUIRED_READY_FIELDS = ("requirements", "deliverables", "acceptance_evidence")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work_item", type=Path)
    args = parser.parse_args()
    item = yaml.safe_load(args.work_item.read_text(encoding="utf-8")) or {}
    missing = [field for field in REQUIRED_READY_FIELDS if not item.get(field)]
    if item.get("status") == "READY" and missing:
        print(f"FAIL: READY work item missing {', '.join(missing)}", file=sys.stderr)
        return 1
    if not item.get("id", "").startswith("work_"):
        print("FAIL: work item ID must start with work_", file=sys.stderr)
        return 1
    if not isinstance(item.get("baseline_revision"), int) or item["baseline_revision"] < 1:
        print("FAIL: baseline_revision must be a positive integer", file=sys.stderr)
        return 1
    print("PASS: work item traceability is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
