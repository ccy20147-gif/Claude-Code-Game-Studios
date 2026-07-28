from __future__ import annotations

import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from atlascloud_core import AtlasClient, AtlasError, Contract  # noqa: E402
from atlascloud_session import AtlasSession  # noqa: E402
from run_atlascloud_canary import CanaryError, request as canary_request  # noqa: E402


LOCK = ROOT / "integrations/atlascloud/model-lock.yaml"
CONTRACT_SHA = "136b2e027b37465f28071c63d975b12fe3c8c4af094d7ef5d7a91f85e7711257"


def minimal_glb() -> bytes:
    value = {
        "asset": {"version": "2.0"},
        "accessors": [{"count": 3}, {"count": 3, "componentType": 5123}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}, "indices": 1}]}],
    }
    raw = json.dumps(value, separators=(",", ":")).encode()
    raw += b" " * ((4 - len(raw) % 4) % 4)
    return struct.pack("<IIIII", 0x46546C67, 2, 20 + len(raw), len(raw), 0x4E4F534A) + raw


class FakeAtlas:
    def __init__(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                return

            def reply(self, value: object, content_type: str = "application/json") -> None:
                raw = json.dumps(value).encode() if content_type == "application/json" else value
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_POST(self) -> None:
                owner.authorization.append(self.headers.get("Authorization"))
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length)
                if self.path.endswith("/uploadMedia"):
                    owner.upload_bodies.append(raw)
                    self.reply({"data": {"url": owner.origin + "/artifact/uploaded.png"}})
                    return
                if self.path.endswith("/generateImage"):
                    payload = json.loads(raw.decode())
                    owner.submissions.append(payload)
                    identifier = f"pred_{len(owner.submissions)}"
                    owner.predictions[identifier] = payload["model"]
                    self.reply({"code": 200, "data": {"id": identifier, "status": "processing", "model": payload["model"]}})
                    return
                self.send_error(404)

            def do_GET(self) -> None:
                owner.authorization.append(self.headers.get("Authorization"))
                if self.path.startswith("/api/v1/model/prediction/"):
                    identifier = self.path.rsplit("/", 1)[-1]
                    model = owner.predictions[identifier]
                    if model == "tencent/hunyuan3d-pro/image-to-3d":
                        self.reply({"data": {
                            "id": identifier, "status": "completed", "model": model,
                            "files": [{"url": owner.origin + "/artifact/coarse.glb", "type": "GLB", "content_type": "model/gltf-binary", "file_name": "coarse.glb"}],
                            "credits_consumed": 1.25,
                        }})
                    else:
                        self.reply({"data": {"id": identifier, "status": "completed", "model": model, "outputs": [owner.origin + "/artifact/concept.png"]}})
                    return
                if self.path == "/artifact/concept.png" or self.path == "/artifact/uploaded.png":
                    self.reply(b"\x89PNG\r\n\x1a\ncontrolled-image", "image/png")
                    return
                if self.path == "/artifact/coarse.glb":
                    self.reply(minimal_glb(), "model/gltf-binary")
                    return
                self.send_error(404)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.origin = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.authorization: list[str | None] = []
        self.upload_bodies: list[bytes] = []
        self.submissions: list[dict] = []
        self.predictions: dict[str, str] = {}
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class FakeBroker:
    def __init__(self, token: str):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:
                return

            def reply(self, value: object, status: int = 200) -> None:
                raw = json.dumps(value).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def authorized(self) -> bool:
                owner.tokens.append(self.headers.get("X-Atlas-Session-Token"))
                return self.headers.get("X-Atlas-Session-Token") == token

            def do_GET(self) -> None:
                if not self.authorized():
                    self.reply({"error": "rejected"}, 401)
                    return
                if self.path == "/health":
                    self.reply({"status": "ready", "provider": "atlascloud", "contract_sha256": CONTRACT_SHA})
                elif self.path == "/models":
                    self.reply({"contract_sha256": CONTRACT_SHA, "models": ["openai/gpt-image-2/text-to-image", "openai/gpt-image-2/edit", "tencent/hunyuan3d-pro/image-to-3d"]})
                else:
                    self.reply({"prediction_id": "pred_1", "status": "processing"})

            def do_POST(self) -> None:
                if not self.authorized():
                    self.reply({"error": "rejected"}, 401)
                    return
                length = int(self.headers.get("Content-Length", "0"))
                value = json.loads(self.rfile.read(length).decode())
                owner.requests.append((self.path, value))
                self.reply({"prediction_id": "pred_1", "status": "processing", "tool": value.get("tool")})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.origin = f"http://127.0.0.1:{self.server.server_address[1]}"
        self.tokens: list[str | None] = []
        self.requests: list[tuple[str, dict]] = []
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class AtlasCloudTests(unittest.TestCase):
    def run_script(self, relative: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(ROOT / relative), *args], cwd=ROOT, capture_output=True, text=True, check=False)

    def test_model_lock_is_exact_and_policy_bound(self) -> None:
        result = self.run_script("scripts/validate_atlascloud_lock.py", str(LOCK))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn(CONTRACT_SHA, result.stdout)
        contract = Contract(LOCK)
        with self.assertRaisesRegex(AtlasError, "unknown model parameters"):
            contract.validate_arguments("atlas_generate_concept", {"prompt": "sword", "seed": 1})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copy2(LOCK, root / "model-lock.yaml")
            shutil.copy2(ROOT / "integrations/atlascloud/policy.json", root / "policy.json")
            changed = yaml.safe_load((root / "model-lock.yaml").read_text(encoding="utf-8"))
            changed["models"][0]["defaults"]["quality"] = "high"
            (root / "model-lock.yaml").write_text(yaml.safe_dump(changed), encoding="utf-8")
            result = self.run_script("scripts/validate_atlascloud_lock.py", str(root / "model-lock.yaml"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("not bound", result.stderr)

    def test_canary_distinguishes_rejection_from_unknown_submission(self) -> None:
        token = "s" * 48
        with FakeBroker(token) as broker:
            state = {"endpoint": broker.origin, "token": "wrong-token"}
            with self.assertRaisesRegex(CanaryError, r"rejected /generate: rejected; request was not retried"):
                canary_request(state, "/generate", {"tool": "atlas_generate_concept"})
        state = {"endpoint": broker.origin, "token": token}
        with self.assertRaisesRegex(CanaryError, r"submission outcome is UNKNOWN.*manual provider reconciliation"):
            canary_request(state, "/generate", {"tool": "atlas_generate_concept"})

    def test_generation_collects_image_and_mesh_without_persisting_key_or_prompt(self) -> None:
        api_key = "atlas-secret-never-write"
        prompt = "single centered ceremonial sword on a plain background"
        with FakeAtlas() as upstream, tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = Contract(LOCK)
            client = AtlasClient(contract, api_key, api_origin=upstream.origin, allow_test_http=True)
            session = AtlasSession(project, "assets/asset-registry.yaml", contract, client, max_jobs=3)
            concept = session.submit({
                "tool": "atlas_generate_concept", "asset_id": "asset_sword_concept",
                "rights_record": "rights_project_original", "target_destination": "/Game/Art/Concept/Sword",
                "parameters": {"prompt": prompt, "quality": "high", "output_format": "png"},
            })
            with self.assertRaisesRegex(AtlasError, "reserved"):
                session.submit({
                    "tool": "atlas_generate_concept", "asset_id": "asset_sword_concept",
                    "rights_record": "rights_project_original", "target_destination": "/Game/Art/Concept/Sword",
                    "parameters": {"prompt": "duplicate must fail"},
                })
            job_text = session._job_path(concept["prediction_id"]).read_text(encoding="utf-8")
            self.assertNotIn(prompt, job_text)
            self.assertNotIn(api_key, job_text)
            concept = session.collect(concept["prediction_id"])
            self.assertEqual(concept["status"], "collected")
            concept_file = concept["artifacts"][0]["path"]
            mesh = session.submit({
                "tool": "atlas_generate_mesh", "asset_id": "asset_sword_mesh",
                "rights_record": "rights_project_original", "target_destination": "/Game/Weapons/Sword",
                "source_asset_ids": ["asset_sword_concept"],
                "parameters": {"image": concept_file, "generate_type": "Normal", "enable_pbr": True, "face_count": 40000},
            })
            mesh = session.collect(mesh["prediction_id"])
            mesh_path = project / mesh["artifacts"][0]["path"]
            registry_path = project / "assets/asset-registry.yaml"
            registry_result = self.run_script("scripts/validate_asset_registry.py", str(registry_path))
            self.assertEqual(registry_result.returncode, 0, registry_result.stderr + registry_result.stdout)
            coarse = self.run_script("scripts/validate_generated_mesh.py", str(mesh_path))
            self.assertEqual(coarse.returncode, 0, coarse.stderr + coarse.stdout)
            strict = self.run_script("scripts/validate_gltf_asset.py", str(mesh_path))
            self.assertEqual(strict.returncode, 1)
            for evidence in (project / "production/generation").glob("*.yaml"):
                validation = self.run_script("scripts/validate_evidence.py", str(evidence))
                self.assertEqual(validation.returncode, 0, validation.stderr + validation.stdout)
            tracked_text = "\n".join(
                path.read_text(encoding="utf-8", errors="ignore")
                for path in project.rglob("*") if path.is_file()
            )
            self.assertNotIn(api_key, tracked_text)
            self.assertNotIn(prompt, tracked_text)
            registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
            self.assertEqual([item["status"] for item in registry["assets"]], ["PENDING_LOCAL_VALIDATION", "PENDING_LOCAL_VALIDATION"])
            self.assertEqual(registry["assets"][1]["source"]["input_asset_ids"], ["asset_sword_concept"])
            self.assertEqual(upstream.submissions[0]["model"], "openai/gpt-image-2/text-to-image")
            self.assertEqual(upstream.submissions[1]["model"], "tencent/hunyuan3d-pro/image-to-3d")
            self.assertTrue(all(value == f"Bearer {api_key}" for value in upstream.authorization if value is not None))

    def test_unknown_poll_is_recorded_and_not_automatically_retried(self) -> None:
        with FakeAtlas() as upstream, tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            contract = Contract(LOCK)
            client = AtlasClient(contract, "secret", api_origin=upstream.origin, allow_test_http=True)
            session = AtlasSession(project, "assets/asset-registry.yaml", contract, client, max_jobs=1)
            job = session.submit({
                "tool": "atlas_generate_concept", "asset_id": "asset_unknown_concept",
                "rights_record": "rights_test", "target_destination": "/Game/Test/Unknown",
                "parameters": {"prompt": "unknown transport canary"},
            })
            calls = 0

            def fail_poll(prediction_id: str):
                nonlocal calls
                calls += 1
                raise AtlasError("transport state unknown")

            client.prediction = fail_poll  # type: ignore[method-assign]
            with self.assertRaisesRegex(AtlasError, "transport state unknown"):
                session.collect(job["prediction_id"])
            self.assertEqual(session.get_job(job["prediction_id"])["status"], "unknown")
            with self.assertRaisesRegex(AtlasError, "manual provider reconciliation"):
                session.collect(job["prediction_id"])
            self.assertEqual(calls, 1)

    def test_edit_requires_approval_and_registered_source(self) -> None:
        with FakeAtlas() as upstream, tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            image = project / "Source/concept.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"\x89PNG\r\n\x1a\nimage")
            registry = {
                "schema_version": 1,
                "assets": [{
                    "id": "asset_existing_concept", "kind": "texture", "status": "PENDING_LOCAL_VALIDATION",
                    "source": {"origin": "HUMAN_AUTHORED", "artifact_sha256": hashlib.sha256(b"\x89PNG\r\n\x1a\nimage").hexdigest(), "rights_record": "rights_original"},
                    "files": ["Source/concept.png"], "target": {"engine": "UE5", "destination": "/Game/Concept"},
                }],
            }
            registry_path = project / "assets/asset-registry.yaml"
            registry_path.parent.mkdir(parents=True)
            registry_path.write_text(yaml.safe_dump(registry), encoding="utf-8")
            contract = Contract(LOCK)
            session = AtlasSession(project, "assets/asset-registry.yaml", contract, AtlasClient(contract, "secret", api_origin=upstream.origin, allow_test_http=True), max_jobs=2)
            request = {
                "tool": "atlas_edit_concept", "asset_id": "asset_edited_concept",
                "rights_record": "rights_original", "target_destination": "/Game/EditedConcept",
                "source_asset_ids": ["asset_existing_concept"],
                "parameters": {"prompt": "make the hilt silver", "images": ["Source/concept.png"]},
            }
            with self.assertRaisesRegex(AtlasError, "approval"):
                session.submit(request)
            request["approval_record"] = "approval_user_20260728"
            job = session.submit(request)
            self.assertEqual(job["effect"], "MODIFY")
            self.assertEqual(upstream.submissions[0]["model"], "openai/gpt-image-2/edit")

    def test_controlled_adapter_exposes_fixed_surface_and_forwards_only_session_token(self) -> None:
        token = "s" * 48
        with FakeBroker(token) as broker, tempfile.TemporaryDirectory() as temporary:
            state = Path(temporary) / "session.json"
            state.write_text(json.dumps({"schema_version": 1, "endpoint": broker.origin, "token": token, "contract_sha256": CONTRACT_SHA}), encoding="utf-8")
            requests = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "atlas_generate_concept", "arguments": {
                    "asset_id": "asset_shield_concept", "rights_record": "rights_1", "target_destination": "/Game/Concept/Shield", "prompt": "shield",
                }}},
                {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "atlas_edit_concept", "arguments": {
                    "asset_id": "asset_shield_edit", "rights_record": "rights_1", "target_destination": "/Game/Concept/ShieldEdit",
                    "source_asset_ids": ["asset_shield_concept"], "images": ["Source/shield.png"], "prompt": "silver",
                }}},
            ]
            process = subprocess.run(
                ["node", str(ROOT / "integrations/atlascloud/adapter.mjs"), "--state-file", str(state)],
                input="\n".join(json.dumps(item) for item in requests) + "\n", capture_output=True, text=True, check=False,
            )
        self.assertEqual(process.returncode, 0, process.stderr)
        responses = [json.loads(line) for line in process.stdout.splitlines()]
        names = {item["name"] for item in responses[1]["result"]["tools"]}
        self.assertEqual(names, {"atlas_health", "atlas_models", "atlas_generate_concept", "atlas_edit_concept", "atlas_generate_mesh", "atlas_collect_job", "atlas_get_job"})
        self.assertNotIn("atlas_quick_generate", names)
        self.assertNotIn("delete_asset", names)
        self.assertEqual(broker.requests[0][1]["tool"], "atlas_generate_concept")
        self.assertNotIn("model", broker.requests[0][1])
        self.assertTrue(all(value == token for value in broker.tokens))
        self.assertIn("approval_record is required", responses[3]["error"]["message"])

    def test_provisioner_refuses_unapproved_install_and_configuration_collision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "Project"
            project.mkdir()
            fake_codex = Path(temporary) / "fake-codex"
            fake_codex.write_text("#!/bin/sh\nif [ \"$1\" = mcp ] && [ \"$2\" = get ]; then echo '{}'; exit 0; fi\necho '{}'; exit 0\n", encoding="utf-8")
            fake_codex.chmod(0o755)
            result = self.run_script("scripts/provision_atlascloud.py", "install", "--project", str(project), "--codex", str(fake_codex))
            self.assertEqual(result.returncode, 1)
            self.assertIn("requires --approve", result.stderr)
            result = self.run_script("scripts/provision_atlascloud.py", "install", "--project", str(project), "--codex", str(fake_codex), "--approve")
        self.assertEqual(result.returncode, 1)
        self.assertIn("refusing to overwrite", result.stderr)


if __name__ == "__main__":
    unittest.main()
