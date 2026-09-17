"""3D scene assembly (Item 17, Epoch 4 Phase 4.1).

Joins the geographic products of the elevation branch — a terrain mesh (item 16)
and Z-attributed rivers (item 15) — with artistic/display styling (watershed
materials, cardinal/axis annotations, camera presets, and a display-only
vertical exaggeration) into an immutable :class:`SceneModel`.

The scene deliberately **separates geographic data from styling**: mesh and
river vertices are stored at true 1x meters with immutable source Z; vertical
exaggeration and river lift live in :class:`DisplaySettings` and are applied only
on demand by :func:`render_river_vertices` (never baked into stored geometry).
The model carries no browser/runtime state — it is a pure, deterministic
description that a later GLB/preview stage (Group 6) can serialize.

Pure data composition over the item 15/16 value objects; no GDAL, no shapely, no
browser dependency, so it is fully offline-testable.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, replace

from src.hydro_z import ElevatedLine, render_z
from src.mesh import TerrainMesh

__all__ = [
    "AxisInfo",
    "CameraPreset",
    "CardinalAnnotation",
    "DisplaySettings",
    "Material",
    "RiverFeature",
    "SceneModel",
    "assemble_scene",
    "default_cameras",
    "render_river_vertices",
]

#: Material color used for a river whose segment has no assigned watershed color.
DEFAULT_COLOR = "#808080"

Vec3 = tuple[float, float, float]
SourceVertex = tuple[float, float, float | None]


@dataclass(frozen=True)
class Material:
    """An artistic material (currently a watershed color)."""

    id: str
    color: str


@dataclass(frozen=True)
class RiverFeature:
    """A Z-attributed river in the scene, referencing a shared material.

    ``vertices`` are the *source* (geographic) ``(x, y, z)`` in meters with ``z``
    possibly ``None`` at nodata — never exaggerated. Render Z is computed by
    :func:`render_river_vertices` using the scene's :class:`DisplaySettings`.
    """

    segment_id: int
    vertices: tuple[SourceVertex, ...]
    material_id: str
    dem_id: str
    nodata_count: int


@dataclass(frozen=True)
class CardinalAnnotation:
    """A cardinal-direction label (N/S/E/W) placed at a scene-bounds edge."""

    label: str
    x: float
    y: float
    z: float


@dataclass(frozen=True)
class AxisInfo:
    """Axis extents of the scene in meters (geographic, 1x)."""

    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float


@dataclass(frozen=True)
class CameraPreset:
    """A named camera viewpoint derived from the scene bounds."""

    name: str
    position: Vec3
    target: Vec3
    up: Vec3
    fov_deg: float = 45.0


@dataclass(frozen=True)
class DisplaySettings:
    """Display-only styling applied at render time, never to stored geometry."""

    vertical_exaggeration: float = 1.0
    river_lift: float = 0.0


@dataclass(frozen=True)
class SceneModel:
    """A deterministic, browser-agnostic 3D scene description."""

    terrain: TerrainMesh
    rivers: tuple[RiverFeature, ...]
    materials: tuple[Material, ...]
    cardinals: tuple[CardinalAnnotation, ...]
    axis: AxisInfo
    cameras: tuple[CameraPreset, ...]
    display: DisplaySettings
    crs: str
    scene_hash: str = ""


def assemble_scene(
    *,
    terrain: TerrainMesh,
    rivers: Sequence[ElevatedLine],
    segment_colors: dict[int, str],
    vertical_exaggeration: float = 1.0,
    river_lift: float = 0.0,
    cameras: Sequence[CameraPreset] | None = None,
) -> SceneModel:
    """Compose a :class:`SceneModel` from terrain, rivers, and watershed colors.

    Materials are deduplicated per distinct color (shared across rivers). Cardinal
    annotations and camera presets are derived deterministically from the terrain
    bounds unless ``cameras`` is supplied. Vertical exaggeration and river lift are
    stored as display metadata only.
    """
    rivers = list(rivers)

    colors = [segment_colors.get(r.segment_id, DEFAULT_COLOR) for r in rivers]
    unique = sorted(set(colors))
    color_to_id = {c: f"mat_{i:02d}" for i, c in enumerate(unique)}
    materials = tuple(Material(color_to_id[c], c) for c in unique)

    river_features = tuple(
        RiverFeature(
            segment_id=r.segment_id,
            vertices=tuple((v.x, v.y, v.z) for v in r.vertices),
            material_id=color_to_id[segment_colors.get(r.segment_id, DEFAULT_COLOR)],
            dem_id=r.dem_id,
            nodata_count=r.nodata_count,
        )
        for r in rivers
    )

    axis = _axis_from_terrain(terrain)
    cardinals = _cardinals(axis)
    cams = tuple(cameras) if cameras is not None else default_cameras(axis)
    display = DisplaySettings(
        vertical_exaggeration=float(vertical_exaggeration),
        river_lift=float(river_lift),
    )

    scene = SceneModel(
        terrain=terrain,
        rivers=river_features,
        materials=materials,
        cardinals=cardinals,
        axis=axis,
        cameras=cams,
        display=display,
        crs=terrain.crs,
    )
    return replace(scene, scene_hash=_scene_hash(scene))


def render_river_vertices(
    feature: RiverFeature, display: DisplaySettings
) -> tuple[SourceVertex, ...]:
    """Return ``(x, y, render_z)`` for a river, applying display settings.

    ``render_z = source_z * vertical_exaggeration + river_lift`` (None-safe);
    the feature's stored source Z is left untouched.
    """
    return tuple(
        (
            x,
            y,
            render_z(
                z,
                vertical_exaggeration=display.vertical_exaggeration,
                river_lift=display.river_lift,
            ),
        )
        for x, y, z in feature.vertices
    )


def default_cameras(axis: AxisInfo) -> tuple[CameraPreset, ...]:
    """Derive deterministic top / isometric / south camera presets from bounds."""
    cx = (axis.min_x + axis.max_x) / 2.0
    cy = (axis.min_y + axis.max_y) / 2.0
    cz = (axis.min_z + axis.max_z) / 2.0
    span = max(
        axis.max_x - axis.min_x,
        axis.max_y - axis.min_y,
        axis.max_z - axis.min_z,
        1.0,
    )
    target: Vec3 = (cx, cy, cz)
    return (
        CameraPreset("top", (cx, cy, axis.max_z + span), target, (0.0, 1.0, 0.0)),
        CameraPreset(
            "isometric",
            (axis.max_x + span, axis.min_y - span, axis.max_z + span),
            target,
            (0.0, 0.0, 1.0),
        ),
        CameraPreset(
            "south",
            (cx, axis.min_y - span, cz + span * 0.5),
            target,
            (0.0, 0.0, 1.0),
        ),
    )


def _axis_from_terrain(terrain: TerrainMesh) -> AxisInfo:
    if not terrain.positions:
        raise ValueError("Cannot assemble a scene from an empty terrain mesh.")
    xs = [p[0] for p in terrain.positions]
    ys = [p[1] for p in terrain.positions]
    zs = [p[2] for p in terrain.positions]
    return AxisInfo(min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def _cardinals(axis: AxisInfo) -> tuple[CardinalAnnotation, ...]:
    cx = (axis.min_x + axis.max_x) / 2.0
    cy = (axis.min_y + axis.max_y) / 2.0
    z = axis.min_z  # annotations sit at ground level
    return (
        CardinalAnnotation("N", cx, axis.max_y, z),
        CardinalAnnotation("S", cx, axis.min_y, z),
        CardinalAnnotation("E", axis.max_x, cy, z),
        CardinalAnnotation("W", axis.min_x, cy, z),
    )


def _scene_hash(scene: SceneModel) -> str:
    h = hashlib.sha256()
    h.update(scene.terrain.geometry_hash.encode())
    h.update(b"|mat|")
    for m in scene.materials:
        h.update(f"{m.id},{m.color};".encode())
    h.update(b"|riv|")
    for r in scene.rivers:
        h.update(f"{r.segment_id},{r.material_id},{r.dem_id}:".encode())
        for x, y, z in r.vertices:
            zt = "nan" if z is None else f"{z:.6f}"
            h.update(f"{x:.6f},{y:.6f},{zt};".encode())
    h.update(b"|card|")
    for c in scene.cardinals:
        h.update(f"{c.label},{c.x:.6f},{c.y:.6f},{c.z:.6f};".encode())
    h.update(b"|cam|")
    for cam in scene.cameras:
        h.update(f"{cam.name}:{cam.position}:{cam.target}:{cam.up}:{cam.fov_deg};".encode())
    h.update(
        f"|disp|{scene.display.vertical_exaggeration:.6f},"
        f"{scene.display.river_lift:.6f}|{scene.crs}".encode()
    )
    return h.hexdigest()
