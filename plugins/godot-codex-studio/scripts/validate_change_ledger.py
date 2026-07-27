#!/usr/bin/env python3
"""Validate a revision impact ledger before stale downstream work is cleared."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


CLASSIFICATIONS = {"COPY_EDIT", "CONTENT_EDIT", "STRUCTURAL"}
STALE_KINDS = {"string", "translation", "subtitle", "vo_take", "cue", "sequence", "clue", "level_trigger", "work_item", "test", "evidence"}


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    args = parser.parse_args()
    try:
        ledger = yaml.safe_load(args.ledger.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        return fail(f"cannot read ledger: {error}")
    if not isinstance(ledger, dict) or ledger.get("schema_version") != 1 or not isinstance(ledger.get("id"), str) or not ledger["id"].startswith("change_"):
        return fail("ledger needs schema_version 1 and a change_ ID")
    classification = ledger.get("classification")
    if classification not in CLASSIFICATIONS or not ledger.get("source_hash_before") or not ledger.get("source_hash_after"):
        return fail("ledger needs classification and before/after source hashes")
    changes = ledger.get("changes")
    if not isinstance(changes, list) or not changes:
        return fail("ledger needs at least one changed stable ID")
    changed_ids = []
    for change in changes:
        if not isinstance(change, dict) or not isinstance(change.get("id"), str) or not change["id"] or not isinstance(change.get("source_span_ids"), list) or not change["source_span_ids"]:
            return fail("each change needs ID and source_span_ids")
        changed_ids.append(change["id"])
    if len(set(changed_ids)) != len(changed_ids):
        return fail("change IDs must be unique")
    stale = ledger.get("stale")
    if not isinstance(stale, list):
        return fail("ledger stale must be a list")
    stale_ids = []
    for item in stale:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str) or item.get("kind") not in STALE_KINDS or item.get("status") != "STALE" or not isinstance(item.get("caused_by"), list) or not set(item["caused_by"]) <= set(changed_ids):
            return fail("each stale record needs stable ID, known kind, STALE status, and changed cause")
        stale_ids.append(item["id"])
    if len(set(stale_ids)) != len(stale_ids):
        return fail("stale IDs must be unique")
    if classification in {"CONTENT_EDIT", "STRUCTURAL"} and not stale:
        return fail("content or structural changes must mark downstream artifacts stale")
    if classification == "STRUCTURAL" and not ledger.get("approval_record"):
        return fail("structural changes require approval_record")
    print("PASS: change ledger preserves revision impact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
