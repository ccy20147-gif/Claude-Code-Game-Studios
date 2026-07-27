#!/usr/bin/env python3
"""Validate released persistence contracts have N-1 and N-2 migration paths."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    args = parser.parse_args()
    data = yaml.safe_load(args.contract.read_text(encoding="utf-8")) or {}
    if not data.get("released", False):
        print("PASS: pre-release contract does not require release migration coverage")
        return 0
    current = data.get("current_schema")
    paths = {(item.get("from"), item.get("to")) for item in data.get("migration_paths", [])}
    expected = {(current - 1, current), (current - 2, current)}
    missing = expected - paths
    if missing:
        print(f"FAIL: missing migration paths {sorted(missing)}", file=sys.stderr)
        return 1
    print("PASS: released contract has N-1 and N-2 migration paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
