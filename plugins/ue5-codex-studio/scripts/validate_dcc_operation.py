#!/usr/bin/env python3
"""Validate a project-local DCC operation against the inactive Blender contract."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path, PurePosixPath

from schema_validation import load_yaml, validate_schema


ACTIONS = {
    "create_mesh": ("dcc.model.create_mesh", "CREATE"),
    "create_sculpt": ("dcc.model.create_sculpt", "CREATE"),
    "import_new_asset": ("dcc.asset.import_new", "CREATE"),
    "edit_existing_mesh": ("dcc.model.modify_existing", "MODIFY"),
    "delete_asset": ("dcc.asset.delete", "DELETE"),
}


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", type=Path)
    parser.add_argument("--capabilities", type=Path, default=Path(__file__).resolve().parents[1] / "catalog/capabilities.yaml")
    args = parser.parse_args()
    try:
        operation = load_yaml(args.operation)
        catalog = load_yaml(args.capabilities)
    except (OSError, ValueError) as error:
        return fail(str(error))
    errors = validate_schema(operation, "dcc-operation.schema.json")
    if errors:
        return fail("; ".join(errors))
    expected_capability, expected_effect = ACTIONS[operation["action"]]
    if operation["capability_id"] != expected_capability or operation["effect"] != expected_effect:
        return fail("DCC action capability or effect does not match the allowlist")
    target = PurePosixPath(operation["target_path"])
    if target.is_absolute() or ".." in target.parts or not target.parts or target.parts[0] != "dcc":
        return fail("target_path must be a project-relative path below dcc/")
    if operation["effect"] in {"MODIFY", "DELETE"} and not operation.get("approval_record"):
        return fail("DCC modify and delete operations require an explicit approval record")
    capabilities = {item.get("id"): item for item in catalog.get("capabilities", []) if isinstance(item, dict)}
    capability = capabilities.get(expected_capability)
    if capability is None:
        return fail("operation references an unknown capability")
    if capability.get("availability") in {"BLOCKED", "UNSUPPORTED"} and operation["status"] != "BLOCKED":
        return fail("unavailable DCC capability must remain BLOCKED")
    print(f"PASS: {operation['id']} is a bounded {operation['status']} DCC operation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
