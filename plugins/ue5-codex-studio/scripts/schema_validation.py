#!/usr/bin/env python3
"""Shared YAML and JSON Schema helpers for UE5 Codex Studio contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import json

import jsonschema
import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a mapping")
    return data


def validate_schema(document: dict[str, Any], schema_name: str) -> list[str]:
    schema_path = ROOT / "schemas" / schema_name
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [error.message for error in sorted(validator.iter_errors(document), key=lambda item: list(item.path))]


def sha256_file(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
