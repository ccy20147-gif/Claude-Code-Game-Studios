#!/usr/bin/env python3
"""Validate that a generated glTF/GLB is a parseable coarse-mesh candidate."""

from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path
from typing import Any


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def document(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".gltf":
        value = json.loads(path.read_text(encoding="utf-8"))
    elif path.suffix.lower() == ".glb":
        raw = path.read_bytes()
        if len(raw) < 20 or raw[:4] != b"glTF":
            raise ValueError("invalid GLB header")
        _, version, length = struct.unpack_from("<III", raw, 0)
        chunk_length, chunk_type = struct.unpack_from("<II", raw, 12)
        if version != 2 or length != len(raw) or chunk_type != 0x4E4F534A or 20 + chunk_length > len(raw):
            raise ValueError("GLB must be version 2 with a valid JSON chunk")
        value = json.loads(raw[20:20 + chunk_length].decode("utf-8").rstrip(" \t\r\n\0"))
    else:
        raise ValueError("coarse mesh validation supports .gltf and .glb")
    if not isinstance(value, dict) or value.get("asset", {}).get("version") != "2.0":
        raise ValueError("asset must be glTF 2.0")
    return value


def count(accessors: list[Any], index: object, label: str) -> int:
    if not isinstance(index, int) or not 0 <= index < len(accessors) or not isinstance(accessors[index], dict):
        raise ValueError(f"{label} references an invalid accessor")
    value = accessors[index].get("count")
    if not isinstance(value, int) or value < 3:
        raise ValueError(f"{label} accessor count is invalid")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asset", type=Path)
    parser.add_argument("--max-triangles", type=int, default=1_500_000)
    args = parser.parse_args()
    try:
        if args.max_triangles < 1:
            raise ValueError("max triangles must be positive")
        value = document(args.asset)
        meshes = value.get("meshes")
        accessors = value.get("accessors")
        if not isinstance(meshes, list) or not meshes or not isinstance(accessors, list):
            raise ValueError("generated mesh needs meshes and accessors")
        triangles = 0
        primitives_seen = 0
        for mesh_index, mesh in enumerate(meshes):
            if not isinstance(mesh, dict) or not isinstance(mesh.get("primitives"), list) or not mesh["primitives"]:
                raise ValueError(f"mesh[{mesh_index}] has no primitives")
            for primitive_index, primitive in enumerate(mesh["primitives"]):
                if not isinstance(primitive, dict) or primitive.get("mode", 4) != 4:
                    raise ValueError(f"mesh[{mesh_index}] primitive[{primitive_index}] must use triangles")
                attributes = primitive.get("attributes")
                if not isinstance(attributes, dict) or "POSITION" not in attributes:
                    raise ValueError(f"mesh[{mesh_index}] primitive[{primitive_index}] needs POSITION")
                vertices = count(accessors, attributes["POSITION"], "POSITION")
                indices = primitive.get("indices")
                triangle_count = count(accessors, indices, "indices") // 3 if indices is not None else vertices // 3
                if triangle_count < 1:
                    raise ValueError("generated primitive contains no triangles")
                triangles += triangle_count
                primitives_seen += 1
        if triangles > args.max_triangles:
            raise ValueError(f"generated mesh has {triangles} triangles, exceeds {args.max_triangles}")
        print(f"PASS: coarse mesh parses ({len(meshes)} meshes, {primitives_seen} primitives, {triangles} triangles); PENDING_LOCAL_VALIDATION")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, UnicodeDecodeError, struct.error) as error:
        return fail(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
