"""DEM alignment invariant regression (Epoch 10 #42, offline half).

Reproduces the #32 latitude-drift class with hand-built grids — no GDAL, no real
data. The bug: warping each 1°×1° 3DEP tile to the metric internal CRS
*independently* picks a per-tile output pixel size that drifts with latitude, so
the warped tiles no longer share a pixel grid and cannot be mosaicked. The fix
(``normalize_dem`` mosaics in the shared source CRS *before* the single warp)
yields one uniform-pixel grid; ``_require_aligned`` tolerates last-float-digit
warp drift (``rel_tol=1e-6``) while still rejecting a genuine tier change.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.dem import DemAsset
from src.elevation import TileRef, build_provenance
from src.raster import (
    GridTransform,
    RasterGrid,
    _require_aligned,
    mosaic,
    normalize_dem,
)


def _grid(values, *, origin_x=0.0, origin_y=2.0, px=1.0, py=1.0, crs="EPSG:4269"):
    return RasterGrid(
        values=np.array(values, dtype=float),
        transform=GridTransform(origin_x, origin_y, px, py),
        crs=crs,
    )


def _asset(tile_id: str) -> DemAsset:
    prov = build_provenance(
        source_product="USGS 3DEP 1 arc-second DEM",
        source_url=f"http://x/{tile_id}.tif",
        acquisition_date="2026-07-30",
        horizontal_crs="EPSG:4269",
        vertical_crs="NAVD88",
        vertical_units="meters",
        resolution_m=30.0,
        checksum="sha256:abc",
    )
    return DemAsset(tile=TileRef(tile_id, prov.source_url, 30.0), path=Path("x"), provenance=prov)


class _FakeReader:
    """Maps a DemAsset to its predefined source-CRS grid (EPSG:4269)."""

    def __init__(self, grids: dict[str, RasterGrid]) -> None:
        self._grids = grids

    def read(self, asset: DemAsset) -> RasterGrid:
        return self._grids[asset.tile.tile_id]


class _LatitudeDriftReprojector:
    """Models the #32 bug: the warped pixel size depends on the grid's latitude.

    ``origin_y`` stands in for latitude — a grid warped nearer the pole gets a
    slightly smaller metre pixel. Applied to a *single* mosaic this just picks one
    resolution (fine); applied per-tile it makes adjacent tiles drift apart.
    """

    def __init__(self) -> None:
        self.calls: list[str] = []

    def reproject(self, grid: RasterGrid, dst_crs: str) -> RasterGrid:
        self.calls.append(dst_crs)
        t = grid.transform
        scale = 1.0 - t.origin_y * 1e-3
        return RasterGrid(
            values=grid.values,
            transform=GridTransform(
                t.origin_x, t.origin_y, t.pixel_width * scale, t.pixel_height * scale
            ),
            crs=dst_crs,
            nodata=grid.nodata,
            provenance=grid.provenance,
        )


def test_normalize_dem_applies_single_warp_to_the_mosaic() -> None:
    # Two tiles stacked in latitude: north (y=4) over south (y=2), aligned at
    # 1m in the shared source CRS.
    grids = {
        "north": _grid([[10, 20], [30, 40]], origin_x=0.0, origin_y=4.0),
        "south": _grid([[50, 60], [70, 80]], origin_x=0.0, origin_y=2.0),
    }
    reprojector = _LatitudeDriftReprojector()

    result = normalize_dem(
        assets=[_asset("north"), _asset("south")],
        boundary=(0.0, 0.0, 2.0, 4.0),
        reader=_FakeReader(grids),
        reprojector=reprojector,
        pyramid_levels=2,
    )

    # Mosaic-before-warp: exactly one warp, of the merged mosaic (not per tile).
    assert reprojector.calls == ["EPSG:5070"]
    # The single warp yields one uniform pixel grid — no latitude drift.
    t = result.base.transform
    assert t.pixel_width == pytest.approx(t.pixel_height)
    assert t.pixel_width == pytest.approx(1.0 - 4.0 * 1e-3)


def test_warp_then_mosaic_would_drift_and_fail() -> None:
    # The bug the fix avoids: warp each tile independently, then try to mosaic.
    north = _grid([[10, 20], [30, 40]], origin_x=0.0, origin_y=4.0)
    south = _grid([[50, 60], [70, 80]], origin_x=0.0, origin_y=2.0)
    reprojector = _LatitudeDriftReprojector()

    warped = [
        reprojector.reproject(north, "EPSG:5070"),
        reprojector.reproject(south, "EPSG:5070"),
    ]
    # 0.996 vs 0.998 — a ~2e-3 relative gap, far outside rel_tol=1e-6.
    assert warped[0].transform.pixel_width != pytest.approx(
        warped[1].transform.pixel_width, rel=1e-6
    )
    with pytest.raises(ValueError, match="mismatched pixel sizes"):
        mosaic(warped)


def test_require_aligned_tolerates_float_drift_but_rejects_tier_change() -> None:
    base = _grid([[1, 2], [3, 4]], px=1.0, py=1.0, crs="EPSG:5070")

    # Last-float-digit warp drift (~1e-7 relative) is the same resolution.
    drifted = _grid([[5, 6], [7, 8]], px=1.0 + 1e-7, py=1.0 + 1e-7, crs="EPSG:5070")
    pw, ph, crs = _require_aligned([base, drifted])
    assert (pw, ph, crs) == (1.0, 1.0, "EPSG:5070")

    # A genuine resolution change (~1e-5 relative here; a real tier is whole
    # metres) is still rejected.
    tier_change = _grid([[5, 6], [7, 8]], px=1.0 + 1e-5, py=1.0 + 1e-5, crs="EPSG:5070")
    with pytest.raises(ValueError, match="mismatched pixel sizes"):
        _require_aligned([base, tier_change])
