#!/usr/bin/env python3
"""Inspect a Godot project without attributing meaning to binary resources."""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.project.resolve()
    project_file = root / "project.godot"
    if not project_file.is_file():
        raise SystemExit("project.godot not found")
    scripts = sorted(str(item.relative_to(root)) for item in root.rglob("*.gd"))
    csharp = sorted(str(item.relative_to(root)) for item in list(root.rglob("*.cs")) + list(root.rglob("*.csproj")) + list(root.rglob("*.sln")))
    resources = sorted(str(item.relative_to(root)) for suffix in ("*.res", "*.tres", "*.scn", "*.tscn") for item in root.rglob(suffix))
    payload = {
        "schema_version": 1,
        "intake": {"origin": "implementation", "project_root": str(root)},
        "godot": {
            "detected": True,
            "project_file": "project.godot",
            "gdscript": scripts,
            "csharp": csharp,
            "resources_requiring_editor_validation": resources,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
