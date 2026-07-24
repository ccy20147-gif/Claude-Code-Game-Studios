#!/usr/bin/env python3
"""Read-only preflight for the UE5 Codex Studio toolchain."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def run_version(command: list[str]) -> dict[str, str | bool]:
    executable = shutil.which(command[0])
    if executable is None:
        return {"available": False, "detail": f"{command[0]} not found"}
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    detail = (result.stdout or result.stderr).strip().splitlines()
    return {"available": result.returncode == 0, "detail": detail[0] if detail else f"exit {result.returncode}"}


def ue_version(root: Path | None) -> dict[str, str | bool]:
    if root is None:
        return {"available": False, "detail": "UE root not supplied"}
    version_file = root / "Engine/Build/Build.version"
    if not version_file.is_file():
        return {"available": False, "detail": f"Build.version missing under {root}"}
    try:
        version = json.loads(version_file.read_text(encoding="utf-8"))
        return {"available": True, "detail": f"{version.get('MajorVersion')}.{version.get('MinorVersion')}.{version.get('PatchVersion')}"}
    except (OSError, json.JSONDecodeError) as error:
        return {"available": False, "detail": str(error)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ue-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    lock = yaml.safe_load((ROOT / "templates/toolchain-lock.yaml").read_text(encoding="utf-8"))
    report = {
        "schema_version": 1,
        "expected": lock,
        "observed": {
            "codex": run_version(["codex", "--version"]),
            "blender": run_version(["blender", "--version"]),
            "unreal": ue_version(args.ue_root),
        },
        "provisioning": "not_attempted",
    }
    encoded = yaml.safe_dump(report, sort_keys=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
        print(f"Wrote toolchain report to {args.output}")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
