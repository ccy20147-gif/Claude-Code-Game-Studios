#!/usr/bin/env python3
"""Validate a bounded Blueprint operation while automation remains fail-closed."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from schema_validation import load_yaml, validate_schema


ACTIONS = {
    "create_from_template": ("ue.blueprint.create_from_template", "template_id"),
    "add_allowlisted_component": ("ue.blueprint.add_allowlisted_component", "component_class"),
    "set_allowlisted_variable": ("ue.blueprint.set_allowlisted_variable", "variable"),
    "apply_allowlisted_graph_patch": ("ue.blueprint.apply_allowlisted_graph_patch", "graph_patch_id"),
    "compile": ("ue.blueprint.compile", None),
    "save_reload_readback": ("ue.blueprint.save_reload_readback", None),
}
TEMPLATES = {"bp_template_actor", "bp_template_character", "bp_template_interactable", "bp_template_widget"}
COMPONENTS = {"AudioComponent", "BoxComponent", "PointLightComponent", "SceneComponent", "StaticMeshComponent"}
VARIABLE_TYPES = {"bool", "float", "int32", "name", "text", "vector"}
GRAPH_PATCHES = {"graph_patch_begin_play", "graph_patch_interact", "graph_patch_widget_confirm"}


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
    errors = validate_schema(operation, "blueprint-operation.schema.json")
    if errors:
        return fail("; ".join(errors))
    action = operation["action"]
    capability_id, detail_field = ACTIONS[action]
    if operation["capability_id"] != capability_id:
        return fail(f"{action} must use capability {capability_id}")
    if detail_field and not operation.get(detail_field):
        return fail(f"{action} requires {detail_field}")
    if action == "create_from_template" and operation["template_id"] not in TEMPLATES:
        return fail("template_id is not allowlisted")
    if action == "add_allowlisted_component" and operation["component_class"] not in COMPONENTS:
        return fail("component_class is not allowlisted")
    if action == "set_allowlisted_variable" and operation["variable"]["type"] not in VARIABLE_TYPES:
        return fail("variable type is not allowlisted")
    if action == "apply_allowlisted_graph_patch":
        if operation["graph_patch_id"] not in GRAPH_PATCHES:
            return fail("graph_patch_id is not allowlisted")
        if not operation.get("approval_record"):
            return fail("graph patches require an explicit approval record")
    capabilities = {item.get("id"): item for item in catalog.get("capabilities", []) if isinstance(item, dict)}
    capability = capabilities.get(capability_id)
    if capability is None:
        return fail("operation references an unknown capability")
    if capability.get("availability") in {"BLOCKED", "UNSUPPORTED"} and operation["status"] != "BLOCKED":
        return fail("unavailable Blueprint capability must remain BLOCKED")
    print(f"PASS: {operation['id']} is a bounded {operation['status']} Blueprint operation")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
