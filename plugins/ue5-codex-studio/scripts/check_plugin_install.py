#!/usr/bin/env python3
"""Read plugin installation state without changing Codex configuration."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / ".codex-plugin" / "plugin.json")
    parser.add_argument("--codex-bin", default="codex")
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        result = subprocess.run([args.codex_bin, "plugin", "list", "--json"], capture_output=True, text=True, check=False, timeout=15)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or f"codex exited {result.returncode}")
        installed = json.loads(result.stdout).get("installed", [])
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"status": "UNKNOWN", "reason": str(error)}, indent=2))
        return 0
    expected_name = manifest.get("name")
    expected_version = manifest.get("version")
    match = next((item for item in installed if item.get("name") == expected_name), None)
    if not match:
        status = "NOT_INSTALLED"
    elif not match.get("enabled") or not match.get("installed"):
        status = "DISABLED"
    elif match.get("version") != expected_version:
        status = "STALE"
    else:
        status = "CURRENT"
    print(json.dumps({"status": status, "expected": {"name": expected_name, "version": expected_version}, "installed": match}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
