#!/usr/bin/env python3
"""Run a loopback-only MCP HTTP guard with default-deny action policy.

The guarded client sends its capability token in ``X-UE5-Codex-Token``.  A
``tools/call`` also needs a ``_meta.ue5_codex`` envelope containing stable
capability and binding identities.  The guard intentionally refuses to proxy
unrecognised MCP methods: discovery should use a separate read-only endpoint
or an explicitly approved route.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

from mcp_security import PolicyError, authorize, load_policy, token_decision


MAX_BODY_BYTES = 1_048_576


def json_reply(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


def authorize_payload(policy: dict[str, Any], backend: str, payload: object, expected_binding: dict[str, Any]):
    """Extract the required envelope and authorize it without making a network call."""
    if not isinstance(payload, dict) or payload.get("method") != "tools/call":
        return None, "METHOD_REJECTED"
    params = payload.get("params")
    if not isinstance(params, dict) or not isinstance(params.get("name"), str):
        return None, "invalid_tool_call"
    arguments = params.get("arguments")
    if not isinstance(arguments, dict):
        arguments = {}
    meta = arguments.get("_meta")
    envelope = meta.get("ue5_codex") if isinstance(meta, dict) else None
    if not isinstance(envelope, dict):
        return None, "BINDING_REQUIRED"
    decision = authorize(
        policy,
        {
            "backend": backend,
            "capability_id": envelope.get("capability_id"),
            "tool": params["name"],
            "action": arguments.get("action") or arguments.get("subAction"),
            "skill_name": envelope.get("skill_name"),
            "backend_tool": envelope.get("backend_tool"),
            "approval_record": envelope.get("approval_record"),
            "binding": envelope.get("binding"),
            "expected_binding": expected_binding,
        },
    )
    return payload if decision.allowed else None, decision.code


def make_handler(policy: dict[str, Any], backend: str, upstream: str, expected_binding: dict[str, Any]):
    class GuardHandler(BaseHTTPRequestHandler):
        server_version = "UE5CodexMCPGuard/1"

        def log_message(self, format: str, *args: object) -> None:
            # Request bodies and authentication headers are intentionally never logged.
            print("mcp-guard: " + format % args, file=sys.stderr)

        def do_GET(self) -> None:
            if self.path == "/health":
                json_reply(self, 200, {"status": "ok", "backend": backend})
                return
            json_reply(self, 404, {"error": "not_found"})

        def do_POST(self) -> None:
            if self.path != "/mcp":
                json_reply(self, 404, {"error": "not_found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = -1
            if length <= 0 or length > MAX_BODY_BYTES:
                json_reply(self, 413, {"error": "invalid_request_size"})
                return
            token = token_decision(policy, self.headers.get("X-UE5-Codex-Token"))
            if not token.allowed:
                json_reply(self, 401, {"error": token.code})
                return
            try:
                payload = json.loads(self.rfile.read(length))
            except json.JSONDecodeError:
                json_reply(self, 400, {"error": "invalid_json"})
                return
            authorized_payload, code = authorize_payload(policy, backend, payload, expected_binding)
            if authorized_payload is None:
                json_reply(self, 403 if code != "invalid_tool_call" else 400, {"error": code})
                return
            request = urllib.request.Request(
                upstream,
                data=json.dumps(authorized_payload).encode("utf-8"),
                method="POST",
                headers={"Content-Type": "application/json", "Accept": "application/json"},
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:
                    data = response.read()
                    content_type = response.headers.get("Content-Type", "application/json")
                    self.send_response(response.status)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
            except urllib.error.HTTPError as error:
                data = error.read()
                self.send_response(error.code)
                self.send_header("Content-Type", error.headers.get("Content-Type", "application/json"))
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except (urllib.error.URLError, TimeoutError) as error:
                json_reply(self, 502, {"error": "UPSTREAM_UNAVAILABLE", "detail": str(error.reason if hasattr(error, "reason") else error)})

    return GuardHandler


def loopback(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--backend", required=True)
    parser.add_argument("--bind", default="127.0.0.1:3100")
    parser.add_argument("--expected-binding", required=True, help="JSON object obtained from current backend discovery")
    args = parser.parse_args()
    try:
        policy = load_policy(args.policy)
        if args.backend not in policy["backends"]:
            raise PolicyError("backend is not configured")
        expected_binding = json.loads(args.expected_binding)
        if not isinstance(expected_binding, dict):
            raise PolicyError("expected-binding must be a JSON object")
        host, raw_port = args.bind.rsplit(":", 1)
        port = int(raw_port)
        if host not in {"127.0.0.1", "localhost", "::1"}:
            raise PolicyError("guard may bind only loopback")
        upstream = policy["backends"][args.backend]["endpoint"]
        if not loopback(upstream):
            raise PolicyError("upstream must be loopback")
    except (PolicyError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    server = ThreadingHTTPServer((host, port), make_handler(policy, args.backend, upstream, expected_binding))
    print(f"MCP guard listening on http://{host}:{port}/mcp for {args.backend}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
