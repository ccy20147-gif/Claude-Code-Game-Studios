#!/usr/bin/env python3
"""Validate that a baseline acceptance is backed by a reconciled canonical GDD."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from validate_canonical_gdd import validate as validate_gdd


STATUSES = {"DRAFT", "CANDIDATE", "ACCEPTED", "SUPERSEDED"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("--gdd", type=Path, required=True)
    args = parser.parse_args()
    try:
        baseline = yaml.safe_load(args.baseline.read_text(encoding="utf-8"))
        gdd = yaml.safe_load(args.gdd.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        print(f"FAIL: cannot read baseline or GDD: {error}", file=sys.stderr)
        return 1
    if not isinstance(baseline, dict) or baseline.get("schema_version") != 1 or baseline.get("status") not in STATUSES:
        print("FAIL: baseline must be a schema version 1 document with a valid status", file=sys.stderr)
        return 1
    if baseline.get("status") != "ACCEPTED":
        print("PASS: baseline is not accepted")
        return 0
    errors = validate_gdd(gdd, require_ready=True)
    gdd_ref = baseline.get("gdd")
    acceptance = baseline.get("acceptance")
    if not isinstance(gdd_ref, dict) or gdd_ref.get("revision") != gdd.get("revision"):
        errors.append("accepted baseline must reference the reconciled GDD revision")
    if not isinstance(acceptance, dict) or acceptance.get("status") != "APPROVED" or acceptance.get("approver") != "user" or not acceptance.get("record"):
        errors.append("accepted baseline requires a direct user approval record")
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PASS: accepted baseline is backed by a reconciled GDD and user approval")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
