#!/usr/bin/env python3
"""Validate a read-only UE5 Codex Studio intake bundle."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


ORIGINS = {"zero", "source_fiction", "design_pack", "implementation", "hybrid"}


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    try:
        bundle = yaml.safe_load(args.bundle.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        return fail(f"cannot read intake bundle: {error}")
    if not isinstance(bundle, dict):
        return fail("intake bundle must be a mapping")
    intake = bundle.get("intake")
    unreal = bundle.get("unreal")
    if not isinstance(intake, dict) or not isinstance(unreal, dict):
        return fail("intake bundle requires intake and unreal sections")
    if intake.get("origin") not in ORIGINS or intake.get("read_only") is not True:
        return fail("intake origin or read_only contract is invalid")
    files = intake.get("files")
    if not isinstance(files, list):
        return fail("intake files must be a list")
    paths = [entry.get("path") for entry in files if isinstance(entry, dict)]
    if len(paths) != len(files) or len(paths) != len(set(paths)):
        return fail("intake file paths must be present and unique")
    unknown = unreal.get("binary_assets_unknown")
    if not isinstance(unknown, list) or any(path not in paths for path in unknown):
        return fail("unknown UE binary assets must be listed in intake files")
    if unreal.get("detected") is True:
        directories = unreal.get("native_directories")
        projects = unreal.get("project_files")
        if not isinstance(directories, dict) or not isinstance(projects, list):
            return fail("detected UE project requires native directory and project-file records")
        if not projects and not any(directories.values()):
            return fail("detected UE project has no native UE structure")
    print("PASS: intake bundle is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
