#!/usr/bin/env python3
"""Run the non-destructive portion of the real-editor UE5UltimateMCP canary.

The caller must open the dedicated canary map first. Saving and reloading is
performed by the Windows UE fixture harness (not by an MCP write tool) and is
supplied as a small evidence JSON document. This keeps save/reload out of the
first public MCP allowlist.
"""

from __future__ import annotations

import argparse
import json
import secrets
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


def request(endpoint: str, token: str, path: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    value = urllib.request.Request(endpoint + path, data=data, headers={"X-UE5-Codex-Token": token, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(value, timeout=45) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as error:
        raise RuntimeError(f"{path} failed: {error}") from error
    if path == "/api/tool" and result.get("success") is not True:
        raise RuntimeError(f"{payload.get('tool')} failed: {result.get('error', 'unknown error')}")
    return result.get("result", result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--canary-map", required=True)
    parser.add_argument("--save-reload-evidence", type=Path, required=True)
    parser.add_argument("--stop-service", action="store_true")
    args = parser.parse_args()
    try:
        state = json.loads(args.state_file.read_text(encoding="utf-8"))
        endpoint = state["endpoint"].rstrip("/")
        parsed = urlparse(endpoint)
        if parsed.hostname != "127.0.0.1" or state["catalog"]["status"] != "APPROVED":
            raise RuntimeError("state is not an approved loopback integration")
        if not args.canary_map.startswith("/Game/__CodexCanary_"):
            raise RuntimeError("canary map must use the /Game/__CodexCanary_ prefix")
        health = request(endpoint, state["token"], "/api/health")
        tools = request(endpoint, state["token"], "/api/tools")
        if not isinstance(tools.get("tools"), list):
            raise RuntimeError("tool discovery is invalid")
        level = request(endpoint, state["token"], "/api/tool", {"tool": "get_level_info"})
        if level.get("map_name") not in (args.canary_map, args.canary_map.rsplit("/", 1)[-1]):
            raise RuntimeError("dedicated canary map is not active")
        name = "__CodexCanary_" + secrets.token_hex(8)
        created = request(endpoint, state["token"], "/api/tool", {"tool": "spawn_actor", "name": name, "type": "PointLight"})
        readback = request(endpoint, state["token"], "/api/tool", {"tool": "find_actors_by_name", "pattern": name})
        if int(readback.get("count", 0)) != 1:
            raise RuntimeError("created canary actor did not survive independent readback")
        screenshot = request(endpoint, state["token"], "/api/tool", {"tool": "capture_viewport", "width": 640, "height": 360})
        saved = json.loads(args.save_reload_evidence.read_text(encoding="utf-8"))
        if saved.get("map") != args.canary_map or saved.get("saved") is not True or saved.get("reloaded") is not True:
            raise RuntimeError("fixture save/reload evidence is incomplete")
        request(endpoint, state["token"], "/api/tool", {"tool": "delete_actor", "name": name})
        deleted = request(endpoint, state["token"], "/api/tool", {"tool": "find_actors_by_name", "pattern": name})
        if int(deleted.get("count", 0)) != 0:
            raise RuntimeError("deleted canary actor still appears in independent readback")
        logs = request(endpoint, state["token"], "/api/tool", {"tool": "get_output_log", "lines": 200})
        if "[UltimateMCP] Error" in json.dumps(logs):
            raise RuntimeError("UE output log contains an UltimateMCP error")
        if args.stop_service:
            request(endpoint, state["token"], "/api/shutdown", {})
        state["canary"] = {"status": "PASS", "map": args.canary_map, "actor": name, "health": health, "tool_count": len(tools["tools"]), "screenshot_captured": bool(screenshot), "save_reload_evidence": str(args.save_reload_evidence), "service_stopped": args.stop_service}
        args.state_file.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, KeyError, TypeError, ValueError, RuntimeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PASS: authenticated UE5UltimateMCP canary completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
