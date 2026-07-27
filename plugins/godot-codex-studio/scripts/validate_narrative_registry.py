#!/usr/bin/env python3
"""Validate fiction-to-game traceability and an actionable core gameplay loop."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


DECISIONS = {"preserve", "compress", "reorder", "cut", "invent"}
STATUSES = {"mapped", "excluded", "deferred"}


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def ids(items: object, prefix: str) -> set[str] | None:
    if not isinstance(items, list):
        return None
    values = [item.get("id") for item in items if isinstance(item, dict)]
    if len(values) != len(items) or any(not isinstance(value, str) or not value.startswith(prefix) for value in values) or len(set(values)) != len(values):
        return None
    return set(values)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("registry", type=Path)
    parser.add_argument("--source", type=Path, required=True, help="normalized source-span YAML from import_narrative.py")
    args = parser.parse_args()
    try:
        registry = yaml.safe_load(args.registry.read_text(encoding="utf-8"))
        source = yaml.safe_load(args.source.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        return fail(f"cannot read registry or source: {error}")
    if not isinstance(registry, dict) or registry.get("schema_version") != 1 or not isinstance(source, dict):
        return fail("registry and normalized source must be schema version 1 mappings")
    source_ids = ids(source.get("spans"), "source_span_")
    registry_ids = registry.get("source_spans")
    if source_ids is None or not isinstance(registry_ids, list) or set(registry_ids) != source_ids or len(registry_ids) != len(source_ids):
        return fail("registry source_spans must exactly match normalized source spans")
    coverage = registry.get("coverage")
    if not isinstance(coverage, list):
        return fail("registry coverage must be a list")
    by_span = {}
    for item in coverage:
        if not isinstance(item, dict) or item.get("source_span_id") not in source_ids or item.get("status") not in STATUSES:
            return fail("each coverage entry needs a known source_span_id and valid status")
        if item["source_span_id"] in by_span:
            return fail("each source span must have exactly one coverage entry")
        by_span[item["source_span_id"]] = item
    if set(by_span) != source_ids:
        return fail("coverage must account for every normalized source span")
    adaptation_ids = ids(registry.get("adaptations"), "adapt_")
    requirement_ids = ids(registry.get("game_requirements"), "req_")
    if adaptation_ids is None or requirement_ids is None:
        return fail("adaptations and game_requirements need unique stable IDs")
    for item in registry["adaptations"]:
        spans = item.get("source_span_ids")
        requirements = item.get("game_requirement_ids")
        if item.get("decision") not in DECISIONS or not isinstance(spans, list) or not spans or not set(spans) <= source_ids:
            return fail(f"adaptation {item['id']} needs a valid decision and source spans")
        if not isinstance(requirements, list) or not set(requirements) <= requirement_ids:
            return fail(f"adaptation {item['id']} references unknown game requirements")
        if item["decision"] == "invent" and not item.get("approval_record"):
            return fail(f"invent adaptation {item['id']} requires approval_record")
    for item in registry["game_requirements"]:
        links = item.get("adaptation_ids")
        if not isinstance(links, list) or not links or not set(links) <= adaptation_ids or not item.get("description"):
            return fail(f"game requirement {item['id']} needs description and adaptation links")
    if ids(registry.get("characters"), "character_") is None or ids(registry.get("beats"), "beat_") is None:
        return fail("characters and beats need unique stable IDs")
    core_loop = registry.get("core_loop")
    if not isinstance(core_loop, dict) or not core_loop.get("player_actions") or not core_loop.get("success_state") or not core_loop.get("failure_or_cost") or not core_loop.get("feedback"):
        return fail("core_loop needs player actions, success, failure/cost, and feedback")
    print("PASS: narrative registry is source-traceable and gameable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
