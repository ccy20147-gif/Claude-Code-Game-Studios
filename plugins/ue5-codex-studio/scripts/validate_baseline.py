#!/usr/bin/env python3
"""Validate a baseline against its canonical GDD and optional profile delivery."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from schema_validation import load_yaml, sha256_file, validate_schema
from validate_canonical_gdd import validate as validate_gdd


STATUSES = {"DRAFT", "CANDIDATE", "ACCEPTED", "SUPERSEDED"}


def fail(message: str, code: int = 1) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return code


def resolve_gdd(baseline_path: Path, baseline: dict, explicit: Path | None) -> Path:
    if explicit:
        return explicit
    reference = baseline.get("gdd", {})
    path = reference.get("path") if isinstance(reference, dict) else None
    if not isinstance(path, str) or not path or Path(path).is_absolute() or ".." in Path(path).parts:
        raise ValueError("baseline gdd.path must be a safe relative path")
    return baseline_path.parent / path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("baseline", type=Path)
    parser.add_argument("--gdd", type=Path, help="Legacy explicit GDD path; omitted paths resolve from baseline.gdd.path.")
    parser.add_argument("--require-accepted", action="store_true")
    parser.add_argument("--profile-delivery", type=Path)
    parser.add_argument("--require-profile-delivery", action="store_true")
    args = parser.parse_args()
    try:
        baseline = load_yaml(args.baseline)
    except (OSError, ValueError) as error:
        return fail(str(error))
    version = baseline.get("schema_version")
    if version not in {1, 2}:
        return fail("baseline must declare schema version 1 or 2")
    if version == 1 and args.require_accepted:
        return fail("LEGACY_SCHEMA_READ_ONLY: schema version 2 is required for an acceptance gate", 2)
    if version == 2:
        errors = validate_schema(baseline, "baseline.schema.json")
        if errors:
            return fail("; ".join(errors))
    elif baseline.get("status") not in STATUSES:
        return fail("baseline must have a valid status")
    if args.require_accepted and baseline.get("status") != "ACCEPTED":
        return fail("baseline must be ACCEPTED")
    if baseline.get("status") != "ACCEPTED":
        print("PASS: baseline is structurally valid but not accepted")
        return 0
    try:
        gdd_path = resolve_gdd(args.baseline, baseline, args.gdd)
        gdd = load_yaml(gdd_path)
    except (OSError, ValueError) as error:
        return fail(str(error))
    errors = validate_gdd(gdd, require_ready=True)
    gdd_ref = baseline.get("gdd")
    acceptance = baseline.get("acceptance")
    if not isinstance(gdd_ref, dict):
        errors.append("accepted baseline requires a GDD reference")
    else:
        if gdd_ref.get("revision") != gdd.get("revision"):
            errors.append("accepted baseline must reference the reconciled GDD revision")
        if version == 2:
            if gdd_ref.get("id") != gdd.get("id"):
                errors.append("accepted baseline must reference the reconciled GDD ID")
            if gdd_ref.get("sha256") != sha256_file(gdd_path):
                errors.append("accepted baseline GDD hash does not match the referenced GDD")
    if not isinstance(acceptance, dict) or acceptance.get("status") != "APPROVED" or acceptance.get("approver") != "user" or not acceptance.get("record"):
        errors.append("accepted baseline requires a direct user approval record")
    if version == 2 and not baseline.get("requirements"):
        errors.append("accepted baseline requires at least one requirement")
    if args.require_profile_delivery and not args.profile_delivery:
        errors.append("accepted baseline requires profile delivery")
    if args.profile_delivery:
        from subprocess import run

        project = args.profile_delivery.parents[1] / ".ue5-codex-studio" / "project.yaml"
        result = run([sys.executable, str(Path(__file__).with_name("validate_profile_delivery.py")), str(args.profile_delivery), "--require-current", "--project", str(project)], capture_output=True, text=True, check=False)
        if result.returncode:
            errors.append(result.stderr.strip() or "profile delivery is invalid")
    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PASS: accepted baseline is backed by a reconciled GDD and user approval")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
