#!/usr/bin/env python3
"""Validate a traceable asset registry without requiring a DCC or engine."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml


ASSET_ID = re.compile(r"asset_[a-z0-9_]+$")
SHA256 = re.compile(r"[0-9a-f]{64}$")
KINDS = {"mesh", "texture", "material", "rig", "animation", "vfx", "audio", "ui", "level", "gameplay_data", "collision", "nav_data"}
STATUSES = {"CANDIDATE", "PENDING_LOCAL_VALIDATION", "VALIDATED", "REJECTED"}
ROOT = Path(__file__).resolve().parents[1]


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", type=Path)
    parser.add_argument("--model-lock", type=Path, default=ROOT / "integrations" / "atlascloud" / "model-lock.yaml")
    args = parser.parse_args()
    try:
        registry = yaml.safe_load(args.registry.read_text(encoding="utf-8"))
        registry = mapping(registry, "registry")
        model_lock = mapping(yaml.safe_load(args.model_lock.read_text(encoding="utf-8")), "model lock")
        atlas_models = {item.get("id") for item in model_lock.get("models", []) if isinstance(item, dict)}
        if registry.get("schema_version") != 1 or not isinstance(registry.get("assets"), list):
            raise ValueError("registry needs schema_version: 1 and assets")
        ids: set[str] = set()
        for index, raw in enumerate(registry["assets"]):
            asset = mapping(raw, f"assets[{index}]")
            identifier = asset.get("id")
            if not isinstance(identifier, str) or not ASSET_ID.fullmatch(identifier) or identifier in ids:
                raise ValueError(f"assets[{index}] needs a unique asset_ ID")
            ids.add(identifier)
            if asset.get("kind") not in KINDS or asset.get("status") not in STATUSES:
                raise ValueError(f"{identifier} has invalid kind or status")
            source = mapping(asset.get("source"), f"{identifier}.source")
            origin = source.get("origin")
            if origin not in {"AI_GENERATED", "HUMAN_AUTHORED", "LICENSED", "DERIVED"}:
                raise ValueError(f"{identifier}.source.origin is invalid")
            for field in ("artifact_sha256", "rights_record"):
                if not isinstance(source.get(field), str) or not source[field]:
                    raise ValueError(f"{identifier}.source.{field} is required")
            if not SHA256.fullmatch(source["artifact_sha256"]):
                raise ValueError(f"{identifier}.source.artifact_sha256 must be SHA-256")
            if origin == "AI_GENERATED":
                for field in ("provider", "model", "prompt_sha256"):
                    if not isinstance(source.get(field), str) or not source[field]:
                        raise ValueError(f"AI-generated {identifier} needs source.{field}")
                if not SHA256.fullmatch(source["prompt_sha256"]):
                    raise ValueError(f"{identifier}.source.prompt_sha256 must be SHA-256")
                if source.get("provider") == "atlascloud":
                    if source.get("model") not in atlas_models:
                        raise ValueError(f"{identifier}.source.model is not in the AtlasCloud model lock")
                    if not isinstance(source.get("prediction_id"), str) or not source["prediction_id"]:
                        raise ValueError(f"{identifier}.source.prediction_id is required")
                    if not isinstance(source.get("request_sha256"), str) or not SHA256.fullmatch(source["request_sha256"]):
                        raise ValueError(f"{identifier}.source.request_sha256 must be SHA-256")
                    inputs = source.get("input_asset_ids", [])
                    if not isinstance(inputs, list) or not all(isinstance(item, str) and ASSET_ID.fullmatch(item) for item in inputs):
                        raise ValueError(f"{identifier}.source.input_asset_ids are invalid")
                    evidence = source.get("generation_evidence")
                    if not isinstance(evidence, str) or not evidence or Path(evidence).is_absolute() or ".." in Path(evidence).parts:
                        raise ValueError(f"{identifier}.source.generation_evidence must be a safe relative path")
            files = asset.get("files")
            if not isinstance(files, list) or not files or not all(isinstance(item, str) and item and not Path(item).is_absolute() and ".." not in Path(item).parts for item in files):
                raise ValueError(f"{identifier}.files must be safe relative paths")
            target = mapping(asset.get("target"), f"{identifier}.target")
            if target.get("engine") != "UE5" or not isinstance(target.get("destination"), str) or not target["destination"]:
                raise ValueError(f"{identifier}.target needs engine and destination")
            for field, prefix in (("requirement_ids", "req_"), ("ability_ids", "ability_")):
                values = asset.get(field, [])
                if not isinstance(values, list) or not all(isinstance(item, str) and item.startswith(prefix) for item in values):
                    raise ValueError(f"{identifier}.{field} must contain {prefix} IDs")
            if asset["status"] == "VALIDATED":
                evidence = asset.get("validation_evidence")
                if not isinstance(evidence, list) or not evidence:
                    raise ValueError(f"VALIDATED {identifier} needs validation_evidence")
        print(f"PASS: asset registry validates ({len(ids)} assets)")
        return 0
    except (OSError, ValueError, yaml.YAMLError) as error:
        return fail(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
