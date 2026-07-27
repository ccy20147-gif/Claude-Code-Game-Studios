#!/usr/bin/env python3
"""Validate voice lines link to approved takes and cues when VO is required."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    data = yaml.safe_load(args.manifest.read_text(encoding="utf-8")) or {}
    cue_ids = {cue.get("id") for cue in data.get("cues", []) if cue.get("id")}
    failures = []
    for line in data.get("lines", []):
        if not line.get("requires_vo", False):
            continue
        take = line.get("approved_take")
        cue = line.get("cue_id")
        if not take:
            failures.append(f"{line.get('id', '<unnamed>')}: missing approved take")
        if cue not in cue_ids:
            failures.append(f"{line.get('id', '<unnamed>')}: missing registered cue")
    if failures:
        print("FAIL: " + "; ".join(failures), file=sys.stderr)
        return 1
    print("PASS: required VO lines have takes and cues")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
