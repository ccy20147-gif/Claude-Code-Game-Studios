#!/usr/bin/env python3
"""Validate required truths have explicit, existing clue support."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("graph", type=Path)
    args = parser.parse_args()
    data = yaml.safe_load(args.graph.read_text(encoding="utf-8")) or {}
    clues = {item.get("id") for item in data.get("clues", []) if item.get("id")}
    failures = []
    for truth in data.get("truths", []):
        if not truth.get("required", True):
            continue
        support = truth.get("clues", [])
        if not support:
            failures.append(f"{truth.get('id', '<unnamed>')}: no supporting clue")
        missing = set(support) - clues
        if missing:
            failures.append(f"{truth.get('id', '<unnamed>')}: unknown clues {sorted(missing)}")
    if failures:
        print("FAIL: " + "; ".join(failures), file=sys.stderr)
        return 1
    print("PASS: required truths have registered clue support")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
