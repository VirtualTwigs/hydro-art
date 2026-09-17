"""Reproducible 3D export: GLB + OBJ + provenance manifest (Item 19, Phase 4.3).

Serializes a :class:`~src.scene.SceneModel` (item 17) into portable 3D assets:

- :func:`scene_to_glb` writes a binary glTF (``.glb``) with a **pure-stdlib,
  deterministic** writer — terrain as a ``TRIANGLES`` primitive, each river run as
  a ``LINE_STRIP``, with per-watershed PBR materials. No external glTF library, so
  the exact bytes are reproducible and unit-testable offline.
- :func:`scene_to_obj` writes a plain-text OBJ + MTL pair for broad importability.
- :func:`build_manifest` emits a JSON provenance manifest with source/raster/
  geometry/scene hashes, settings, and per-asset content hashes.
- :func:`export_scene` bundles all four files through an injected ``writer`` seam
  (defaulting to disk) so callers/tests control I/O.

Geometry is exported at **true 1× meters** by default (geographic truth); vertical
exaggeration is recorded in the manifest, not baked in, unless
``apply_exaggeration=True`` is requested for a display-oriented asset. Resolved
decision #4: GLB + OBJ this epoch; terrain GeoTIFF deferred.
"""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Callable, Sequence
from pathlib import Path

from src.scene import SceneModel

__all__ = [
    "build_manifest",
    "export_scene",
    "scene_to_glb",
    "scene_to_obj",
]

Writer = Callable[[str, bytes], None]

Vec3 = tuple[float, float, float]

# glTF constants
_ARRAY_BUFFER = 34962
_ELEMENT_ARRAY_BUFFER = 34963
_FLOAT = 5126
_UNSIGNED_INT = 5125
_MODE_TRIANGLES = 4
_MODE_LINE_STRIP = 3

# GLB chunk magics
_GLB_MAGIC = 0x46546C67  # 'glTF'
_JSON_MAGIC = 0x4E4F534A  # 'JSON'
_BIN_MAGIC = 0x004E4942  # 'BIN\0'

_TERRAIN_COLOR = (0.5, 0.5, 0.5)


def _hex_to_rgb(color: str) -> Vec3:
    h = color.lstrip("#")
    return (int(h[0:2], 16) / 255.0, int(h[2:4], 16) / 255.0, int(h[4:6], 16) / 255.0)


def _terrain_verts(scene: SceneModel, apply: bool) -> list[Vec3]:
    ve = scene.display.vertical_exaggeration
    if apply:
        return [(x, y, z * ve) for x, y, z in scene.terrain.positions]
    return [(x, y, z) for x, y, z in scene.terrain.positions]


def _river_runs(scene: SceneModel, apply: bool) -> list[tuple[str, list[Vec3]]]:
    """Split each river into maximal runs of valid (non-nodata) vertices."""
    ve = scene.display.vertical_exaggeration
    lift = scene.display.river_lift
    runs: list[tuple[str, list[Vec3]]] = []
    for rf in scene.rivers:
        cur: list[Vec3] = []
        for x, y, z in rf.vertices:
            if z is None:
                if len(cur) >= 2:
                    runs.append((rf.material_id, cur))
                cur = []
                continue
            cur.append((x, y, z * ve + lift if apply else z))
        if len(cur) >= 2:
            runs.append((rf.material_id, cur))
    return runs


