#!/usr/bin/env python3
"""Run an in-memory AtlasCloud credential session on HTTP loopback."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import yaml

from atlascloud_core import (
    ASSET_ID,
    AtlasClient,
    AtlasError,
    Contract,
    IN_PROGRESS,
    TERMINAL_FAILURE,
    TERMINAL_SUCCESS,
    atomic_json,
    now_iso,
    project_path,
    redacted_request_hash,
    sha256_file,
    validate_image_file,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCK = ROOT / "integrations/atlascloud/model-lock.yaml"
SAFE_PREDICTION = re.compile(r"[A-Za-z0-9_-]{1,160}$")
TYPE_EXTENSIONS = {
    "GLB": ".glb", "OBJ": ".obj", "FBX": ".fbx", "USDZ": ".usdz",
    "STL": ".stl", "MTL": ".mtl", "PNG": ".png", "JPG": ".jpg", "JPEG": ".jpeg",
}


def _atomic_yaml(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            yaml.safe_dump(value, stream, sort_keys=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _secure_windows_file(path: Path) -> None:
    os.chmod(path, 0o600)
    if os.name != "nt":
        return
    username = os.environ.get("USERNAME")
    if not username:
        raise AtlasError("cannot secure session state without USERNAME")
    result = subprocess.run(
        ["icacls", str(path), "/inheritance:r", "/grant:r", f"{username}:(R,W)"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        raise AtlasError("failed to apply the current-user ACL to session state")


class AtlasSession:
    def __init__(
        self,
        project: Path,
        registry_relative: str,
        contract: Contract,
        client: AtlasClient,
        *,
        max_jobs: int,
    ):
        self.project = project.resolve()
        if not self.project.is_dir():
            raise AtlasError("project root does not exist")
        self.registry = project_path(self.project, registry_relative)
        self.contract = contract
        self.client = client
        if not 1 <= max_jobs <= 100:
            raise AtlasError("max_jobs must be between 1 and 100")
        self.max_jobs = max_jobs
        self.submitted_jobs = 0
        self.jobs_dir = self.project / ".ue5-codex-studio" / "atlascloud" / "jobs"
        self.lock = threading.RLock()
        self.reserved_asset_ids: set[str] = set()
        if self.jobs_dir.is_dir():
            for path in self.jobs_dir.glob("*.json"):
                try:
                    value = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    raise AtlasError(f"existing AtlasCloud job record is invalid: {path.name}")
                identifier = value.get("asset_id") if isinstance(value, dict) else None
                if not isinstance(identifier, str) or not ASSET_ID.fullmatch(identifier):
                    raise AtlasError(f"existing AtlasCloud job lacks a valid asset ID: {path.name}")
                self.reserved_asset_ids.add(identifier)

    def health(self) -> dict[str, Any]:
        return {
            "status": "ready",
            "provider": "atlascloud",
            "contract_sha256": self.contract.sha256,
            "models": sorted(self.contract.models),
            "max_jobs": self.max_jobs,
            "submitted_jobs": self.submitted_jobs,
        }

    def _registry_document(self) -> dict[str, Any]:
        if not self.registry.exists():
            return {"schema_version": 1, "assets": []}
        try:
            value = yaml.safe_load(self.registry.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise AtlasError(f"cannot read asset registry: {error}") from error
        if not isinstance(value, dict) or value.get("schema_version") != 1 or not isinstance(value.get("assets"), list):
            raise AtlasError("asset registry is not a supported schema_version 1 document")
        return value

    def _asset_ids(self, registry: dict[str, Any]) -> set[str]:
        identifiers = {item.get("id") for item in registry["assets"] if isinstance(item, dict)}
        if any(not isinstance(item, str) or not ASSET_ID.fullmatch(item) for item in identifiers):
            raise AtlasError("asset registry contains an invalid asset ID")
        return identifiers

    def _job_path(self, prediction_id: str) -> Path:
        if not SAFE_PREDICTION.fullmatch(prediction_id):
            raise AtlasError("prediction ID is invalid")
        return self.jobs_dir / f"{prediction_id}.json"

    def _save_job(self, job: dict[str, Any]) -> None:
        atomic_json(self._job_path(job["prediction_id"]), job)

    def get_job(self, prediction_id: str) -> dict[str, Any]:
        path = self._job_path(prediction_id)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise AtlasError("local job record does not exist or is invalid") from error
        if not isinstance(value, dict) or value.get("prediction_id") != prediction_id:
            raise AtlasError("local job record identity is invalid")
        return value

    def submit(self, request: object) -> dict[str, Any]:
        if not isinstance(request, dict):
            raise AtlasError("generation request must be an object")
        tool = request.get("tool")
        asset_id = request.get("asset_id")
        rights_record = request.get("rights_record")
        destination = request.get("target_destination")
        source_asset_ids = request.get("source_asset_ids", [])
        if not isinstance(tool, str) or not isinstance(asset_id, str) or not ASSET_ID.fullmatch(asset_id):
            raise AtlasError("generation request needs a valid tool and asset_id")
        if not isinstance(rights_record, str) or not rights_record.strip():
            raise AtlasError("rights_record is required")
        if not isinstance(destination, str) or not destination.startswith("/Game/") or ".." in destination:
            raise AtlasError("target_destination must be a safe /Game/ path")
        if not isinstance(source_asset_ids, list) or not all(isinstance(item, str) and ASSET_ID.fullmatch(item) for item in source_asset_ids):
            raise AtlasError("source_asset_ids are invalid")
        approval_record = request.get("approval_record")
        if tool == "atlas_edit_concept" and (
            not isinstance(approval_record, str)
            or not re.fullmatch(r"approval_[a-z0-9_.-]{1,200}", approval_record)
        ):
            raise AtlasError("editing an existing asset requires a valid approval_ record")
        if tool == "atlas_edit_concept" and not source_asset_ids:
            raise AtlasError("editing requires at least one registered source asset")
        model, parameters = self.contract.validate_arguments(tool, request.get("parameters"))
        with self.lock:
            registry = self._registry_document()
            existing = self._asset_ids(registry)
            if asset_id in existing:
                raise AtlasError("generated asset_id already exists; overwrite is refused")
            if asset_id in self.reserved_asset_ids:
                raise AtlasError("generated asset_id is already reserved by an AtlasCloud job")
            if not set(source_asset_ids) <= existing:
                raise AtlasError("source_asset_ids must resolve in the asset registry")
            if self.submitted_jobs >= self.max_jobs:
                raise AtlasError("AtlasCloud session job limit reached")
            self.submitted_jobs += 1
            self.reserved_asset_ids.add(asset_id)

        local_inputs: list[dict[str, str]] = []
        upstream_parameters = dict(parameters)
        if "images" in parameters:
            uploaded = []
            for relative in parameters["images"]:
                path = project_path(self.project, relative, must_exist=True)
                validate_image_file(path, 64 * 1024 * 1024)
                local_inputs.append({"path": relative, "sha256": sha256_file(path)})
                uploaded.append(self.client.upload(path))
            upstream_parameters["images"] = uploaded
        if "image" in parameters:
            path = project_path(self.project, parameters["image"], must_exist=True)
            validate_image_file(path, 6 * 1024 * 1024)
            local_inputs.append({"path": parameters["image"], "sha256": sha256_file(path)})
            upstream_parameters["image"] = self.client.upload(path)
        started_at = now_iso()
        prompt_sha = hashlib.sha256(parameters.get("prompt", "").encode()).hexdigest() if "prompt" in parameters else None
        request_hash = redacted_request_hash(model.id, parameters)
        try:
            result = self.client.submit(model, upstream_parameters)
        except AtlasError:
            # Submission failures are not retried because acceptance by the remote
            # service may be unknowable after a transport failure.
            raise
        job = {
            "schema_version": 1,
            "prediction_id": result["id"],
            "status": result["status"],
            "asset_id": asset_id,
            "model": model.id,
            "tool": tool,
            "capability_id": model.capability_id,
            "effect": model.effect,
            "output_kind": model.output_kind,
            "rights_record": rights_record,
            "approval_record": approval_record,
            "target_destination": destination,
            "source_asset_ids": source_asset_ids,
            "input_files": local_inputs,
            "prompt_sha256": prompt_sha,
            "redacted_request_hash": request_hash,
            "contract_sha256": self.contract.sha256,
            "started_at": started_at,
            "parameters": {key: value for key, value in parameters.items() if key not in {"prompt", "images", "image"}},
        }
        self._save_job(job)
        return job

    def _output_candidates(self, result: dict[str, Any], job: dict[str, Any]) -> list[dict[str, str]]:
        candidates: list[dict[str, str]] = []
        files = result.get("files")
        if isinstance(files, list):
            for item in files:
                if not isinstance(item, dict) or not isinstance(item.get("url"), str):
                    raise AtlasError("AtlasCloud files output is invalid")
                file_type = str(item.get("type", "")).upper()
                extension = TYPE_EXTENSIONS.get(file_type)
                name = Path(str(item.get("file_name", ""))).name
                if not extension and name:
                    extension = Path(name).suffix.lower()
                if not extension:
                    raise AtlasError("AtlasCloud output lacks a recognized file type")
                candidates.append({"url": item["url"], "extension": extension, "name": name})
        outputs = result.get("outputs")
        if not candidates and isinstance(outputs, list):
            for index, url in enumerate(outputs):
                if not isinstance(url, str):
                    raise AtlasError("AtlasCloud outputs list is invalid")
                extension = Path(urllib.parse.urlparse(url).path).suffix.lower()
                if not extension:
                    if job["output_kind"] == "image":
                        extension = "." + str(job["parameters"].get("output_format", "png")).replace("jpeg", "jpg")
                    else:
                        extension = ".glb" if index == 0 else ".png"
                candidates.append({"url": url, "extension": extension, "name": ""})
        if not candidates:
            raise AtlasError("completed prediction has no downloadable outputs")
        return candidates

    def _finalize(self, result: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
        output_policy = self.contract.outputs[job["output_kind"]]
        allowed_extensions = set(output_policy["extensions"])
        allowed_content_types = set(output_policy["content_types"])
        destination = self.project / "Generated" / "AtlasCloud" / job["asset_id"] / job["prediction_id"]
        staging = self.project / ".ue5-codex-studio" / "atlascloud" / "staging" / job["prediction_id"]
        artifacts: list[dict[str, Any]] = []
        with self.lock:
            registry = self._registry_document()
            if job["asset_id"] in self._asset_ids(registry):
                raise AtlasError("asset appeared during generation; registry overwrite is refused")
            if destination.exists() or staging.exists():
                raise AtlasError("artifact destination or staging already exists; overwrite is refused")
            used_names: set[str] = set()
            try:
                for index, candidate in enumerate(self._output_candidates(result, job)):
                    extension = candidate["extension"].lower()
                    if extension not in allowed_extensions:
                        raise AtlasError(f"AtlasCloud output extension is not allowed: {extension}")
                    raw_name = candidate["name"]
                    name = Path(raw_name).name if raw_name and Path(raw_name).suffix.lower() == extension else f"output_{index}{extension}"
                    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,160}", name) or name in used_names:
                        name = f"output_{index}{extension}"
                    used_names.add(name)
                    temporary_target = staging / name
                    digest, size, content_type = self.client.download(
                        candidate["url"], temporary_target, output_policy["maximum_bytes"], allowed_content_types,
                    )
                    final_target = destination / name
                    artifacts.append({
                        "path": final_target.relative_to(self.project).as_posix(),
                        "sha256": digest,
                        "bytes": size,
                        "content_type": content_type,
                    })
                destination.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staging, destination)
            except Exception:
                if staging.exists():
                    shutil.rmtree(staging)
                raise
        evidence_id = "evidence_atlas_" + hashlib.sha256(job["prediction_id"].encode()).hexdigest()[:20]
        evidence_path = self.project / "production" / "generation" / f"{evidence_id}.yaml"
        evidence = {
            "schema_version": 1,
            "id": evidence_id,
            "operation_id": "operation_" + job["tool"],
            "subject_refs": [job["asset_id"]],
            "level": "OBSERVED",
            "result": "PENDING_LOCAL_VALIDATION",
            "kind": "cloud_generation",
            "state": "SUCCEEDED",
            "execution_profile": "cloud",
            "provider": "atlascloud",
            "model": job["model"],
            "prediction_id": job["prediction_id"],
            "capability_id": job["capability_id"],
            "approval_record": job.get("approval_record"),
            "contract_sha256": job["contract_sha256"],
            "redacted_request_hash": job["redacted_request_hash"],
            "prompt_sha256": job.get("prompt_sha256"),
            "input_artifacts": job["input_files"],
            "output_artifacts": artifacts,
            "credits_consumed": result.get("credits_consumed"),
            "started_at": job["started_at"],
            "finished_at": now_iso(),
        }
        _atomic_yaml(evidence_path, evidence)
        with self.lock:
            registry = self._registry_document()
            if job["asset_id"] in self._asset_ids(registry):
                raise AtlasError("asset appeared during evidence creation; registry overwrite is refused")
            registry["assets"].append({
                "id": job["asset_id"],
                "kind": "mesh" if job["output_kind"] == "mesh" else "texture",
                "status": "PENDING_LOCAL_VALIDATION",
                "source": {
                    "origin": "AI_GENERATED",
                    "provider": "atlascloud",
                    "model": job["model"],
                    "prediction_id": job["prediction_id"],
                    "prompt_sha256": job.get("prompt_sha256") or hashlib.sha256(b"").hexdigest(),
                    "artifact_sha256": artifacts[0]["sha256"],
                    "request_sha256": job["redacted_request_hash"],
                    "input_asset_ids": job["source_asset_ids"],
                    "rights_record": job["rights_record"],
                    "generation_evidence": evidence_path.relative_to(self.project).as_posix(),
                },
                "files": [item["path"] for item in artifacts],
                "target": {"engine": "UE5", "destination": job["target_destination"]},
                "validation_evidence": [evidence_id],
            })
            _atomic_yaml(self.registry, registry)
        job.update({
            "status": "collected",
            "finished_at": evidence["finished_at"],
            "artifacts": artifacts,
            "evidence": evidence_path.relative_to(self.project).as_posix(),
        })
        self._save_job(job)
        return job

    def collect(self, prediction_id: str, wait_seconds: int = 0) -> dict[str, Any]:
        if not isinstance(wait_seconds, int) or not 0 <= wait_seconds <= 30:
            raise AtlasError("wait_seconds must be between 0 and 30")
        job = self.get_job(prediction_id)
        if job.get("status") == "collected":
            return job
        if job.get("status") == "unknown":
            raise AtlasError("UNKNOWN jobs require manual provider reconciliation; automatic collection is refused")
        deadline = time.monotonic() + wait_seconds
        while True:
            try:
                result = self.client.prediction(prediction_id)
            except AtlasError:
                job.update({"status": "unknown", "unknown_at": now_iso()})
                self._save_job(job)
                raise
            status = str(result["status"]).lower()
            if status in TERMINAL_FAILURE:
                job.update({"status": "failed", "finished_at": now_iso()})
                self._save_job(job)
                return job
            if status in TERMINAL_SUCCESS:
                return self._finalize(result, job)
            job["status"] = status
            self._save_job(job)
            if time.monotonic() >= deadline:
                return job
            time.sleep(min(2, max(0, deadline - time.monotonic())))


def make_handler(session: AtlasSession, token: str, stop_event: threading.Event):
    class Handler(BaseHTTPRequestHandler):
        server_version = "AtlasCloudControlled/1.0"

        def log_message(self, format: str, *args: object) -> None:
            return

        def _authorized(self) -> bool:
            presented = self.headers.get("X-Atlas-Session-Token", "")
            return bool(presented) and hmac.compare_digest(token, presented)

        def _body(self) -> object:
            length = int(self.headers.get("Content-Length", "0") or 0)
            if not 0 <= length <= 1024 * 1024:
                raise AtlasError("session request exceeds 1 MiB")
            return json.loads(self.rfile.read(length).decode("utf-8")) if length else {}

        def _reply(self, status: int, value: object) -> None:
            raw = json.dumps(value, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def _run(self, action) -> None:  # type: ignore[no-untyped-def]
            if not self._authorized():
                self._reply(401, {"error": "session token rejected"})
                return
            try:
                self._reply(200, action())
            except (AtlasError, json.JSONDecodeError, ValueError) as error:
                self._reply(400, {"error": str(error)})

        def do_GET(self) -> None:
            if self.path == "/health":
                self._run(session.health)
            elif self.path == "/models":
                self._run(lambda: {"contract_sha256": session.contract.sha256, "models": sorted(session.contract.models)})
            elif self.path.startswith("/jobs/"):
                self._run(lambda: session.get_job(self.path.removeprefix("/jobs/")))
            else:
                self._reply(404, {"error": "route not found"})

        def do_POST(self) -> None:
            if self.path == "/generate":
                self._run(lambda: session.submit(self._body()))
            elif self.path == "/collect":
                self._run(lambda: session.collect(**self._body()))
            elif self.path == "/session/stop":
                def stop() -> dict[str, bool]:
                    stop_event.set()
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                    return {"stopping": True}
                self._run(stop)
            else:
                self._reply(404, {"error": "route not found"})

    return Handler


def _state_request(state_path: Path, method: str, route: str) -> dict[str, Any]:
    state = json.loads(state_path.read_text(encoding="utf-8"))
    endpoint = state.get("endpoint")
    token = state.get("token")
    if not isinstance(endpoint, str) or not endpoint.startswith("http://127.0.0.1:") or not isinstance(token, str):
        raise AtlasError("session state is invalid")
    request = urllib.request.Request(endpoint + route, method=method, headers={"X-Atlas-Session-Token": token})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            value = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as error:
        raise AtlasError(f"session request failed: {type(error).__name__}") from error
    if not isinstance(value, dict):
        raise AtlasError("session returned invalid JSON")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    start = subparsers.add_parser("start")
    start.add_argument("--project", type=Path, required=True)
    start.add_argument("--registry", default="assets/asset-registry.yaml")
    start.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    start.add_argument("--state-file", type=Path)
    start.add_argument("--max-jobs", type=int, default=3)
    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("--state-file", type=Path, required=True)
    stop = subparsers.add_parser("stop")
    stop.add_argument("--state-file", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            health = _state_request(args.state_file, "GET", "/health")
            print(f"PASS: AtlasCloud session ready; contract {health['contract_sha256']}")
            return 0
        if args.command == "stop":
            _state_request(args.state_file, "POST", "/session/stop")
            args.state_file.unlink(missing_ok=True)
            print("PASS: AtlasCloud session stopped")
            return 0
        project = args.project.resolve()
        candidate = args.state_file or Path(".ue5-codex-studio/atlascloud-session.json")
        state_file = (candidate if candidate.is_absolute() else project / candidate).resolve()
        if state_file != project and project not in state_file.parents:
            raise AtlasError("session state must remain inside the project")
        if state_file.exists():
            raise AtlasError("session state already exists; stop or inspect the existing session first")
        api_key = getpass.getpass("AtlasCloud API key (kept only in this process): ").strip()
        contract = Contract(args.lock)
        client = AtlasClient(contract, api_key)
        session = AtlasSession(project, args.registry, contract, client, max_jobs=args.max_jobs)
        token = secrets.token_urlsafe(48)
        stop_event = threading.Event()
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(session, token, stop_event))
        endpoint = f"http://127.0.0.1:{server.server_address[1]}"
        state = {
            "schema_version": 1,
            "endpoint": endpoint,
            "token": token,
            "contract_sha256": contract.sha256,
            "project": str(project),
            "registry": args.registry,
            "pid": os.getpid(),
            "max_jobs": args.max_jobs,
        }
        atomic_json(state_file, state)
        _secure_windows_file(state_file)
        print(f"AtlasCloud session ready at {endpoint}; state: {state_file}", flush=True)
        try:
            server.serve_forever(poll_interval=0.25)
        finally:
            server.server_close()
            state_file.unlink(missing_ok=True)
        return 0
    except (AtlasError, OSError, KeyError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
