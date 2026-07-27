#!/usr/bin/env python3
"""Default-deny policy used by the UE5 Codex Studio local MCP guard.

This module is deliberately independent of a particular MCP SDK.  Upstream
MCP forks call ``authorize`` before dispatching, while ``run_mcp_guard.py``
uses the same function at an HTTP boundary.  The guard is not a substitute for
binding the upstream server securely: the upstream listener must itself be
private and enforce its capability token.
"""

from __future__ import annotations

import hmac
import os
from dataclasses import dataclass
from typing import Any

import yaml


class PolicyError(ValueError):
    """Raised when a policy cannot be interpreted safely."""


@dataclass(frozen=True)
class Decision:
    allowed: bool
    code: str
    detail: str


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PolicyError(f"{label} must be a mapping")
    return value


def load_policy(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as stream:
            policy = yaml.safe_load(stream)
    except (OSError, yaml.YAMLError) as error:
        raise PolicyError(f"cannot read policy: {error}") from error
    policy = _mapping(policy, "policy")
    if policy.get("schema_version") != 1:
        raise PolicyError("policy schema_version must be 1")
    token = _mapping(policy.get("token"), "token")
    environment = token.get("environment")
    if not isinstance(environment, str) or not environment or environment != environment.strip():
        raise PolicyError("token.environment must be a non-empty environment variable name")
    if token.get("required") is not True:
        raise PolicyError("token.required must be true")
    backends = _mapping(policy.get("backends"), "backends")
    if not backends:
        raise PolicyError("policy needs at least one backend")
    for backend_name, backend_value in backends.items():
        if not isinstance(backend_name, str) or not backend_name:
            raise PolicyError("backend names must be non-empty strings")
        backend = _mapping(backend_value, f"backends.{backend_name}")
        endpoint = backend.get("endpoint")
        if not isinstance(endpoint, str) or not endpoint.startswith("http://127.0.0.1:"):
            raise PolicyError(f"backends.{backend_name}.endpoint must bind loopback")
        if backend.get("require_binding") is not True:
            raise PolicyError(f"backends.{backend_name}.require_binding must be true")
        for key in ("denied_tools", "denied_actions", "routes"):
            if not isinstance(backend.get(key), list):
                raise PolicyError(f"backends.{backend_name}.{key} must be a list")
        if not all(isinstance(item, str) and item for item in backend["denied_tools"] + backend["denied_actions"]):
            raise PolicyError(f"backends.{backend_name} deny entries must be non-empty strings")
        _validate_routes(backend_name, backend)
    return policy


def _validate_routes(backend_name: str, backend: dict[str, Any]) -> None:
    seen: set[tuple[str, str, str, str]] = set()
    for index, value in enumerate(backend["routes"]):
        route = _mapping(value, f"backends.{backend_name}.routes[{index}]")
        required = ("capability_id", "tool", "effect")
        if any(not isinstance(route.get(key), str) or not route[key] for key in required):
            raise PolicyError(f"backends.{backend_name}.routes[{index}] needs capability_id, tool, effect")
        if route["effect"] not in {"READ", "CREATE", "MODIFY", "DELETE", "WRITE", "EXECUTE"}:
            raise PolicyError(f"backends.{backend_name}.routes[{index}].effect is invalid")
        action = route.get("action", "")
        if action is not None and not isinstance(action, str):
            raise PolicyError(f"backends.{backend_name}.routes[{index}].action must be a string")
        skill_name = route.get("skill_name", "")
        backend_tool = route.get("backend_tool", "")
        if not isinstance(skill_name, str) or not isinstance(backend_tool, str):
            raise PolicyError(f"backends.{backend_name}.routes[{index}] identity fields must be strings")
        if backend_name == "blender-mcp" and (not skill_name or not backend_tool):
            raise PolicyError(f"backends.{backend_name}.routes[{index}] needs stable skill_name and backend_tool")
        identity = (route["capability_id"], route["tool"], action or "", backend_tool)
        if identity in seen:
            raise PolicyError(f"backends.{backend_name} contains duplicate route {identity}")
        seen.add(identity)


def token_decision(policy: dict[str, Any], presented: str | None, environment: dict[str, str] | None = None) -> Decision:
    env = os.environ if environment is None else environment
    expected = env.get(policy["token"]["environment"])
    if not expected:
        return Decision(False, "TOKEN_CONFIGURATION_MISSING", "server token is absent; failing closed")
    if not presented or not hmac.compare_digest(expected, presented):
        return Decision(False, "TOKEN_REJECTED", "capability token is missing or invalid")
    return Decision(True, "TOKEN_ACCEPTED", "capability token accepted")


def authorize(policy: dict[str, Any], request: dict[str, Any]) -> Decision:
    """Authorize a resolved action. Unknown fields never relax policy."""
    backend_name = request.get("backend")
    backends = policy["backends"]
    if not isinstance(backend_name, str) or backend_name not in backends:
        return Decision(False, "BACKEND_REJECTED", "backend is absent or not configured")
    backend = backends[backend_name]
    tool = request.get("tool")
    action = request.get("action") or ""
    if not isinstance(tool, str) or not tool:
        return Decision(False, "TOOL_REJECTED", "tool identity is absent")
    if tool in backend["denied_tools"] or action in backend["denied_actions"]:
        return Decision(False, "ACTION_DENIED", "tool or action is explicitly denylisted")
    if backend_name == "blender-mcp" and tool == "call":
        # A raw tool_slug cannot be policy filtered safely. The patched gateway
        # must pass the stable identity supplied by its selected skill manifest.
        if not request.get("skill_name") or not request.get("backend_tool"):
            return Decision(False, "STABLE_IDENTITY_REQUIRED", "Blender call requires skill_name and backend_tool")
    binding = request.get("binding")
    if backend["require_binding"]:
        if not isinstance(binding, dict):
            return Decision(False, "BINDING_REQUIRED", "instance, catalog, and schema binding is required")
        required = ("instance_id", "catalog_generation", "schema_hash")
        if any(not binding.get(key) for key in required):
            return Decision(False, "BINDING_REQUIRED", "binding is incomplete")
        expected = request.get("expected_binding")
        if not isinstance(expected, dict) or any(binding.get(key) != expected.get(key) for key in required):
            return Decision(False, "BINDING_DRIFT", "instance, catalog generation, or schema changed")
    capability_id = request.get("capability_id")
    for route in backend["routes"]:
        if route["capability_id"] != capability_id or route["tool"] != tool:
            continue
        if route.get("action", "") not in ("", action):
            continue
        if backend_name == "blender-mcp" and (
            route.get("skill_name") != request.get("skill_name")
            or route.get("backend_tool") != request.get("backend_tool")
        ):
            continue
        if route["effect"] in {"MODIFY", "DELETE", "WRITE", "EXECUTE"} and not request.get("approval_record"):
            return Decision(False, "APPROVAL_REQUIRED", "editing or deleting an existing asset requires an approval record")
        return Decision(True, "ALLOWED", f"allowed by capability {capability_id}")
    return Decision(False, "ROUTE_REJECTED", "no explicit route authorizes this action")
