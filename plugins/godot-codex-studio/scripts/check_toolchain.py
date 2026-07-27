#!/usr/bin/env python3
"""Read-only Godot Codex Studio environment preflight."""
from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys

import yaml


def version(command: str) -> str | None:
    path = shutil.which(command)
    if not path:
        return None
    try:
        result = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=5, check=False)
    except OSError:
        return None
    return (result.stdout or result.stderr).strip().splitlines()[0] if result.returncode == 0 else None


def main() -> int:
    host = platform.system().lower()
    report = {
        "schema_version": 1,
        "provisioning": "not_attempted",
        "accepted_host": host in {"windows", "linux"} and not bool(os.environ.get("WSL_DISTRO_NAME")),
        "observed": {
            "platform": platform.platform(),
            "node": version("node"),
            "godot": version("godot") or version("godot4"),
            "dotnet": version("dotnet"),
            "codex": version("codex"),
        },
        "requirements": {
            "godot_verified": "4.7.1",
            "godot_accepted_range": ">=4.5,<4.8",
            "node": ">=20",
            "dotnet_csharp": ">=8",
            "hosts": ["windows", "linux"],
        },
    }
    print(yaml.safe_dump(report, sort_keys=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
