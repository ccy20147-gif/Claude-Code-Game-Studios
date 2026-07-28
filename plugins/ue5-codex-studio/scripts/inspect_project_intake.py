#!/usr/bin/env python3
"""Read-only inventory and intake classification for design packs and UE5 projects."""

from __future__ import annotations

import argparse
import hashlib
from collections import Counter
from pathlib import Path

import yaml


UE_DIRECTORIES = ("Source", "Content", "Config", "Plugins")
UE_BINARY_SUFFIXES = {".uasset", ".umap", ".ubulk", ".uexp"}
FICTION_SUFFIXES = {".txt", ".fountain", ".fdx"}
DESIGN_SUFFIXES = {".yaml", ".yml", ".json"}
FICTION_HINTS = {"story", "novel", "script", "screenplay", "narrative", "fiction"}
DESIGN_HINTS = {"gdd", "design", "game-design", "game_design"}
NON_DESIGN_NAMES = {"readme", "license", "copying", "changelog", "contributing"}
IGNORED_DIRECTORIES = {".git", ".ue5-codex-studio", "Binaries", "DerivedDataCache", "Intermediate", "Saved"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _path_words(path: str) -> set[str]:
    normalized = path.lower().replace("_", "-").replace(".", "-").replace("/", "-")
    return {word for word in normalized.split("-") if word}


def classify(files: list[dict[str, object]], has_ue: bool) -> str:
    has_fiction = False
    has_design = False
    for item in files:
        suffix = str(item["suffix"])
        path = str(item["path"])
        words = _path_words(path)
        stem = Path(path).stem.lower()
        if suffix in FICTION_SUFFIXES or (suffix in {".md", ".docx", ".pdf"} and words & FICTION_HINTS):
            has_fiction = True
        if suffix in DESIGN_SUFFIXES or (suffix in {".md", ".docx", ".pdf"} and words & DESIGN_HINTS):
            if stem not in NON_DESIGN_NAMES:
                has_design = True
    categories = sum((has_ue, has_fiction, has_design))
    if categories == 0:
        return "zero"
    if categories > 1:
        return "hybrid"
    if has_ue:
        return "implementation"
    return "source_fiction" if has_fiction else "design_pack"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, help="Write an intake bundle only to this explicit output path.")
    parser.add_argument("--origin", choices=["zero", "source_fiction", "design_pack", "implementation", "hybrid"], help="Record a user-confirmed classification override.")
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        parser.error(f"Directory not found: {root}")

    files: list[dict[str, object]] = []
    skipped: list[str] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in IGNORED_DIRECTORIES for part in relative.parts):
            if path.is_dir():
                skipped.append(relative.as_posix())
            continue
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        kind = "binary_unknown" if suffix in UE_BINARY_SUFFIXES else "file"
        files.append({"path": relative.as_posix(), "suffix": suffix, "bytes": path.stat().st_size, "sha256": sha256(path), "kind": kind})

    paths = {item["path"] for item in files}
    project_files = sorted(path for path in paths if path.lower().endswith(".uproject"))
    ue_directories = {name: (root / name).is_dir() for name in UE_DIRECTORIES}
    has_ue = bool(project_files) or any(ue_directories.values())
    binary_unknown = [item["path"] for item in files if item["kind"] == "binary_unknown"]
    suffix_counts = dict(sorted(Counter(str(item["suffix"]) for item in files).items()))
    detected_origin = classify(files, has_ue)
    origin = args.origin or detected_origin
    bundle = {
        "schema_version": 1,
        "intake": {
            "root": str(root),
            "origin": origin,
            "detected_origin": detected_origin,
            "origin_source": "user_override" if args.origin else "classifier",
            "read_only": True,
            "file_count": len(files),
            "files": files,
            "ignored_directories": sorted(set(skipped)),
        },
        "unreal": {
            "detected": has_ue,
            "project_files": project_files,
            "native_directories": ue_directories,
            "binary_assets_unknown": binary_unknown,
        },
        "source_manifest": {
            "suffix_counts": suffix_counts,
            "facts": ["UE binary assets require Asset Registry or approved MCP readback before semantic claims." ] if binary_unknown else [],
            "open_questions": ["Choose an authority map for conflicts between prose and implementation."] if origin == "hybrid" else [],
        },
    }
    encoded = yaml.safe_dump(bundle, allow_unicode=True, sort_keys=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
        print(f"Wrote read-only intake bundle to {args.output}")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
