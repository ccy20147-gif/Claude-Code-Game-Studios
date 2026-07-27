#!/usr/bin/env python3
"""Static, offline validation for game-ready glTF 2.0 mesh exports.

This validates structural requirements only. It cannot replace Blender checks
for non-manifold topology, exact UV-island overlap, skin deformation, baking,
or visual LOD quality.
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


LOD_NAME = re.compile(r"(?:^|[_-])lod(\d+)$", re.IGNORECASE)
INDEX_COMPONENTS = {5121, 5123, 5125}


def fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def read_document(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".gltf":
        value = json.loads(path.read_text(encoding="utf-8"))
    elif path.suffix.lower() == ".glb":
        raw = path.read_bytes()
        if len(raw) < 20 or raw[:4] != b"glTF":
            raise ValueError("invalid GLB header")
        _, version, length = struct.unpack_from("<III", raw, 0)
        if version != 2 or length != len(raw):
            raise ValueError("GLB must be version 2 with matching length")
        chunk_length, chunk_type = struct.unpack_from("<II", raw, 12)
        if chunk_type != 0x4E4F534A or 20 + chunk_length > len(raw):
            raise ValueError("GLB must start with a JSON chunk")
        value = json.loads(raw[20:20 + chunk_length].decode("utf-8").rstrip(" \t\r\n\0"))
    else:
        raise ValueError("asset must be .gltf or .glb")
    if not isinstance(value, dict) or value.get("asset", {}).get("version") != "2.0":
        raise ValueError("asset must be glTF 2.0")
    return value


def accessor_count(accessors: list[Any], index: object, label: str) -> int:
    if not isinstance(index, int) or not 0 <= index < len(accessors) or not isinstance(accessors[index], dict):
        raise ValueError(f"{label} references an invalid accessor")
    count = accessors[index].get("count")
    if not isinstance(count, int) or count < 1:
        raise ValueError(f"{label} accessor has invalid count")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asset", type=Path)
    parser.add_argument("--max-lod0-triangles", type=int, default=100_000)
    parser.add_argument("--max-other-lod-triangles", type=int, default=50_000)
    parser.add_argument("--require-lods", type=int, default=1)
    parser.add_argument("--require-uv1", action="store_true")
    args = parser.parse_args()
    try:
        if args.require_lods < 1 or args.max_lod0_triangles < 1 or args.max_other_lod_triangles < 1:
            raise ValueError("LOD and triangle limits must be positive")
        document = read_document(args.asset)
        meshes = document.get("meshes")
        accessors = document.get("accessors", [])
        if not isinstance(meshes, list) or not meshes or not isinstance(accessors, list):
            raise ValueError("glTF needs meshes and accessors")
        lods: dict[str, list[tuple[int, int]]] = defaultdict(list)
        total_triangles = 0
        for mesh_index, mesh in enumerate(meshes):
            if not isinstance(mesh, dict) or not isinstance(mesh.get("name"), str):
                raise ValueError(f"mesh[{mesh_index}] needs a named mesh")
            match = LOD_NAME.search(mesh["name"])
            if not match:
                raise ValueError(f"mesh {mesh['name']} must end in _LOD0, _LOD1, and so on")
            lod_index = int(match.group(1))
            base_name = mesh["name"][:match.start()]
            primitives = mesh.get("primitives")
            if not isinstance(primitives, list) or not primitives:
                raise ValueError(f"mesh {mesh['name']} has no primitives")
            triangles = 0
            for primitive_index, primitive in enumerate(primitives):
                if not isinstance(primitive, dict) or primitive.get("mode", 4) != 4:
                    raise ValueError(f"{mesh['name']} primitive {primitive_index} must be triangles")
                attributes = primitive.get("attributes")
                if not isinstance(attributes, dict) or not {"POSITION", "NORMAL", "TEXCOORD_0"} <= set(attributes):
                    raise ValueError(f"{mesh['name']} primitive {primitive_index} needs POSITION, NORMAL, TEXCOORD_0")
                if args.require_uv1 and "TEXCOORD_1" not in attributes:
                    raise ValueError(f"{mesh['name']} primitive {primitive_index} needs TEXCOORD_1")
                vertex_count = accessor_count(accessors, attributes["POSITION"], f"{mesh['name']}.POSITION")
                if accessor_count(accessors, attributes["NORMAL"], f"{mesh['name']}.NORMAL") != vertex_count:
                    raise ValueError(f"{mesh['name']} has mismatched normal count")
                if accessor_count(accessors, attributes["TEXCOORD_0"], f"{mesh['name']}.TEXCOORD_0") != vertex_count:
                    raise ValueError(f"{mesh['name']} has mismatched UV0 count")
                if "TEXCOORD_1" in attributes and accessor_count(accessors, attributes["TEXCOORD_1"], f"{mesh['name']}.TEXCOORD_1") != vertex_count:
                    raise ValueError(f"{mesh['name']} has mismatched UV1 count")
                index = primitive.get("indices")
                count = accessor_count(accessors, index, f"{mesh['name']}.indices")
                if accessors[index].get("componentType") not in INDEX_COMPONENTS or count % 3:
                    raise ValueError(f"{mesh['name']} must use triangular unsigned indices")
                triangles += count // 3
            limit = args.max_lod0_triangles if lod_index == 0 else args.max_other_lod_triangles
            if triangles > limit:
                raise ValueError(f"{mesh['name']} has {triangles} triangles, exceeds budget {limit}")
            lods[base_name].append((lod_index, triangles))
            total_triangles += triangles
        for base, entries in lods.items():
            entries.sort()
            actual = [index for index, _ in entries]
            expected = list(range(args.require_lods))
            if actual != expected:
                raise ValueError(f"{base} LOD set is {actual}, expected {expected}")
            if any(entries[index][1] >= entries[index - 1][1] for index in range(1, len(entries))):
                raise ValueError(f"{base} LOD triangle counts must strictly decrease")
        print(f"PASS: {args.asset.name}; {len(meshes)} mesh LODs; {total_triangles} triangles")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as error:
        return fail(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
