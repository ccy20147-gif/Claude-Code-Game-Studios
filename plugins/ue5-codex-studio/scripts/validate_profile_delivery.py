#!/usr/bin/env python3
"""Validate profile-specific design deliverables before a UE5 baseline can be accepted."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def required(mapping: dict, name: str) -> bool:
    value = mapping.get(name)
    return isinstance(value, list) and bool(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("delivery", type=Path)
    args = parser.parse_args()
    try:
        delivery = yaml.safe_load(args.delivery.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        return fail(f"cannot read delivery: {error}")
    if not isinstance(delivery, dict) or not isinstance(delivery.get("profiles"), dict):
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
