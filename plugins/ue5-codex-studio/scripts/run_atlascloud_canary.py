#!/usr/bin/env python3
"""Run one controlled concept, edit, and Hunyuan mesh AtlasCloud canary."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


class CanaryError(RuntimeError):
    pass


def _http_error_detail(error: urllib.error.HTTPError) -> str:
    try:
        raw = error.read(8193)
        if len(raw) > 8192:
            return "session error response exceeded 8 KiB"
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return f"HTTP {error.code}"
    detail = value.get("error") if isinstance(value, dict) else None
    if not isinstance(detail, str) or not detail or len(detail) > 500 or any(ord(character) < 32 for character in detail):
        return f"HTTP {error.code}"
    return detail


def request(state: dict[str, Any], path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
    value = urllib.request.Request(
        state["endpoint"] + path,
        method="GET" if payload is None else "POST",
        data=data,
        headers={"X-Atlas-Session-Token": state["token"], "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(value, timeout=45) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise CanaryError(f"local session rejected {path}: {_http_error_detail(error)}; request was not retried") from error
    except (urllib.error.URLError, OSError) as error:
        if path == "/generate":
            raise CanaryError(
                "local session transport failed at /generate; submission outcome is UNKNOWN and manual provider reconciliation is required"
            ) from error
        raise CanaryError(f"local session transport failed at {path}; request was not retried") from error
    except json.JSONDecodeError as error:
        raise CanaryError(f"local session returned invalid JSON at {path}; request was not retried") from error
    if not isinstance(result, dict):
        raise CanaryError("local session returned invalid JSON")
    return result


def collect(state: dict[str, Any], prediction_id: str, timeout: int) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while True:
        result = request(state, "/collect", {"prediction_id": prediction_id, "wait_seconds": 30})
        status = result.get("status")
        if status == "collected":
            return result
        if status == "failed":
            raise CanaryError(f"AtlasCloud prediction {prediction_id} failed")
        if time.monotonic() >= deadline:
            raise CanaryError(f"AtlasCloud prediction {prediction_id} remains UNKNOWN after timeout")


def generate(state: dict[str, Any], payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    submitted = request(state, "/generate", payload)
    prediction_id = submitted.get("prediction_id")
    if not isinstance(prediction_id, str):
        raise CanaryError("submission did not return a prediction ID")
    return collect(state, prediction_id, timeout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--approve-spend", action="store_true")
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    if not args.approve_spend:
        print("FAIL: real AtlasCloud canary requires --approve-spend", file=sys.stderr)
        return 1
    try:
        if not 60 <= args.timeout <= 1800:
            raise CanaryError("timeout must be between 60 and 1800 seconds")
        state = json.loads(args.state_file.read_text(encoding="utf-8"))
        if not isinstance(state, dict) or not str(state.get("endpoint", "")).startswith("http://127.0.0.1:"):
            raise CanaryError("state is not a loopback AtlasCloud session")
        health = request(state, "/health")
        if health.get("max_jobs", 0) - health.get("submitted_jobs", 0) < 3:
            raise CanaryError("session needs capacity for exactly three canary jobs")
        suffix = time.strftime("%Y%m%d%H%M%S", time.gmtime()).lower()
        concept_id = f"asset_codex_canary_concept_{suffix}"
        edit_id = f"asset_codex_canary_edit_{suffix}"
        mesh_id = f"asset_codex_canary_mesh_{suffix}"
        common = {
            "rights_record": "rights_atlascloud_canary_nonshipping_review_pending",
            "target_destination": f"/Game/__CodexCanary_/AtlasCloud/{suffix}",
        }
        concept = generate(state, {
            "tool": "atlas_generate_concept", "asset_id": concept_id, **common,
            "parameters": {
                "prompt": "Single ceremonial steel sword centered on a plain light gray background, full object visible, no text, no hands, orthographic product concept art",
                "size": "1024x1024", "quality": "medium", "output_format": "png",
            },
        }, args.timeout)
        concept_file = concept["artifacts"][0]["path"]
        edited = generate(state, {
            "tool": "atlas_edit_concept", "asset_id": edit_id, **common,
            "source_asset_ids": [concept_id], "approval_record": "approval_user_atlascloud_canary_20260728",
            "parameters": {
                "prompt": "Preserve the sword design exactly; remove any remaining visual clutter and place it on a uniform light gray background, full silhouette visible, no text",
                "images": [concept_file], "size": "1024x1024", "quality": "medium", "output_format": "png",
            },
        }, args.timeout)
        edited_file = edited["artifacts"][0]["path"]
        mesh = generate(state, {
            "tool": "atlas_generate_mesh", "asset_id": mesh_id, **common,
            "source_asset_ids": [edit_id],
            "parameters": {"image": edited_file, "generate_type": "Normal", "enable_pbr": True, "face_count": 40000},
        }, args.timeout)
        glb = next((item["path"] for item in mesh["artifacts"] if item["path"].lower().endswith(".glb")), None)
        if not glb:
            raise CanaryError("Hunyuan canary completed without a GLB output")
        project = Path(state["project"])
        validation = subprocess.run(
            [sys.executable, str(ROOT / "scripts/validate_generated_mesh.py"), str(project / glb), "--max-triangles", "1500000"],
            capture_output=True, text=True, check=False,
        )
        if validation.returncode != 0:
            raise CanaryError(f"Hunyuan GLB failed coarse validation: {validation.stderr.strip()}")
        report = {
            "status": "PASS",
            "contract_sha256": health["contract_sha256"],
            "assets": [concept_id, edit_id, mesh_id],
            "predictions": [concept["prediction_id"], edited["prediction_id"], mesh["prediction_id"]],
            "mesh": glb,
            "local_state": "PENDING_LOCAL_VALIDATION",
        }
        print(json.dumps(report, indent=2))
        return 0
    except (CanaryError, OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
