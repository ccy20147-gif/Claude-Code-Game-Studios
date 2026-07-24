#!/usr/bin/env python3
"""Validate a default-deny MCP policy without contacting an editor."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from mcp_security import PolicyError, load_policy


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("policy", type=Path)
    args = parser.parse_args()
    try:
        policy = load_policy(str(args.policy))
    except PolicyError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"PASS: default-deny policy validates for {len(policy['backends'])} backends")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
