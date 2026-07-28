#!/usr/bin/env python3
"""Validate a fixed-scope Win64 Shipping package manifest and its hashes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from schema_validation import load_yaml, sha256_file, validate_schema


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--staging-dir", type=Path)
    args = parser.parse_args()
    try:
        manifest = load_yaml(args.manifest)
    except (OSError, ValueError) as error:
        return fail(str(error))
    errors = validate_schema(manifest, "package-manifest.schema.json")
    if errors:
        return fail("; ".join(errors))
    seen = set()
    root = args.staging_dir.resolve() if args.staging_dir else None
    for entry in manifest["files"]:
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts or entry["path"] in seen:
            return fail("package manifest has an unsafe or duplicate file path")
        seen.add(entry["path"])
        if root:
            artifact = (root / relative).resolve()
            if root not in artifact.parents or not artifact.is_file() or sha256_file(artifact) != entry["sha256"]:
                return fail(f"package artifact hash does not match: {entry['path']}")
    print(f"PASS: {args.manifest.name}; {len(manifest['files'])} Win64 Shipping files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