def scene_to_glb(scene: SceneModel, *, apply_exaggeration: bool = False) -> bytes:
    """Serialize ``scene`` to deterministic binary glTF (GLB) bytes."""
    materials = [
        {
            "name": "terrain",
            "pbrMetallicRoughness": {
                "baseColorFactor": [*_TERRAIN_COLOR, 1.0],
                "metallicFactor": 0.0,
                "roughnessFactor": 1.0,
            },
        }
    ]
    mat_index: dict[str, int] = {}
    for m in scene.materials:
        mat_index[m.id] = len(materials)
        materials.append(
            {
                "name": m.id,
                "pbrMetallicRoughness": {
                    "baseColorFactor": [*_hex_to_rgb(m.color), 1.0],
                    "metallicFactor": 0.0,
                    "roughnessFactor": 1.0,
                },
            }
        )

    bin_parts: list[bytes] = []
    buffer_views: list[dict] = []
    accessors: list[dict] = []
    offset = 0

    def add_view(data: bytes, target: int) -> int:
        nonlocal offset
        pad = (-offset) % 4
        if pad:
            bin_parts.append(b"\x00" * pad)
            offset += pad
        idx = len(buffer_views)
        buffer_views.append(
            {"buffer": 0, "byteOffset": offset, "byteLength": len(data), "target": target}
        )
        bin_parts.append(data)
        offset += len(data)
        return idx

    def add_positions(verts: Sequence[Vec3]) -> int:
        flat: list[float] = [c for v in verts for c in v]
        view = add_view(struct.pack(f"<{len(flat)}f", *flat), _ARRAY_BUFFER)
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        zs = [v[2] for v in verts]
        accessors.append(
            {
                "bufferView": view,
                "componentType": _FLOAT,
                "count": len(verts),
                "type": "VEC3",
                "min": [min(xs), min(ys), min(zs)],
                "max": [max(xs), max(ys), max(zs)],
            }
        )
        return len(accessors) - 1

    def add_indices(indices: Sequence[int]) -> int:
        view = add_view(
            struct.pack(f"<{len(indices)}I", *indices), _ELEMENT_ARRAY_BUFFER
        )
        accessors.append(
            {
                "bufferView": view,
                "componentType": _UNSIGNED_INT,
                "count": len(indices),
                "type": "SCALAR",
            }
        )
        return len(accessors) - 1

    primitives: list[dict] = []
    tverts = _terrain_verts(scene, apply_exaggeration)
    if tverts and scene.terrain.triangles:
        pos = add_positions(tverts)
        idx = add_indices([i for tri in scene.terrain.triangles for i in tri])
        primitives.append(
            {"attributes": {"POSITION": pos}, "indices": idx, "mode": _MODE_TRIANGLES,
             "material": 0}
        )
    for material_id, run in _river_runs(scene, apply_exaggeration):
        pos = add_positions(run)
        primitives.append(
            {"attributes": {"POSITION": pos}, "mode": _MODE_LINE_STRIP,
             "material": mat_index[material_id]}
        )

    bin_bytes = b"".join(bin_parts)
    doc = {
        "asset": {"version": "2.0", "generator": "hydro-art"},
        "buffers": [{"byteLength": len(bin_bytes)}],
        "bufferViews": buffer_views,
        "accessors": accessors,
        "materials": materials,
        "meshes": [{"primitives": primitives}],
        "nodes": [{"mesh": 0}],
        "scenes": [{"nodes": [0]}],
        "scene": 0,
    }
    return _pack_glb(doc, bin_bytes)


def _pack_glb(doc: dict, bin_bytes: bytes) -> bytes:
    json_bytes = json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
    json_chunk = json_bytes + b" " * ((-len(json_bytes)) % 4)
    bin_chunk = bin_bytes + b"\x00" * ((-len(bin_bytes)) % 4)
    total = 12 + 8 + len(json_chunk) + 8 + len(bin_chunk)
    out = bytearray()
    out += struct.pack("<III", _GLB_MAGIC, 2, total)
    out += struct.pack("<II", len(json_chunk), _JSON_MAGIC) + json_chunk
    out += struct.pack("<II", len(bin_chunk), _BIN_MAGIC) + bin_chunk
    return bytes(out)


