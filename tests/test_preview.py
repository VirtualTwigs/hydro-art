"""Tests for browser preview-asset generation (Item 18, Epoch 4 Phase 4.2).

Offline and deterministic. Builds DEM-derived preview tiles (a coarse
interaction LOD + a fine commit LOD) plus optional Z-attributed rivers from
synthetic pyramids, so the 3D lab can replace its synthetic ``elevationAt()``
field with real sampled elevation without any GDAL/network dependency.
"""

from __future__ import annotations

import json

import numpy as np

from src.hydro_z import ElevatedLine, ElevatedVertex
from src.preview import build_preview_asset, preview_json
from src.raster import GridTransform, NormalizedDem, RasterGrid


def _dem(nodata=None):
    # 4x4 finest grid, z = row*10 + col; one coarser 2x2 pyramid level.
    base = np.array(
        [[r * 10 + c for c in range(4)] for r in range(4)], dtype=float
    )
    fine = RasterGrid(base, GridTransform(0.0, 4.0, 1.0, 1.0), "EPSG:5070", nodata)
    coarse_vals = np.array([[5.0, 7.0], [25.0, 27.0]])  # 2x2 block means
    coarse = RasterGrid(coarse_vals, GridTransform(0.0, 4.0, 2.0, 2.0), "EPSG:5070", nodata)
    return NormalizedDem(base=fine, pyramid=(fine, coarse))


def test_asset_has_interaction_and_commit_tiles() -> None:
    asset = build_preview_asset(_dem(), boundary_id="clark")
    inter, commit = asset["tiles"]["interaction"], asset["tiles"]["commit"]
    assert (commit["width"], commit["height"]) == (4, 4)  # finest level
    assert (inter["width"], inter["height"]) == (2, 2)  # coarser level
    assert inter["level"] == 1 and commit["level"] == 0


def test_tile_z_is_row_major_with_nodata_null() -> None:
    asset = build_preview_asset(_dem(nodata=11.0), boundary_id="b")
    commit = asset["tiles"]["commit"]
    assert len(commit["z"]) == commit["width"] * commit["height"]
    # value 11.0 sits at row 1, col 1 -> index 5, surfaced as null (not substituted).
    assert commit["z"][5] is None
    assert commit["z"][0] == 0.0


def test_bounds_ignore_nodata_for_z_range() -> None:
    asset = build_preview_asset(_dem(nodata=33.0), boundary_id="b")
    b = asset["bounds"]
    assert (b["min_x"], b["min_y"], b["max_x"], b["max_y"]) == (0.0, 0.0, 4.0, 4.0)
    assert b["min_z"] == 0.0
    assert b["max_z"] == 32.0  # 33 excluded, next highest is 32 (row3,col2)


def test_interaction_cell_size_is_coarser() -> None:
    asset = build_preview_asset(_dem(), boundary_id="b")
    assert asset["cell_size_m"]["interaction"] > asset["cell_size_m"]["commit"]


def test_rivers_carry_source_z_meters_with_null_nodata() -> None:
    r = ElevatedLine(
        7,
        (ElevatedVertex(0.5, 0.5, 10.0), ElevatedVertex(1.5, 0.5, None)),
        ((0.5, 0.5), (1.5, 0.5)),
        "dem-1",
    )
    asset = build_preview_asset(
        _dem(), boundary_id="b", rivers=[r], segment_colors={7: "#00ffff"}
    )
    assert len(asset["rivers"]) == 1
    riv = asset["rivers"][0]
    assert riv["color"] == "#00ffff"
    assert riv["pts"][0] == [0.5, 0.5, 10.0]
    assert riv["pts"][1][2] is None


def test_single_level_dem_clamps_interaction_to_commit() -> None:
    fine = RasterGrid(
        np.array([[1.0, 2.0], [3.0, 4.0]]), GridTransform(0.0, 2.0, 1.0, 1.0), "EPSG:5070"
    )
    dem = NormalizedDem(base=fine, pyramid=(fine,))
    asset = build_preview_asset(dem, boundary_id="b")
    assert asset["tiles"]["interaction"]["level"] == asset["tiles"]["commit"]["level"] == 0


def test_preview_json_is_deterministic_and_roundtrips() -> None:
    dem = _dem()
    j1 = preview_json(build_preview_asset(dem, boundary_id="b"))
    j2 = preview_json(build_preview_asset(dem, boundary_id="b"))
    assert j1 == j2
    parsed = json.loads(j1)
    assert parsed["boundary_id"] == "b" and parsed["crs"] == "EPSG:5070"


def test_no_rivers_yields_empty_list() -> None:
    asset = build_preview_asset(_dem(), boundary_id="b")
    assert asset["rivers"] == []
