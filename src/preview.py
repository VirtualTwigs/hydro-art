"""Browser preview-asset generation (Item 18, Epoch 4 Phase 4.2).

Turns a normalized DEM pyramid into browser-ready heightfield tiles so the 3D
lab (``web/3d.html``) can replace its synthetic ``elevationAt()`` field with
real sampled elevation. Two level-of-detail tiles are emitted:

- an ``interaction`` tile from a coarser pyramid level (fast to orbit), and
- a ``commit`` tile from the finest level (full detail on release).

Optional Z-attributed rivers are serialized as ``[x, y, z]`` meter polylines.
Everything here is pure, deterministic, and offline — it consumes the numpy
grids produced by :mod:`src.raster` and the :class:`~src.hydro_z.ElevatedLine`
values from :mod:`src.hydro_z`, with no GDAL/network dependency, and serializes
to stable ``sort_keys`` JSON.
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Mapping, Sequence

from src.raster import NormalizedDem, RasterGrid

__all__ = ["build_preview_asset", "preview_json"]

#: Identifies the asset producer in the serialized output.
GENERATOR = "hydro-art preview (item 18)"


def _clamp_level(dem: NormalizedDem, level: int) -> int:
    """Clamp a requested pyramid level to the available range."""
    last = len(dem.pyramid) - 1
    return max(0, min(last, level))


def _tile(grid: RasterGrid, level: int) -> dict[str, Any]:
    """Serialize one pyramid level as a row-major heightfield tile."""
    z: list[float | None] = []
    for r in range(grid.height):
        for c in range(grid.width):
            v = float(grid.values[r, c])
            if grid.nodata is not None and v == grid.nodata:
                z.append(None)
            else:
                z.append(v)
    return {"level": level, "width": grid.width, "height": grid.height, "z": z}


def _z_range(grid: RasterGrid) -> tuple[float, float]:
    """Min/max of a grid's valid (non-nodata) values."""
    vals = [
        float(grid.values[r, c])
        for r in range(grid.height)
        for c in range(grid.width)
        if grid.nodata is None or float(grid.values[r, c]) != grid.nodata
    ]
    return min(vals), max(vals)


def _river(line: Any, color: str) -> dict[str, Any]:
    """Serialize a Z-attributed river line as an ``[x, y, z]`` polyline."""
    pts: list[list[float | None]] = []
    for v in line.vertices:
        z = None if v.z is None else float(v.z)
        pts.append([float(v.x), float(v.y), z])
    return {"segment_id": line.segment_id, "color": color, "pts": pts}


def build_preview_asset(
    dem: NormalizedDem,
    *,
    boundary_id: str,
    interaction_level: int = 1,
    commit_level: int = 0,
    rivers: Sequence[Any] = (),
    segment_colors: Mapping[int, str] | None = None,
    default_color: str = "#808080",
) -> dict[str, Any]:
    """Build a browser-ready preview asset from a normalized DEM.

    Emits a coarse ``interaction`` tile and a fine ``commit`` tile (each a
    row-major heightfield with nodata surfaced as ``null``), the geographic
    bounds and elevation range of the commit grid, per-LOD cell sizes, and any
    Z-attributed rivers as ``[x, y, z]`` meter polylines. Requested pyramid
    levels are clamped to what the DEM provides, so a single-level DEM collapses
    both LODs onto level 0.
    """
    inter_lvl = _clamp_level(dem, interaction_level)
    commit_lvl = _clamp_level(dem, commit_level)
    inter_grid = dem.pyramid[inter_lvl]
    commit_grid = dem.pyramid[commit_lvl]

    min_x, min_y, max_x, max_y = commit_grid.bounds
    min_z, max_z = _z_range(commit_grid)

    colors = dict(segment_colors or {})
    river_out = [
        _river(line, colors.get(line.segment_id, default_color)) for line in rivers
    ]

    return {
        "generator": GENERATOR,
        "boundary_id": boundary_id,
        "crs": dem.base.crs,
        "tiles": {
            "interaction": _tile(inter_grid, inter_lvl),
            "commit": _tile(commit_grid, commit_lvl),
        },
        "cell_size_m": {
            "interaction": inter_grid.transform.pixel_width,
            "commit": commit_grid.transform.pixel_width,
        },
        "bounds": {
            "min_x": min_x,
            "min_y": min_y,
            "max_x": max_x,
            "max_y": max_y,
            "min_z": min_z,
            "max_z": max_z,
        },
        "rivers": river_out,
    }


def preview_json(asset: Mapping[str, Any]) -> str:
    """Serialize a preview asset to deterministic JSON."""
    return json.dumps(asset, sort_keys=True, separators=(",", ":"))
