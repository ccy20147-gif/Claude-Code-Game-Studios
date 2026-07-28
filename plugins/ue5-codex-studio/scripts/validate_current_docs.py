#!/usr/bin/env python3
"""Keep the current UE5 Codex guide free of archived slash-command guidance."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
GUIDE = ROOT / "docs" / "UE5-CODEX-WORKFLOW.md"


def main() -> int:
    content = GUIDE.read_text(encoding="utf-8")
    banned = ("`/start`", "`/help`", "production/stage.txt", ".claude/docs/workflow-catalog.yaml")
    found = [token for token in banned if token in content]
    if found:
        print("FAIL: current guide contains archived workflow tokens: " + ", ".join(found), file=sys.stderr)
        return 1
    print("PASS: current UE5 Codex workflow guide is clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
