#!/usr/bin/env python3
"""Copy stable cross-engine contracts into a plugin or verify drift."""
from __future__ import annotations

import argparse
import filecmp
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SHARED = ROOT / "shared" / "studio-contracts"
FILES = {
    "canonical-gdd.yaml": "templates/canonical-gdd.yaml",
    "narrative-registry.yaml": "templates/narrative-registry.yaml",
    "audio-bible.yaml": "templates/audio-bible.yaml",
    "work-item.yaml": "templates/work-item.yaml",
    "canonical-gdd.schema.json": "schemas/canonical-gdd.schema.json",
    "evidence.schema.json": "schemas/evidence.schema.json",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    plugin = args.plugin.resolve()
    drift = []
    for source_name, destination_name in FILES.items():
        source, destination = SHARED / source_name, plugin / destination_name
        if args.check:
            if not destination.is_file() or not filecmp.cmp(source, destination, shallow=False):
                drift.append(destination_name)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
    if drift:
        raise SystemExit("shared contract drift: " + ", ".join(drift))
    print("PASS" if args.check else "SYNCED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
