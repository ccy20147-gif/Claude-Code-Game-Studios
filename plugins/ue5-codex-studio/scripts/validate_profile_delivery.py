#!/usr/bin/env python3
"""Validate profile-specific design deliverables before a UE5 baseline can be accepted."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

from schema_validation import load_yaml, validate_schema


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def required(mapping: dict, name: str) -> bool:
    value = mapping.get(name)
    return isinstance(value, list) and bool(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("delivery", type=Path)
    parser.add_argument("--project", type=Path)
    parser.add_argument("--require-current", action="store_true")
    args = parser.parse_args()
    try:
        delivery = load_yaml(args.delivery)
    except (OSError, ValueError, yaml.YAMLError) as error:
        return fail(f"cannot read delivery: {error}")
    if args.require_current:
        errors = validate_schema(delivery, "profile-delivery.schema.json")
        if errors:
            return fail("; ".join(errors))
        if not args.project:
            return fail("current profile delivery validation requires --project")
        try:
            project = load_yaml(args.project)
        except (OSError, ValueError) as error:
            return fail(str(error))
        if project.get("schema_version") != 2:
            return fail("project profile must use schema version 2")
        profile_ref = delivery["project_profile"]
        from schema_validation import sha256_file
        if profile_ref.get("sha256") != sha256_file(args.project):
            return fail("profile delivery project hash does not match")
        profiles = project["profiles"]
    else:
        if not isinstance(delivery.get("profiles"), dict):
            return fail("delivery requires a profiles mapping")
        profiles = delivery["profiles"]
    artifacts = delivery.get("artifacts", {})
    if not isinstance(artifacts, dict):
        return fail("delivery artifacts must be a mapping")
    missing: list[str] = []
    if profiles.get("experience") == "linear":
        missing.extend(name for name in ("beats", "scenes", "lines", "cues") if not required(artifacts, name))
    if profiles.get("investigation") == "clue-graph":
        missing.extend(name for name in ("truths", "clues", "inferences") if not required(artifacts, name))
        truth_ids = {item.get("id") for item in artifacts.get("truths", []) if isinstance(item, dict)}
        clues = artifacts.get("clues", [])
        linked = {truth for clue in clues if isinstance(clue, dict) for truth in clue.get("supports", [])}
        if truth_ids - linked:
            missing.append("clues supporting every truth")
    if profiles.get("experience") == "systemic":
        simulation = artifacts.get("simulation")
        if not isinstance(simulation, dict):
            missing.append("simulation")
        else:
            missing.extend(name for name in ("entities", "layers", "seed", "soak_scenarios") if not simulation.get(name))
    if profiles.get("presentation") == "2.5d":
        presentation = artifacts.get("presentation")
        if not isinstance(presentation, dict):
            missing.append("presentation")
        else:
            missing.extend(name for name in ("camera", "projection", "depth_sort", "asset_representation") if not presentation.get(name))
    if missing:
        return fail("profile delivery missing " + ", ".join(sorted(set(missing))))
    print("PASS: profile delivery is valid")
    return 0
