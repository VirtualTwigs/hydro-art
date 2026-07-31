"""Tests for reproducible 3D export (Item 19, Epoch 4 Phase 4.3).

Offline and deterministic. Builds a small scene (terrain + one Z-river) and
checks the GLB byte structure, OBJ/MTL text, provenance manifest, and the
injected-writer export path — all without any external glTF/GDAL dependency.
"""

from __future__ import annotations

import json
import struct

import numpy as np

from src.export3d import (
    build_manifest,
    export_scene,
    scene_to_glb,
    scene_to_obj,
)
from src.hydro_z import ElevatedLine, ElevatedVertex
from src.mesh import build_terrain_mesh
from src.raster import GridTransform, RasterGrid
from src.scene import assemble_scene


def _scene(vertical_exaggeration=1.0):
    vals = np.array([[0, 1, 2], [1, 2, 3], [2, 3, 4]], dtype=float)  # planar
    g = RasterGrid(vals, GridTransform(0.0, 3.0, 1.0, 1.0), "EPSG:5070", None)
    terrain = build_terrain_mesh(g, error_budget_m=0.01, boundary_id="clark")
    r = ElevatedLine(
        1,
        (ElevatedVertex(0.5, 0.5, 10.0), ElevatedVertex(1.5, 0.5, 8.0)),
        ((0.5, 0.5), (1.5, 0.5)),
        "dem-1",
    )
    return assemble_scene(
        terrain=terrain,
        rivers=[r],
        segment_colors={1: "#00ffff"},
        vertical_exaggeration=vertical_exaggeration,
    )


def test_glb_has_valid_header_and_chunks() -> None:
    glb = scene_to_glb(_scene())
    magic, version, length = struct.unpack_from("<III", glb, 0)
    assert magic == 0x46546C67  # 'glTF'
    assert version == 2
    assert length == len(glb)
    assert length % 4 == 0
    # First chunk is JSON and parses; declares a mesh.
    clen, ctype = struct.unpack_from("<II", glb, 12)
    assert ctype == 0x4E4F534A  # 'JSON'
    doc = json.loads(glb[20 : 20 + clen])
    assert doc["asset"]["version"] == "2.0"
    assert doc["meshes"] and doc["meshes"][0]["primitives"]


def test_glb_is_deterministic() -> None:
    assert scene_to_glb(_scene()) == scene_to_glb(_scene())


def test_obj_emits_terrain_vertices_and_faces() -> None:
    scene = _scene()
    obj, mtl = scene_to_obj(scene, name="clark")
    vlines = [ln for ln in obj.splitlines() if ln.startswith("v ")]
    flines = [ln for ln in obj.splitlines() if ln.startswith("f ")]
    llines = [ln for ln in obj.splitlines() if ln.startswith("l ")]
    # Terrain (4 corners) + river (2 verts).
    assert len(vlines) == len(scene.terrain.positions) + 2
    assert len(flines) == len(scene.terrain.triangles)
    assert len(llines) == 1  # one river polyline
    assert "mtllib clark.mtl" in obj
    assert "newmtl" in mtl and "#00ffff".lstrip("#") not in mtl  # color as Kd floats


def test_obj_is_deterministic() -> None:
    assert scene_to_obj(_scene(), name="clark") == scene_to_obj(_scene(), name="clark")


def test_manifest_records_hashes_and_settings() -> None:
    scene = _scene(vertical_exaggeration=2.0)
    m = build_manifest(scene)
    assert m["scene_hash"] == scene.scene_hash
    assert m["terrain_geometry_hash"] == scene.terrain.geometry_hash
    assert m["source_raster_hash"] == scene.terrain.source_raster_hash
    assert m["crs"] == "EPSG:5070"
    assert m["vertical_exaggeration"] == 2.0
    assert m["counts"]["terrain_vertices"] == len(scene.terrain.positions)
    assert m["counts"]["terrain_triangles"] == len(scene.terrain.triangles)
    assert m["counts"]["rivers"] == 1
    assert m["formats"] == ["glb", "obj"]
    # Must be JSON-serializable and deterministic.
    assert json.dumps(m, sort_keys=True) == json.dumps(build_manifest(scene), sort_keys=True)


def test_geometry_is_1x_by_default_exaggeration_only_in_manifest() -> None:
    scene = _scene(vertical_exaggeration=5.0)
    obj, _ = scene_to_obj(scene, name="clark")
    # A river vertex keeps its 1x source Z (10.0), not 10*5.
    assert any(ln == "v 0.500000 0.500000 10.000000" for ln in obj.splitlines())
    assert build_manifest(scene)["vertical_exaggeration"] == 5.0


def test_export_scene_writes_all_files_via_injected_writer() -> None:
    written: dict[str, bytes] = {}

    def writer(path: str, data: bytes) -> None:
        written[path] = data

    scene = _scene()
    result = export_scene(scene, out_dir="/out", name="clark", writer=writer)
    assert set(written) == {
        "/out/clark.glb",
        "/out/clark.obj",
        "/out/clark.mtl",
        "/out/clark.manifest.json",
    }
    # Manifest records a sha256 for each emitted asset.
    manifest = json.loads(written["/out/clark.manifest.json"])
    assert set(manifest["assets"]) == {"clark.glb", "clark.obj", "clark.mtl"}
    assert all(len(h) == 64 for h in manifest["assets"].values())
    assert result["glb"] == "/out/clark.glb"


def test_export_scene_is_deterministic() -> None:
    a: dict[str, bytes] = {}
    b: dict[str, bytes] = {}
    export_scene(_scene(), out_dir="/o", name="c", writer=lambda p, d: a.__setitem__(p, d))
    export_scene(_scene(), out_dir="/o", name="c", writer=lambda p, d: b.__setitem__(p, d))
    assert a == b