def scene_to_obj(
    scene: SceneModel, *, name: str, apply_exaggeration: bool = False
) -> tuple[str, str]:
    """Serialize ``scene`` to a deterministic OBJ + MTL text pair."""
    obj = [f"# hydro-art 3D export: {scene.terrain.boundary_id}", f"mtllib {name}.mtl"]
    obj.append("o terrain")
    obj.append("usemtl terrain")
    tverts = _terrain_verts(scene, apply_exaggeration)
    for x, y, z in tverts:
        obj.append(f"v {x:.6f} {y:.6f} {z:.6f}")
    for tri in scene.terrain.triangles:
        obj.append("f {} {} {}".format(*(i + 1 for i in tri)))

    voff = len(tverts)
    for ri, (material_id, run) in enumerate(_river_runs(scene, apply_exaggeration)):
        obj.append(f"o river_{ri}")
        obj.append(f"usemtl {material_id}")
        for x, y, z in run:
            obj.append(f"v {x:.6f} {y:.6f} {z:.6f}")
        obj.append("l " + " ".join(str(voff + 1 + k) for k in range(len(run))))
        voff += len(run)
    obj_str = "\n".join(obj) + "\n"

    mtl = ["# hydro-art materials", "newmtl terrain",
           "Kd {:.6f} {:.6f} {:.6f}".format(*_TERRAIN_COLOR), ""]
    for m in scene.materials:
        mtl += [f"newmtl {m.id}", "Kd {:.6f} {:.6f} {:.6f}".format(*_hex_to_rgb(m.color)), ""]
    return obj_str, "\n".join(mtl) + "\n"


def build_manifest(
    scene: SceneModel,
    *,
    formats: Sequence[str] = ("glb", "obj"),
    assets: dict[str, str] | None = None,
) -> dict:
    """Build the JSON-serializable provenance manifest for ``scene``."""
    manifest = {
        "generator": "hydro-art",
        "boundary_id": scene.terrain.boundary_id,
        "crs": scene.crs,
        "lod": scene.terrain.lod,
        "error_budget_m": scene.terrain.error_budget_m,
        "max_error_m": scene.terrain.max_error_m,
        "vertical_exaggeration": scene.display.vertical_exaggeration,
        "river_lift": scene.display.river_lift,
        "vertical_units": scene.terrain.vertical_units,
        "scene_hash": scene.scene_hash,
        "terrain_geometry_hash": scene.terrain.geometry_hash,
        "source_raster_hash": scene.terrain.source_raster_hash,
        "formats": list(formats),
        "materials": [{"id": m.id, "color": m.color} for m in scene.materials],
        "cameras": [c.name for c in scene.cameras],
        "counts": {
            "terrain_vertices": len(scene.terrain.positions),
            "terrain_triangles": len(scene.terrain.triangles),
            "rivers": len(scene.rivers),
            "river_vertices": sum(len(r.vertices) for r in scene.rivers),
        },
    }
    if assets is not None:
        manifest["assets"] = assets
    return manifest


def _disk_writer(path: str, data: bytes) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)


def export_scene(
    scene: SceneModel,
    *,
    out_dir: str,
    name: str,
    writer: Writer | None = None,
    apply_exaggeration: bool = False,
) -> dict[str, str]:
    """Write ``name``.{glb,obj,mtl,manifest.json} for ``scene`` via ``writer``.

    Returns a mapping of asset kind -> written path. The manifest records a
    SHA-256 for each geometry asset, so the same scene yields identical files.
    """
    write = writer or _disk_writer
    glb = scene_to_glb(scene, apply_exaggeration=apply_exaggeration)
    obj_str, mtl_str = scene_to_obj(scene, name=name, apply_exaggeration=apply_exaggeration)
    obj_b, mtl_b = obj_str.encode("utf-8"), mtl_str.encode("utf-8")

    assets = {
        f"{name}.glb": hashlib.sha256(glb).hexdigest(),
        f"{name}.obj": hashlib.sha256(obj_b).hexdigest(),
        f"{name}.mtl": hashlib.sha256(mtl_b).hexdigest(),
    }
    manifest_b = json.dumps(
        build_manifest(scene, assets=assets), sort_keys=True, indent=2
    ).encode("utf-8")

    paths = {
        "glb": f"{out_dir}/{name}.glb",
        "obj": f"{out_dir}/{name}.obj",
        "mtl": f"{out_dir}/{name}.mtl",
        "manifest": f"{out_dir}/{name}.manifest.json",
    }
    write(paths["glb"], glb)
    write(paths["obj"], obj_b)
    write(paths["mtl"], mtl_b)
    write(paths["manifest"], manifest_b)
    return paths
