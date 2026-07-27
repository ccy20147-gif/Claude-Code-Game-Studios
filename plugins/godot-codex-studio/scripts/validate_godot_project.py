#!/usr/bin/env python3
"""Validate a Godot project through the editor's headless parser."""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--godot", default="godot")
    parser.add_argument("--csharp", action="store_true")
    args = parser.parse_args()
    root = args.project.resolve()
    if not (root / "project.godot").is_file():
        raise SystemExit("project.godot not found")
    if args.csharp:
        projects = list(root.glob("*.csproj"))
        if not projects:
            raise SystemExit("--csharp requires a .csproj")
        result = subprocess.run(["dotnet", "build", str(projects[0]), "--nologo"], check=False)
        if result.returncode:
            return result.returncode
    return subprocess.run([args.godot, "--headless", "--path", str(root), "--editor", "--quit"], check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
