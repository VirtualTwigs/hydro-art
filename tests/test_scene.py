"""Tests for 3D scene assembly (Item 17, Epoch 4 Phase 4.1).

Offline and deterministic. Composes a small terrain mesh (item 16) with a couple
of Z-attributed rivers (item 15) and watershed colors (coloring) into a
``SceneModel``, checking that geographic data (true 1x meters, source Z) stays
separate from display styling (vertical exaggeration, materials, cameras).
"""

from __future__ import annotations

import numpy as np

from src.hydro_z import ElevatedLine, ElevatedVertex
from src.mesh import build_terrain_mesh
from src.raster import GridTransform, RasterGrid
from src.scene import (
    CameraPreset,
    DisplaySettings,
    Material,
    RiverFeature,
    SceneModel,
    assemble_scene,
    render_river_vertices,
)


def _terrain():
    vals = np.array([[0, 1, 2], [1, 2, 3], [2, 3, 4]], dtype=float)  # planar
    g = RasterGrid(vals, GridTransform(0.0, 3.0, 1.0, 1.0), "EPSG:5070", None)
    return build_terrain_mesh(g, error_budget_m=0.01, boundary_id="clark")


def _line(seg, verts):
    vs = tuple(ElevatedVertex(x, y, z) for x, y, z in verts)
    return ElevatedLine(seg, vs, tuple((x, y) for x, y, _ in verts), "dem-1")


def test_assemble_scene_joins_terrain_rivers_materials() -> None:
    t = _terrain()
    r1 = _line(1, [(0.5, 0.5, 10.0), (1.5, 0.5, 8.0)])
    r2 = _line(2, [(2.5, 2.5, 4.0), (2.5, 1.5, 3.0)])
    scene = assemble_scene(
        terrain=t, rivers=[r1, r2], segment_colors={1: "#00ffff", 2: "#ff00ff"}
    )
    assert isinstance(scene, SceneModel)
    assert scene.terrain is t
    assert len(scene.rivers) == 2
    assert all(isinstance(rf, RiverFeature) for rf in scene.rivers)
    assert {m.color for m in scene.materials} == {"#00ffff", "#ff00ff"}
    mids = {m.id for m in scene.materials}
    assert all(rf.material_id in mids for rf in scene.rivers)


def test_materials_deduped_and_shared() -> None:
    t = _terrain()
    r1 = _line(1, [(0.5, 0.5, 10.0)])
    r2 = _line(2, [(2.5, 2.5, 4.0)])
    scene = assemble_scene(
        terrain=t, rivers=[r1, r2], segment_colors={1: "#00ffff", 2: "#00ffff"}
    )
    assert len(scene.materials) == 1
    assert isinstance(scene.materials[0], Material)
    assert scene.rivers[0].material_id == scene.rivers[1].material_id


def test_source_z_preserved_and_exaggeration_display_only() -> None:
    t = _terrain()
    r = _line(1, [(0.5, 0.5, 10.0), (1.5, 0.5, 8.0)])
    scene = assemble_scene(
        terrain=t,
        rivers=[r],
        segment_colors={1: "#00ffff"},
        vertical_exaggeration=3.0,
        river_lift=5.0,
    )
    # Source (geographic) Z is stored at 1x.
    assert [v[2] for v in scene.rivers[0].vertices] == [10.0, 8.0]
    # Terrain positions are unchanged by exaggeration.
    assert scene.terrain.positions == t.positions
    # Render applies exaggeration + lift on demand.
    rv = render_river_vertices(scene.rivers[0], scene.display)
    assert [z for _, _, z in rv] == [35.0, 29.0]


def test_nodata_river_vertex_preserved() -> None:
    t = _terrain()
    r = _line(1, [(0.5, 0.5, 10.0), (1.5, 0.5, None)])
    scene = assemble_scene(
        terrain=t, rivers=[r], segment_colors={1: "#00ffff"}, vertical_exaggeration=2.0
    )
    assert scene.rivers[0].vertices[1][2] is None
    assert scene.rivers[0].nodata_count == 1
    rv = render_river_vertices(scene.rivers[0], scene.display)
    assert rv[1][2] is None


def test_cardinal_annotations_at_bounds_edges() -> None:
    scene = assemble_scene(terrain=_terrain(), rivers=[], segment_colors={})
    assert {c.label for c in scene.cardinals} == {"N", "S", "E", "W"}
    ax = scene.axis
    assert next(c for c in scene.cardinals if c.label == "N").y == ax.max_y
    assert next(c for c in scene.cardinals if c.label == "S").y == ax.min_y
    assert next(c for c in scene.cardinals if c.label == "E").x == ax.max_x
    assert next(c for c in scene.cardinals if c.label == "W").x == ax.min_x


def test_camera_presets_generated_and_deterministic() -> None:
    t = _terrain()
    s1 = assemble_scene(terrain=t, rivers=[], segment_colors={})
    s2 = assemble_scene(terrain=t, rivers=[], segment_colors={})
    assert len(s1.cameras) >= 1
    assert all(isinstance(c, CameraPreset) for c in s1.cameras)
    assert "top" in {c.name for c in s1.cameras}
    assert s1.scene_hash == s2.scene_hash


def test_scene_hash_changes_with_exaggeration_but_geometry_stable() -> None:
    t = _terrain()
    s1 = assemble_scene(terrain=t, rivers=[], segment_colors={}, vertical_exaggeration=1.0)
    s2 = assemble_scene(terrain=t, rivers=[], segment_colors={}, vertical_exaggeration=2.0)
    assert s1.scene_hash != s2.scene_hash
    # The geographic terrain geometry is unaffected by display exaggeration.
    assert s1.terrain.geometry_hash == s2.terrain.geometry_hash


def test_default_display_is_identity() -> None:
    t = _terrain()
    r = _line(1, [(0.5, 0.5, 10.0), (1.5, 0.5, 8.0)])
    scene = assemble_scene(terrain=t, rivers=[r], segment_colors={1: "#00ffff"})
    assert scene.display == DisplaySettings(vertical_exaggeration=1.0, river_lift=0.0)
    rv = render_river_vertices(scene.rivers[0], scene.display)
    assert [z for _, _, z in rv] == [10.0, 8.0]
