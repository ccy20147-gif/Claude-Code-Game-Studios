#!/usr/bin/env python3
"""Build a Win64 Shipping UE package with fixed UAT BuildCookRun arguments."""

from __future__ import annotations

import argparse
import hashlib
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


OPERATION_ID = __import__("re").compile(r"^operation_[a-z0-9_]+$")


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def uat_path(ue_root: Path) -> Path:
    return ue_root / "Engine" / "Build" / "BatchFiles" / "RunUAT.bat"


def make_command(uat: Path, project: Path, staging: Path) -> list[str]:
    return [
        str(uat), "BuildCookRun", f"-project={project}", "-noP4", "-platform=Win64",
        "-clientconfig=Shipping", "-build", "-cook", "-stage", "-pak", "-archive",
        f"-archivedirectory={staging}",
    ]


def package_files(staging: Path, excluded: set[Path]) -> list[dict[str, object]]:
    entries = []
    for path in sorted(item for item in staging.rglob("*") if item.is_file() and item not in excluded):
        entries.append({"path": str(path.relative_to(staging)), "size": path.stat().st_size, "sha256": sha256_file(path)})
    return entries


def write_evidence(path: Path, operation_id: str, subject_refs: list[str], result: str, state: str,
                   command: list[str], started: str, finished: str, log_path: Path, version_hash: str,
                   manifest: Path | None, detail: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    document: dict[str, object] = {
        "schema_version": 1, "id": "evidence_" + operation_id.removeprefix("operation_"),
        "operation_id": operation_id, "subject_refs": subject_refs, "level": "RUNTIME",
        "result": result, "kind": "runtime", "state": state, "execution_profile": "local-editor",
        "tool": "RunUAT.bat", "toolchain_sha256": version_hash, "command": command,
        "started_at": started, "finished_at": finished,
        "log": {"path": str(log_path), "sha256": sha256_file(log_path)},
        "detail": detail, "automatic_retry": False,
    }
    if manifest is not None:
        document["package_manifest"] = {"path": str(manifest), "sha256": sha256_file(manifest)}
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Path to an existing .uproject file")
    parser.add_argument("--ue-root", type=Path, required=True)
    parser.add_argument("--staging-dir", type=Path, required=True)
    parser.add_argument("--package-manifest", type=Path)
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--subject-ref", action="append", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=7200)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.project.suffix != ".uproject" or not args.project.is_file():
        return fail("project must be an existing .uproject file")
    if not OPERATION_ID.fullmatch(args.operation_id):
        return fail("operation ID must start with operation_")
    if args.timeout_seconds < 1:
        return fail("timeout must be positive")
    uat = uat_path(args.ue_root)
    version = args.ue_root / "Engine" / "Build" / "Build.version"
    if not uat.is_file() or not version.is_file():
        return fail("UE root must contain RunUAT.bat and Engine/Build/Build.version")
    staging = args.staging_dir.resolve()
    if staging.exists() and any(staging.iterdir()):
        return fail("staging directory must not already contain files; this command never clears it")
    manifest = (args.package_manifest or (staging / "package-manifest.yaml")).resolve()
    if manifest.parent != staging and staging not in manifest.parents:
        return fail("package manifest must be written inside the staging directory")
    command = make_command(uat.resolve(), args.project.resolve(), staging)
    plan = {"status": "PLANNED" if not args.execute else "EXECUTING", "platform": "Win64", "configuration": "Shipping", "command": command, "timeout_seconds": args.timeout_seconds}
    if not args.execute:
        print(yaml.safe_dump(plan, sort_keys=False), end="")
        return 0
    started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    log_path = args.evidence.with_suffix(".log")
    try:
        staging.mkdir(parents=True, exist_ok=True)
        completed = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout_seconds, check=False)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text((completed.stdout or "") + (completed.stderr or ""), encoding="utf-8")
        finished = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if completed.returncode != 0:
            write_evidence(args.evidence, args.operation_id, args.subject_ref, "FAIL", "FAILED", command, started, finished, log_path, sha256_file(version), None, f"UAT exited {completed.returncode}")
            return fail(f"UAT package failed; evidence written to {args.evidence}")
        files = package_files(staging, {manifest})
        if not files:
            write_evidence(args.evidence, args.operation_id, args.subject_ref, "FAIL", "FAILED", command, started, finished, log_path, sha256_file(version), None, "UAT exited successfully but produced no staged files")
            return fail("UAT produced no staged files")
        manifest.parent.mkdir(parents=True, exist_ok=True)
        manifest.write_text(yaml.safe_dump({"schema_version": 1, "platform": "Win64", "configuration": "Shipping", "project": str(args.project.resolve()), "files": files}, sort_keys=False), encoding="utf-8")
        write_evidence(args.evidence, args.operation_id, args.subject_ref, "PASS", "SUCCEEDED", command, started, finished, log_path, sha256_file(version), manifest, "UAT package completed")
        print(f"PASS: package manifest written to {manifest}")
        return 0
    except subprocess.TimeoutExpired as error:
        output = (error.stdout or "") + (error.stderr or "")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(output if isinstance(output, str) else output.decode("utf-8", errors="replace"), encoding="utf-8")
        finished = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        write_evidence(args.evidence, args.operation_id, args.subject_ref, "UNKNOWN", "UNKNOWN", command, started, finished, log_path, sha256_file(version), None, "UAT timed out; manual reconciliation required")
        return fail(f"UAT timed out; UNKNOWN evidence written to {args.evidence}")
    except OSError as error:
        return fail(f"could not start UAT: {error}")


if __name__ == "__main__":
    raise SystemExit(main())
