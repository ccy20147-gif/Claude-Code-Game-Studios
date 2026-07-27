#!/usr/bin/env python3
"""Normalize supported narrative files into source-span YAML without OCR."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import yaml


TEXT_EXTENSIONS = {".md", ".txt", ".fountain"}


def read_docx(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    parts = [node.text or "" for node in root.iter() if node.tag.endswith("}t")]
    return "".join(parts)


def read_fdx(path: Path) -> str:
    root = ElementTree.parse(path).getroot()
    return "\n".join((node.text or "") for node in root.iter() if node.tag.endswith("}Text"))


def read_pdf(path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", str(path), "-"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise ValueError("PDF text extraction failed; scanned PDFs are unsupported.")
    return result.stdout


def read_source(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in TEXT_EXTENSIONS:
        return path.read_text(encoding="utf-8")
    if suffix == ".docx":
        return read_docx(path)
    if suffix == ".fdx":
        return read_fdx(path)
    if suffix == ".pdf":
        return read_pdf(path)
    raise ValueError(f"Unsupported source format: {suffix or '(none)'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-id", default=None)
    args = parser.parse_args()

    source = args.source.resolve()
    if not source.is_file():
        parser.error(f"Source file not found: {source}")
    text = read_source(source).replace("\r\n", "\n").replace("\r", "\n")
    if not text.strip():
        raise ValueError("No extractable text found; do not use OCR fallback.")

    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    source_id = args.source_id or f"source_{digest[:12]}"
    spans = []
    offset = 0
    for number, block in enumerate((part for part in text.split("\n\n") if part.strip()), start=1):
        start = text.find(block, offset)
        end = start + len(block)
        spans.append({"id": f"source_span_{digest[:12]}_{number:04d}", "start": start, "end": end, "text": block})
        offset = end

    payload = {
        "schema_version": 1,
        "source": {"id": source_id, "path": str(source), "sha256": digest, "format": source.suffix.lower()},
        "normalized_text": text,
        "spans": spans,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"Wrote {len(spans)} source spans to {args.output}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, zipfile.BadZipFile, ElementTree.ParseError) as error:
        print(f"import_narrative: {error}", file=sys.stderr)
        raise SystemExit(2)
