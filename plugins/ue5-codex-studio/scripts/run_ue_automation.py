#!/usr/bin/env python3
"""Run an allowlisted UE Automation test filter with fixed editor arguments.

Without --execute this command only prints the exact execution plan. It never
accepts a raw UE command, console command, or commandlet argument.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml


FILTER = re.compile(r"^Project\.(?:Smoke|Automation)\.[A-Za-z0-9_.]+$")
OPERATION_ID = re.compile(r"^operation_[a-z0-9_]+$")


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def editor_path(ue_root: Path) -> Path:
    return ue_root / "Engine" / "Binaries" / "Win64" / "UnrealEditor-Cmd.exe"


def make_command(editor: Path, project: Path, test_filter: str) -> list[str]:
    return [
        str(editor), str(project),
        f"-ExecCmds=Automation RunTests {test_filter}; Quit",
        "-unattended", "-nop4", "-nosplash", "-NullRHI",
    ]


def write_evidence(path: Path, operation_id: str, subject_refs: list[str], result: str, state: str,
                   command: list[str], started_at: str, finished_at: str, log_path: Path, detail: str,
                   toolchain_sha256: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({
        "schema_version": 1,
        "id": "evidence_" + operation_id.removeprefix("operation_"),
        "operation_id": operation_id,
        "subject_refs": subject_refs,
        "level": "RUNTIME",
        "result": result,
        "kind": "runtime",
        "state": state,
        "execution_profile": "local-editor",
        "tool": "UnrealEditor-Cmd.exe",
        "toolchain_sha256": toolchain_sha256,
        "command": command,
        "started_at": started_at,
        "finished_at": finished_at,
        "log": {"path": str(log_path), "sha256": sha256_file(log_path)},
        "detail": detail,
        "automatic_retry": False,
    }, sort_keys=False), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Path to an existing .uproject file")
    parser.add_argument("--ue-root", type=Path, required=True)
    parser.add_argument("--test-filter", required=True)
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--subject-ref", action="append", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if args.project.suffix != ".uproject" or not args.project.is_file():
        return fail("project must be an existing .uproject file")
    if not FILTER.fullmatch(args.test_filter):
        return fail("test filter must be an allowlisted Project.Smoke.* or Project.Automation.* path")
    if not OPERATION_ID.fullmatch(args.operation_id):
        return fail("operation ID must start with operation_")
    if args.timeout_seconds < 1:
        return fail("timeout must be positive")
    editor = editor_path(args.ue_root)
    if not editor.is_file():
        return fail(f"UnrealEditor-Cmd.exe missing under {args.ue_root}")
    version = args.ue_root / "Engine" / "Build" / "Build.version"
    if not version.is_file():
        return fail("UE Build.version is required for reproducible evidence")
    command = make_command(editor.resolve(), args.project.resolve(), args.test_filter)
    plan = {"status": "PLANNED" if not args.execute else "EXECUTING", "command": command, "timeout_seconds": args.timeout_seconds}
    if not args.execute:
        print(yaml.safe_dump(plan, sort_keys=False), end="")
        return 0
    started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    log_path = args.evidence.with_suffix(".log")
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=args.timeout_seconds, check=False)
        output = (completed.stdout or "") + (completed.stderr or "")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(output, encoding="utf-8")
        finished = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        if completed.returncode == 0:
            write_evidence(args.evidence, args.operation_id, args.subject_ref, "PASS", "SUCCEEDED", command, started, finished, log_path, "automation process exited successfully", sha256_file(version))
            print(f"PASS: UE automation evidence written to {args.evidence}")
            return 0
        write_evidence(args.evidence, args.operation_id, args.subject_ref, "FAIL", "FAILED", command, started, finished, log_path, f"automation process exited {completed.returncode}", sha256_file(version))
        return fail(f"UE automation failed; evidence written to {args.evidence}")
    except subprocess.TimeoutExpired as error:
        output = (error.stdout or "") + (error.stderr or "")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(output if isinstance(output, str) else output.decode("utf-8", errors="replace"), encoding="utf-8")
        finished = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        write_evidence(args.evidence, args.operation_id, args.subject_ref, "UNKNOWN", "UNKNOWN", command, started, finished, log_path, "automation timed out; manual reconciliation required", sha256_file(version))
        return fail(f"UE automation timed out; UNKNOWN evidence written to {args.evidence}")
    except OSError as error:
        return fail(f"could not start UE automation: {error}")


if __name__ == "__main__":
    raise SystemExit(main())
