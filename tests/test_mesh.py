"""Tests for the adaptive terrain mesh (Item 16, Epoch 3 Phase 3.3).

Offline and deterministic. Uses tiny synthetic ``RasterGrid``s so the greedy
error-bounded TIN's behavior is hand-verifiable: a perfectly planar DEM needs
only the four corners (two triangles); a DEM with a localized peak must refine
near the peak to satisfy the vertical-error budget; and identical inputs must
yield identical geometry hashes.
"""

from __future__ import annotations

import numpy as np

from src.mesh import TerrainMesh, build_terrain_mesh, mesh_from_dem
from src.raster import GridTransform, NormalizedDem, RasterGrid


def _grid(values, nodata=None):
    arr = np.array(values, dtype=float)
    # 1 m cells, top-left corner at (0, height); cell centers at 0.5, 1.5, ...
    h = arr.shape[0]
    return RasterGrid(arr, GridTransform(0.0, float(h), 1.0, 1.0), "EPSG:5070", nodata)


def _plane(h, w, *, slope=0.0):
    # z = slope * x (planar), so a TIN needs only the 4 corners.
    return [[slope * (c + 0.5) for c in range(w)] for _ in range(h)]


def test_flat_plane_reduces_to_two_triangles() -> None:
    mesh = build_terrain_mesh(
        _grid(_plane(5, 5, slope=3.0)), error_budget_m=0.01, boundary_id="b1"
    )
    assert isinstance(mesh, TerrainMesh)
    assert len(mesh.positions) == 4  # only the four corners are needed
    assert len(mesh.triangles) == 2
    assert mesh.boundary_id == "b1"
    assert mesh.max_error_m <= 0.01


def test_positions_are_true_meters_no_exaggeration() -> None:
    mesh = build_terrain_mesh(
        _grid(_plane(5, 5, slope=2.0)), error_budget_m=0.01, boundary_id="b"
    )
    zs = sorted({round(z, 6) for _, _, z in mesh.positions})
    # Corner x-centers are 0.5 and 4.5 -> z = 1.0 and 9.0 at 1x scale.
    assert zs == [1.0, 9.0]
    xs = sorted({round(x, 6) for x, _, _ in mesh.positions})
    assert xs == [0.5, 4.5]


def test_peak_forces_refinement_within_budget() -> None:
    vals = _plane(5, 5, slope=0.0)
    vals[2][2] = 50.0  # sharp central peak far above the planar corners
    mesh = build_terrain_mesh(_grid(vals), error_budget_m=1.0, boundary_id="b")
    assert mesh.max_error_m <= 1.0
    # The peak sample must have become an explicit mesh vertex.
    assert any(round(z, 3) == 50.0 for _, _, z in mesh.positions)
    assert len(mesh.positions) > 4


def test_looser_budget_yields_coarser_mesh() -> None:
    vals = _plane(9, 9, slope=0.0)
    vals[4][4] = 20.0
    tight = build_terrain_mesh(_grid(vals), error_budget_m=0.5, boundary_id="b")
    loose = build_terrain_mesh(_grid(vals), error_budget_m=25.0, boundary_id="b")
    assert len(loose.positions) <= len(tight.positions)
    assert len(loose.positions) == 4  # budget above the peak -> corners only


def test_geometry_hash_is_deterministic() -> None:
    vals = _plane(5, 5, slope=0.0)
    vals[1][3] = 12.0
    m1 = build_terrain_mesh(_grid(vals), error_budget_m=0.5, boundary_id="b")
    m2 = build_terrain_mesh(_grid(vals), error_budget_m=0.5, boundary_id="b")
    assert m1.geometry_hash == m2.geometry_hash
    # A different budget that changes geometry changes the hash.
    m3 = build_terrain_mesh(_grid(vals), error_budget_m=50.0, boundary_id="b")
    assert m3.geometry_hash != m1.geometry_hash


def test_max_points_caps_output() -> None:
    rng = np.random.default_rng(0)
    vals = rng.normal(0.0, 10.0, size=(9, 9))
    mesh = build_terrain_mesh(
        _grid(vals.tolist()), error_budget_m=0.001, boundary_id="b", max_points=6
    )
    assert len(mesh.positions) <= 6


def test_nodata_triangles_are_dropped() -> None:
    vals = _plane(5, 5, slope=0.0)
    vals[0][0] = -9999.0  # a nodata corner hole
    mesh = build_terrain_mesh(
        _grid(vals, nodata=-9999.0), error_budget_m=1.0, boundary_id="b"
    )
    # No mesh vertex uses the nodata sentinel value.
    assert all(z != -9999.0 for _, _, z in mesh.positions)
    assert len(mesh.triangles) >= 1


def test_mesh_from_dem_selects_pyramid_level() -> None:
    base = _grid(_plane(9, 9, slope=1.0))
    coarse = _grid(_plane(5, 5, slope=1.0))
    dem = NormalizedDem(base=base, pyramid=(base, coarse))
    mesh = mesh_from_dem(dem, level=1, error_budget_m=0.01, boundary_id="b")
    assert mesh.lod == 1
    assert mesh.max_error_m <= 0.01
    assert mesh.source_raster_hash  # populated from the selected level
