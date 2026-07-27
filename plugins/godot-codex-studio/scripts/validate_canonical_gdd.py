#!/usr/bin/env python3
"""Validate that an imported GDD has been reconciled into Codex Studio truth."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


SECTION_IDS = {
    "vision", "core_loop", "scope", "systems", "content", "ux_accessibility", "art_audio", "technical", "validation",
}
DOCUMENT_STATUSES = {"DRAFT", "RECONCILING", "READY_FOR_BASELINE", "SUPERSEDED"}
SECTION_STATUSES = {"DRAFT", "EXTRACTED", "CONFIRMED", "NOT_APPLICABLE", "DEFERRED"}
QUESTION_STATES = {"OPEN", "ANSWERED", "DEFERRED"}
EXTERNAL_DISPOSITIONS = {"UNVERIFIED", "EXTRACTED", "IGNORED", "REJECTED"}


def validate(document: object, require_ready: bool = False) -> list[str]:
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        return ["canonical GDD must be a schema version 1 mapping"]
    errors: list[str] = []
    if not isinstance(document.get("id"), str) or not document["id"].startswith("gdd_"):
        errors.append("GDD id must start with gdd_")
    if not isinstance(document.get("revision"), int) or document["revision"] < 1:
        errors.append("GDD revision must be a positive integer")
    if document.get("status") not in DOCUMENT_STATUSES:
        errors.append("GDD status is invalid")

    source_refs = document.get("source_refs")
    source_ids: set[str] = set()
    if not isinstance(source_refs, list) or not source_refs:
        errors.append("GDD requires at least one source reference")
    else:
        for item in source_refs:
            source_id = item.get("id") if isinstance(item, dict) else None
            if not isinstance(source_id, str) or not source_id.startswith("source_") or source_id in source_ids:
                errors.append("source references need unique source_ IDs")
                break
            source_ids.add(source_id)

    claims = document.get("external_claims", [])
    if not isinstance(claims, list):
        errors.append("external_claims must be a list")
    else:
        claim_ids: set[str] = set()
        for claim in claims:
            if not isinstance(claim, dict):
                errors.append("external claims must be mappings")
                continue
            claim_id = claim.get("id")
            if not isinstance(claim_id, str) or not claim_id.startswith("claim_") or claim_id in claim_ids:
                errors.append("external claims need unique claim_ IDs")
            claim_ids.add(claim_id)
            if claim.get("source_ref_id") not in source_ids:
                errors.append(f"external claim {claim_id} references an unknown source")
            if claim.get("disposition") not in EXTERNAL_DISPOSITIONS:
                errors.append(f"external claim {claim_id} has an invalid disposition")
            if claim.get("kind") == "approval" and claim.get("disposition") not in {"UNVERIFIED", "IGNORED", "REJECTED"}:
                errors.append(f"external approval claim {claim_id} cannot establish Codex Studio acceptance")

    sections = document.get("sections")
    seen_sections: set[str] = set()
    if not isinstance(sections, list):
        errors.append("GDD sections must be a list")
    else:
        for section in sections:
            if not isinstance(section, dict):
                errors.append("GDD sections must be mappings")
                continue
            section_id = section.get("id")
            if section_id not in SECTION_IDS or section_id in seen_sections:
                errors.append("GDD sections must contain each canonical section exactly once")
                continue
            seen_sections.add(section_id)
            if section.get("status") not in SECTION_STATUSES:
                errors.append(f"section {section_id} has an invalid status")
            source_links = section.get("source_ref_ids")
            if not isinstance(source_links, list) or not set(source_links) <= source_ids:
                errors.append(f"section {section_id} has invalid source references")
            if section.get("status") in {"CONFIRMED", "EXTRACTED"} and not section.get("content"):
                errors.append(f"section {section_id} needs content")
            if section.get("status") in {"NOT_APPLICABLE", "DEFERRED"} and not section.get("decision_record"):
                errors.append(f"section {section_id} needs an explicit decision record")
        if seen_sections != SECTION_IDS:
            errors.append("GDD is missing one or more canonical sections")

    questions = document.get("questions")
    if not isinstance(questions, list):
        errors.append("GDD questions must be a list")
    else:
        question_ids: set[str] = set()
        for question in questions:
            if not isinstance(question, dict):
                errors.append("GDD questions must be mappings")
                continue
            question_id = question.get("id")
            if not isinstance(question_id, str) or not question_id.startswith("question_") or question_id in question_ids:
                errors.append("questions need unique question_ IDs")
            question_ids.add(question_id)
            if question.get("section_id") not in SECTION_IDS or not question.get("prompt"):
                errors.append(f"question {question_id} needs a section and prompt")
            if question.get("state") not in QUESTION_STATES:
                errors.append(f"question {question_id} has an invalid state")
            if question.get("state") in {"ANSWERED", "DEFERRED"} and not question.get("decision_record"):
                errors.append(f"question {question_id} needs a user decision record")

    eligibility = document.get("baseline_eligibility")
    confirmation = document.get("user_confirmation")
    if not isinstance(eligibility, dict) or eligibility.get("status") not in {"BLOCKED", "READY"}:
        errors.append("baseline_eligibility must be BLOCKED or READY")
    if not isinstance(confirmation, dict) or confirmation.get("status") not in {"PENDING", "CONFIRMED"}:
        errors.append("user_confirmation must be PENDING or CONFIRMED")

    if require_ready:
        if document.get("status") != "READY_FOR_BASELINE" or eligibility.get("status") != "READY":
            errors.append("GDD is not ready for baseline review")
        if not isinstance(sections, list) or any(section.get("status") not in {"CONFIRMED", "NOT_APPLICABLE", "DEFERRED"} for section in sections if isinstance(section, dict)):
            errors.append("every canonical section must be confirmed or explicitly decided")
        if not isinstance(questions, list) or any(question.get("state") == "OPEN" for question in questions if isinstance(question, dict)):
            errors.append("open GDD questions block baseline review")
        if not isinstance(claims, list) or any(claim.get("disposition") == "UNVERIFIED" for claim in claims if isinstance(claim, dict)):
            errors.append("unverified external claims block baseline review")
        if not isinstance(confirmation, dict) or confirmation.get("status") != "CONFIRMED" or not confirmation.get("record"):
            errors.append("direct user confirmation of the reconciled GDD is required")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gdd", type=Path)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    try:
        document = yaml.safe_load(args.gdd.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        print(f"FAIL: cannot read GDD: {error}", file=sys.stderr)
        return 1
    errors = validate(document, require_ready=args.require_ready)
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PASS: canonical GDD is reconciled" if args.require_ready else "PASS: canonical GDD is structurally valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
