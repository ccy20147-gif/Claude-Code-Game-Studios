#!/usr/bin/env python3
"""Render the authoritative skill catalog as a compact Markdown view."""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "CATALOG.md")
    args = parser.parse_args()
    catalog = yaml.safe_load((ROOT / "catalog/skills.yaml").read_text(encoding="utf-8"))
    lines = ["# UE5 Codex Studio Catalog", "", "Generated from `catalog/skills.yaml`; do not edit this view manually.", "", "| Skill | Status | Artifact owner |", "|---|---|---|"]
    for skill in catalog["skills"]:
        lines.append(f"| `${skill['name']}` | `{skill['status']}` | `{skill['owner']}` |")
    args.output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Rendered {len(catalog['skills'])} skills to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
