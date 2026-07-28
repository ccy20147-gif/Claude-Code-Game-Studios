#!/usr/bin/env python3
"""Validate the fail-closed AtlasCloud model contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml


EXPECTED = {
    "openai/gpt-image-2/text-to-image": ("atlas_generate_concept", "cloud.asset.concept.create", "CREATE", "image"),
    "openai/gpt-image-2/edit": ("atlas_edit_concept", "cloud.asset.concept.modify", "MODIFY", "image"),
    "tencent/hunyuan3d-pro/image-to-3d": ("atlas_generate_mesh", "cloud.asset.mesh.create", "CREATE", "mesh"),
}
SAFE_KEY = re.compile(r"[a-z][a-z0-9_]*$")


def canonical_sha(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a mapping")
    return value


def load_and_validate(path: Path) -> tuple[dict[str, Any], str]:
    lock = mapping(yaml.safe_load(path.read_text(encoding="utf-8")), "lock")
    if lock.get("schema_version") != 1 or lock.get("provider") != "atlascloud":
        raise ValueError("lock needs schema_version 1 and provider atlascloud")
    if lock.get("api_origin") != "https://api.atlascloud.ai":
        raise ValueError("AtlasCloud API origin must be fixed")
    paths = mapping(lock.get("paths"), "paths")
    expected_paths = {
        "submit": "/api/v1/model/generateImage",
        "prediction": "/api/v1/model/prediction/{prediction_id}",
        "upload": "/api/v1/model/uploadMedia",
    }
    if paths != expected_paths:
        raise ValueError("AtlasCloud paths differ from the reviewed contract")
    models = lock.get("models")
    if not isinstance(models, list) or {model.get("id") for model in models if isinstance(model, dict)} != set(EXPECTED):
        raise ValueError("model lock must contain exactly the three reviewed models")
    for model in models:
        model = mapping(model, "model")
        expected = EXPECTED[model["id"]]
        actual = tuple(model.get(key) for key in ("tool", "capability_id", "effect", "output_kind"))
        if actual != expected:
            raise ValueError(f"{model['id']} identity or effect drifted")
        required = model.get("required")
        optional = model.get("optional")
        if not isinstance(required, list) or not required or not isinstance(optional, list):
            raise ValueError(f"{model['id']} needs required and optional parameters")
        parameters = required + optional
        if len(parameters) != len(set(parameters)) or any(not isinstance(item, str) or not SAFE_KEY.fullmatch(item) for item in parameters):
            raise ValueError(f"{model['id']} has invalid or duplicate parameters")
        defaults = mapping(model.get("defaults", {}), f"{model['id']}.defaults")
        if not set(defaults) <= set(optional):
            raise ValueError(f"{model['id']} defaults contain an undeclared parameter")
        for key, values in mapping(model.get("enums", {}), f"{model['id']}.enums").items():
            if key not in parameters or not isinstance(values, list) or not values or len(values) != len(set(values)):
                raise ValueError(f"{model['id']}.{key} has an invalid enum")
            if key in defaults and defaults[key] not in values:
                raise ValueError(f"{model['id']}.{key} default is outside its enum")
        for key, limits in mapping(model.get("ranges", {}), f"{model['id']}.ranges").items():
            limits = mapping(limits, f"{model['id']}.{key}")
            if key not in parameters or set(limits) != {"minimum", "maximum"} or limits["minimum"] > limits["maximum"]:
                raise ValueError(f"{model['id']}.{key} has an invalid range")
    outputs = mapping(lock.get("outputs"), "outputs")
    if set(outputs) != {"image", "mesh"}:
        raise ValueError("outputs must define image and mesh")
    for kind, raw in outputs.items():
        output = mapping(raw, f"outputs.{kind}")
        if not isinstance(output.get("maximum_bytes"), int) or output["maximum_bytes"] < 1:
            raise ValueError(f"outputs.{kind} needs a positive maximum_bytes")
        if not isinstance(output.get("extensions"), list) or not all(isinstance(item, str) and item.startswith(".") for item in output["extensions"]):
            raise ValueError(f"outputs.{kind} has invalid extensions")
        if not isinstance(output.get("content_types"), list) or not all(isinstance(item, str) and "/" in item for item in output["content_types"]):
            raise ValueError(f"outputs.{kind} has invalid content types")
    return lock, canonical_sha(lock)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lock", type=Path)
    args = parser.parse_args()
    try:
        lock, fingerprint = load_and_validate(args.lock)
        policy_path = args.lock.with_name("policy.json")
        if policy_path.is_file():
            policy = json.loads(policy_path.read_text(encoding="utf-8"))
            if not isinstance(policy, dict) or policy.get("contract_sha256") != fingerprint:
                raise ValueError("AtlasCloud adapter policy is not bound to this model lock")
            policy_models = {value.get("model") for value in policy.get("tools", {}).values() if isinstance(value, dict)}
            if policy_models != set(EXPECTED):
                raise ValueError("AtlasCloud adapter policy model set drifted")
    except (OSError, ValueError, KeyError, json.JSONDecodeError, yaml.YAMLError) as error:
        return fail(str(error))
    print(f"PASS: AtlasCloud model lock validates ({len(lock['models'])} models; sha256={fingerprint})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
