"""Adaptive terrain mesh from a normalized DEM (Item 16, Epoch 3 Phase 3.3).

Turns a normalized DEM raster (item 13) into a deterministic, error-bounded
triangle mesh with true 1x physical coordinates in meters. Vertical
exaggeration is *display-only* and is never baked into these positions.

The mesh is a greedy TIN (Garland-Heckbert style incremental refinement): it
seeds two triangles over the grid corners and repeatedly inserts the DEM sample
whose vertical deviation from the current mesh surface is largest, stopping once
every sample is within ``error_budget_m`` (or an optional ``max_points`` cap is
hit). This spends triangles only where terrain is rugged while keeping a stated,
auditable vertical-accuracy guarantee (resolved decision #3). Point insertion is
a fan retriangulation of the containing triangle(s) with zero-area fans dropped,
so the result is crack-free even when a sample lands on a shared edge.

``numpy`` is imported directly (consistent with ``raster``/``terrain``); no GDAL
or shapely is needed, so this module and its tests run fully offline on tiny
synthetic grids. Rivers get their z-fighting ``river_lift`` at render time
(``src.hydro_z.render_z``); no artificial terrain is introduced here.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from src.crs import INTERNAL_CRS
from src.raster import NormalizedDem, RasterGrid

__all__ = [
    "TerrainMesh",
    "build_terrain_mesh",
    "mesh_from_dem",
]

Vertex = tuple[float, float, float]
Triangle = tuple[int, int, int]

_EPS = 1e-9


@dataclass(frozen=True)
class TerrainMesh:
    """A deterministic, error-bounded terrain mesh in true meters.

    Attributes:
        positions: ``(x, y, z)`` vertices in EPSG:5070 meters at 1x scale.
        triangles: Vertex-index triples (CCW not guaranteed; render two-sided).
        boundary_id: Identity of the clip boundary this mesh represents.
        lod: Pyramid level the mesh was built from (0 = finest).
        error_budget_m: Requested max vertical deviation from the DEM samples.
        max_error_m: Achieved max vertical deviation over all valid samples.
        crs: Horizontal CRS of ``positions``.
        vertical_units: Units of z (verbatim from the source DEM).
        source_raster_hash: Hash of the grid the mesh was built from.
        geometry_hash: Deterministic hash of positions + triangles.
    """

    positions: tuple[Vertex, ...]
    triangles: tuple[Triangle, ...]
    boundary_id: str
    lod: int
    error_budget_m: float
    max_error_m: float
    crs: str = INTERNAL_CRS
    vertical_units: str | None = None
    source_raster_hash: str = ""
    geometry_hash: str = field(default="")


def _cell_center(grid: RasterGrid, r: int, c: int) -> tuple[float, float]:
    t = grid.transform
    return (t.origin_x + (c + 0.5) * t.pixel_width,
            t.origin_y - (r + 0.5) * t.pixel_height)


def _bary(tri: tuple[Vertex, Vertex, Vertex], px: float, py: float):
    """Barycentric coords of (px, py) in triangle ``tri`` (xy only)."""
    (ax, ay, _), (bx, by, _), (cx, cy, _) = tri
    det = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(det) < 1e-12:
        return None
    a = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / det
    b = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / det
    return a, b, 1.0 - a - b


def _interp_z(tri: tuple[Vertex, Vertex, Vertex], bary) -> float:
    a, b, c = bary
    return a * tri[0][2] + b * tri[1][2] + c * tri[2][2]


def _nearest_valid(mask: np.ndarray, r: int, c: int) -> tuple[int, int]:
    """Nearest valid (Manhattan, deterministic) grid index to (r, c)."""
    if mask[r, c]:
        return (r, c)
    rows, cols = np.nonzero(mask)
    dist = np.abs(rows - r) + np.abs(cols - c)
    order = np.lexsort((cols, rows, dist))  # by distance, then row, then col
    i = order[0]
    return (int(rows[i]), int(cols[i]))


def build_terrain_mesh(
    grid: RasterGrid,
    *,
    error_budget_m: float,
    boundary_id: str,
    max_points: int | None = None,
    lod: int = 0,
) -> TerrainMesh:
    """Build an error-bounded TIN over ``grid``.

    Refines until every valid DEM sample is within ``error_budget_m`` of the
    mesh surface, or ``max_points`` vertices have been placed. Triangles whose
    footprint contains a nodata sample are dropped. Positions are true meters at
    1x scale (no vertical exaggeration).

    Raises:
        ValueError: If ``error_budget_m`` < 0 or fewer than three valid corners.
    """
    if error_budget_m < 0:
        raise ValueError(f"error_budget_m must be >= 0, got {error_budget_m}.")

    values = np.asarray(grid.values, dtype=float)
    if grid.nodata is not None:
        valid = values != grid.nodata
    else:
        valid = np.ones(values.shape, dtype=bool)
    if not valid.any():
        raise ValueError("build_terrain_mesh requires at least one valid sample.")

    h, w = values.shape

    def _vertex(r: int, c: int) -> Vertex:
        x, y = _cell_center(grid, r, c)
        return (x, y, float(values[r, c]))

    # Seed with the (valid) grid corners.
    corner_targets = [(0, 0), (0, w - 1), (h - 1, 0), (h - 1, w - 1)]
    seed_rc: list[tuple[int, int]] = []
    for tr, tc in corner_targets:
        rc = _nearest_valid(valid, tr, tc)
        if rc not in seed_rc:
            seed_rc.append(rc)
    if len(seed_rc) < 3:
        raise ValueError("Not enough distinct valid corners to seed a mesh.")

    vertices: list[Vertex] = [_vertex(r, c) for r, c in seed_rc]
    used: set[tuple[int, int]] = set(seed_rc)
    # seed_rc order is [TL, TR, BL, BR]; split on the TL-BR diagonal so the two
    # triangles fully cover the quad.
    if len(seed_rc) >= 4:
        triangles: list[Triangle] = [(0, 1, 3), (0, 3, 2)]
    else:
        triangles = [(0, 1, 2)]

    # Candidate samples: every valid cell that is not already a vertex.
    candidates = [
        (r, c)
        for r in range(h)
        for c in range(w)
        if valid[r, c] and (r, c) not in used
    ]

    def _containing(px: float, py: float) -> list[int]:
        hits = []
        for ti, (i, j, k) in enumerate(triangles):
            bary = _bary((vertices[i], vertices[j], vertices[k]), px, py)
            if bary and all(v >= -_EPS for v in bary):
                hits.append(ti)
        return hits

    def _worst() -> tuple[float, tuple[int, int] | None]:
        best_err = -1.0
        best_rc: tuple[int, int] | None = None
        for r, c in candidates:
            if (r, c) in used:
                continue
            px, py = _cell_center(grid, r, c)
            hits = _containing(px, py)
            if not hits:
                continue
            i, j, k = triangles[hits[0]]
            tri = (vertices[i], vertices[j], vertices[k])
            interp = _interp_z(tri, _bary(tri, px, py))
            err = abs(float(values[r, c]) - interp)
            if err > best_err:
                best_err, best_rc = err, (r, c)
        return best_err, best_rc

    while max_points is None or len(vertices) < max_points:
        best_err, best_rc = _worst()
        if best_rc is None or best_err <= error_budget_m:
            break
        r, c = best_rc
        px, py = _cell_center(grid, r, c)
        new_i = len(vertices)
        vertices.append(_vertex(r, c))
        used.add((r, c))
        hit_tris = _containing(px, py)
        kept = [t for ti, t in enumerate(triangles) if ti not in set(hit_tris)]
        for ti in hit_tris:
            i, j, k = triangles[ti]
            for a, b in ((i, j), (j, k), (k, i)):
                if _tri_area(vertices[a], vertices[b], vertices[new_i]) > _EPS:
                    kept.append((a, b, new_i))
        triangles = kept

    # Drop triangles whose footprint contains a nodata sample.
    if grid.nodata is not None and not valid.all():
        nodata_pts = [
            _cell_center(grid, int(r), int(c))
            for r, c in zip(*np.nonzero(~valid))
        ]
        triangles = [
            t for t in triangles if not _covers_any(vertices, t, nodata_pts)
        ]

    # Final achieved error over all valid samples (0 where a sample is a vertex).
    max_error = _measure_max_error(grid, values, valid, vertices, triangles)

    positions = tuple(vertices)
    tris = tuple(triangles)
    return TerrainMesh(
        positions=positions,
        triangles=tris,
        boundary_id=boundary_id,
        lod=lod,
        error_budget_m=float(error_budget_m),
        max_error_m=max_error,
        crs=grid.crs,
        vertical_units=_provenance_units(grid),
        source_raster_hash=_raster_hash(grid),
        geometry_hash=_geometry_hash(positions, tris),
    )


def mesh_from_dem(
    dem: NormalizedDem,
    *,
    error_budget_m: float,
    boundary_id: str,
    level: int = 0,
    max_points: int | None = None,
) -> TerrainMesh:
    """Build a terrain mesh from a DEM pyramid ``level`` (0 = finest)."""
    return build_terrain_mesh(
        dem.pyramid[level],
        error_budget_m=error_budget_m,
        boundary_id=boundary_id,
        max_points=max_points,
        lod=level,
    )


def _tri_area(a: Vertex, b: Vertex, c: Vertex) -> float:
    return abs((b[0] - a[0]) * (c[1] - a[1]) - (c[0] - a[0]) * (b[1] - a[1])) / 2.0


def _covers_any(
    vertices: Sequence[Vertex], tri: Triangle, points: Sequence[tuple[float, float]]
) -> bool:
    i, j, k = tri
    t = (vertices[i], vertices[j], vertices[k])
    for px, py in points:
        bary = _bary(t, px, py)
        if bary and all(v > _EPS for v in bary):
            return True
    return False


def _measure_max_error(
    grid: RasterGrid,
    values: np.ndarray,
    valid: np.ndarray,
    vertices: Sequence[Vertex],
    triangles: Sequence[Triangle],
) -> float:
    max_err = 0.0
    h, w = values.shape
    for r in range(h):
        for c in range(w):
            if not valid[r, c]:
                continue
            px, py = _cell_center(grid, r, c)
            best = None
            for i, j, k in triangles:
                tri = (vertices[i], vertices[j], vertices[k])
                bary = _bary(tri, px, py)
                if bary and all(v >= -_EPS for v in bary):
                    best = abs(float(values[r, c]) - _interp_z(tri, bary))
                    break
            if best is not None and best > max_err:
                max_err = best
    return max_err


def _provenance_units(grid: RasterGrid) -> str | None:
    prov = getattr(grid, "provenance", None)
    return getattr(prov, "vertical_units", None) if prov else None


def _raster_hash(grid: RasterGrid) -> str:
    arr = np.ascontiguousarray(grid.values, dtype=float)
    hasher = hashlib.sha256()
    hasher.update(arr.tobytes())
    t = grid.transform
    hasher.update(
        f"{t.origin_x},{t.origin_y},{t.pixel_width},{t.pixel_height},"
        f"{grid.crs},{grid.nodata}".encode()
    )
    return hasher.hexdigest()


def _geometry_hash(
    positions: Sequence[Vertex], triangles: Sequence[Triangle]
) -> str:
    hasher = hashlib.sha256()
    for x, y, z in positions:
        hasher.update(f"{x:.6f},{y:.6f},{z:.6f};".encode())
    hasher.update(b"|")
    for i, j, k in triangles:
        hasher.update(f"{i},{j},{k};".encode())
    return hasher.hexdigest()
