from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "integrations" / "ue5ultimatemcp" / "adapter.mjs"
PROVISIONER = ROOT / "scripts" / "provision_ue5ultimatemcp.py"


def fingerprint(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")).hexdigest()


class FakeUE:
    def __init__(self, tools: list[dict[str, object]]) -> None:
        self.tools = tools
        self.requests: list[tuple[str, str, object]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_: object) -> None:
                pass

            def reply(self, status: int, payload: object) -> None:
                encoded = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def do_GET(self) -> None:  # noqa: N802
                outer.requests.append((self.path, self.headers.get("X-UE5-Codex-Token", ""), None))
                if self.headers.get("X-UE5-Codex-Token") != "x" * 48:
                    self.reply(401, {"error": "token"})
                elif self.path == "/api/health":
                    self.reply(200, {"status": "ok", "port": self.server.server_port})
                elif self.path == "/api/tools":
                    self.reply(200, {"tools": outer.tools, "count": len(outer.tools)})
                else:
                    self.reply(404, {"error": "missing"})

            def do_POST(self) -> None:  # noqa: N802
                raw = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                body = json.loads(raw or b"{}")
                outer.requests.append((self.path, self.headers.get("X-UE5-Codex-Token", ""), body))
                if self.headers.get("X-UE5-Codex-Token") != "x" * 48:
                    self.reply(401, {"error": "token"})
                elif body.get("tool") == "get_level_info":
                    self.reply(200, {"success": True, "result": {"map_name": "__CodexCanary_Test"}})
                elif body.get("tool") == "find_actors_by_name":
                    self.reply(200, {"success": True, "result": {"count": 0}})
                else:
                    self.reply(200, {"success": True, "result": body})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> "FakeUE":
        self.thread.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.server.shutdown()
        self.thread.join()


class UE5UltimateMCPTests(unittest.TestCase):
    @staticmethod
    def catalog() -> list[dict[str, object]]:
        return [{"name": name, "description": name, "category": "test", "readOnly": True, "destructive": False, "parameters": []} for name in (
            "get_level_info", "get_actors_in_level", "find_actors_by_name", "capture_viewport", "spawn_actor", "delete_actor"
        )]

    def adapter(self, state: Path, requests: list[dict[str, object]]) -> list[dict[str, object]]:
        payload = "".join(json.dumps(item) + "\n" for item in requests)
        result = subprocess.run(["node", str(ADAPTER), "--state-file", str(state)], input=payload, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        return [json.loads(line) for line in result.stdout.splitlines() if line]

    def write_state(self, root: Path, service: FakeUE, catalog: list[dict[str, object]], expected: str | None = None) -> Path:
        state = root / "state.json"
        state.write_text(json.dumps({
            "schema_version": 1,
            "token": "x" * 48,
            "endpoint": f"http://127.0.0.1:{service.server.server_port}",
            "catalog": {"sha256": expected or fingerprint(catalog)},
        }), encoding="utf-8")
        return state

    def test_adapter_exposes_only_controlled_tools_and_forwards_token(self) -> None:
        catalog = self.catalog()
        with FakeUE(catalog) as service, tempfile.TemporaryDirectory() as temporary:
            state = self.write_state(Path(temporary), service, catalog)
            replies = self.adapter(state, [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "ue_get_level", "arguments": {}}},
            ])
        exposed = {item["name"] for item in replies[1]["result"]["tools"]}
        self.assertEqual(replies[0]["result"]["serverInfo"]["name"], "ue5ultimatemcp-controlled")
        self.assertIn("ue_canary_create_actor", exposed)
        self.assertNotIn("delete_asset", exposed)
        self.assertNotIn("run_console_command", exposed)
        self.assertEqual(replies[2]["result"]["content"][0]["type"], "text")
        self.assertTrue(all(token == "x" * 48 for _, token, _ in service.requests))

    def test_adapter_fails_closed_on_schema_drift_and_unknown_tools(self) -> None:
        catalog = self.catalog()
        with FakeUE(catalog) as service, tempfile.TemporaryDirectory() as temporary:
            state = self.write_state(Path(temporary), service, catalog, "0" * 64)
            reply = self.adapter(state, [{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "ue_get_level", "arguments": {}}}])[0]
            self.assertIn("schema drift", reply["error"]["message"])
        with FakeUE(catalog + [{"name": "future_write", "parameters": []}]) as service, tempfile.TemporaryDirectory() as temporary:
            state = self.write_state(Path(temporary), service, catalog + [{"name": "future_write", "parameters": []}])
            reply = self.adapter(state, [{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "ue_get_level", "arguments": {}}}])[0]
            self.assertIn("unrecognized tool", reply["error"]["message"])

    def test_canary_write_rejects_non_canary_map_before_mutation(self) -> None:
        catalog = self.catalog()
        with FakeUE(catalog) as service, tempfile.TemporaryDirectory() as temporary:
            state = self.write_state(Path(temporary), service, catalog)
            reply = self.adapter(state, [{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "ue_canary_create_actor", "arguments": {"canary_map": "/Game/Main", "name": "__CodexCanary_A", "type": "PointLight"}}}])[0]
        self.assertIn("canary_map", reply["error"]["message"])
        self.assertFalse(any(isinstance(body, dict) and body.get("tool") == "spawn_actor" for _, _, body in service.requests))

    def test_provisioner_requires_explicit_approval_before_platform_checks(self) -> None:
        result = subprocess.run([sys.executable, str(PROVISIONER), "install", "--project", "/definitely/missing", "--ue-root", "/definitely/missing"], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("requires --approve", result.stderr)

    def test_plan_rejects_non_cpp_fixture_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "Game.uproject").write_text("{}", encoding="utf-8")
            engine = root / "UE" / "Engine" / "Build"
            engine.mkdir(parents=True)
            (engine / "Build.version").write_text(json.dumps({"MajorVersion": 5, "MinorVersion": 7, "PatchVersion": 4}), encoding="utf-8")
            result = subprocess.run([sys.executable, str(PROVISIONER), "plan", "--project", str(root), "--ue-root", str(root / "UE")], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("BLOCKED", result.stdout)
        self.assertIn("project_is_cpp: false", result.stdout)


if __name__ == "__main__":
    unittest.main()
