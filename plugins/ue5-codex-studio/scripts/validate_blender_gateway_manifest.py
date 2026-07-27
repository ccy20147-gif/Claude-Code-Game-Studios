#!/usr/bin/env python3
"""Check whether a Blender gateway manifest is safe to provision."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import yaml


SHA256 = re.compile(r"[0-9a-f]{64}$")


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    try:
        value = yaml.safe_load(args.manifest.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise ValueError("manifest schema_version must be 1")
        gateway = value.get("gateway")
        tools = value.get("tools")
        if not isinstance(gateway, dict) or not isinstance(tools, list) or not tools:
            raise ValueError("manifest needs gateway and tools")
        parsed = urlparse(gateway.get("endpoint", ""))
        if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or parsed.port is None:
            raise ValueError("gateway endpoint must be HTTP loopback")
        identities = set()
        for tool in tools:
            if not isinstance(tool, dict) or tool.get("effect") not in {"CREATE", "MODIFY", "DELETE"}:
                raise ValueError("tools need a supported effect")
            identity = (tool.get("skill_name"), tool.get("backend_tool"), tool.get("action"))
            if not all(isinstance(part, str) and part for part in identity) or identity in identities:
                raise ValueError("tools need unique stable identities")
            identities.add(identity)
        ready = all(isinstance(gateway.get(field), str) and SHA256.fullmatch(gateway[field]) for field in ("adapter_sha256", "core_sha256", "protocol_schema_sha256")) and gateway.get("canary") == "PASS"
        if args.require_ready and not ready:
            raise ValueError("gateway is not provisionable: hashes and a passing DCC canary are required")
        print(f"PASS: Blender gateway manifest is {'READY' if ready else 'PENDING'} ({len(identities)} stable tools)")
        return 0
    except (OSError, ValueError, yaml.YAMLError) as error:
        return fail(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
