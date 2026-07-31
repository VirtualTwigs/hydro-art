"""Tests for river elevation attribution & QA (Item 15).

Offline and deterministic. Uses a synthetic single-row DEM whose cell values are
sampled exactly at cell centers, so a downstream flowline gets a known elevation
profile — including a deliberate uphill "bump" that must be flagged as an
inversion and removable by the opt-in monotonic repair.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.hydro_z import (
    ElevatedLine,
    ElevatedVertex,
    ProfileQA,
    RepairPolicy,
    attribute_line,
    profile_qa,
    render_z,
    repair_monotonic,
)
from src.raster import GridSampler, GridTransform, RasterGrid
from src.terrain import TerrainSampler


def _row_dem(values, nodata=None):
    # 1 row, N cols; y-center == 0.5, x-centers == 0.5, 1.5, ...
    arr = np.array([values], dtype=float)
    return RasterGrid(arr, GridTransform(0.0, 1.0, 1.0, 1.0), "EPSG:5070", nodata)


def _sampler(values, nodata=None) -> TerrainSampler:
    return TerrainSampler(GridSampler(_row_dem(values, nodata)))


def test_attribute_line_builds_elevated_line_over_plane() -> None:
    sampler = _sampler([10, 8, 6, 4, 2])
    line = attribute_line(
        [(0.5, 0.5), (4.5, 0.5)], sampler, spacing=1.0, segment_id=7, dem_id="dem-1"
    )
    assert isinstance(line, ElevatedLine)
    assert isinstance(line.vertices[0], ElevatedVertex)
    assert line.segment_id == 7 and line.dem_id == "dem-1"
    assert [round(v.z, 3) for v in line.vertices] == [10, 8, 6, 4, 2]
    # Original 2D path is preserved verbatim (not the densified vertices).
    assert line.geometry_2d == ((0.5, 0.5), (4.5, 0.5))
    assert line.nodata_count == 0


def test_attribute_line_records_nodata_vertices() -> None:
    sampler = _sampler([10, 8, 6, 4, 2], nodata=6.0)
    line = attribute_line(
        [(0.5, 0.5), (4.5, 0.5)], sampler, spacing=1.0, segment_id=1, dem_id="d"
    )
    # The nodata cell (value 6 at index 2) flags its own center AND the adjacent
    # sample whose bilinear stencil touches it (conservative, per sample_bilinear).
    assert line.vertices[2].z is None
    assert line.nodata_count == 2


def test_profile_qa_detects_downstream_inversion() -> None:
    sampler = _sampler([10, 8, 9, 7, 5])  # bump: 9 > 8 going downstream
    line = attribute_line(
        [(0.5, 0.5), (4.5, 0.5)], sampler, spacing=1.0, segment_id=0, dem_id="d"
    )
    qa = profile_qa(line)
    assert isinstance(qa, ProfileQA)
    assert qa.inversion_indices == (2,)
    assert qa.max_inversion_m == pytest.approx(1.0)
    assert qa.n_vertices == 5 and qa.n_nodata == 0


def test_profile_qa_no_inversion_when_monotonic_downstream() -> None:
    sampler = _sampler([10, 8, 6, 4, 2])
    line = attribute_line(
        [(0.5, 0.5), (4.5, 0.5)], sampler, spacing=1.0, segment_id=0, dem_id="d"
    )
    assert profile_qa(line).inversion_indices == ()


def test_repair_monotonic_is_render_only_and_leaves_source_z_intact() -> None:
    sampler = _sampler([10, 8, 9, 7, 5])
    line = attribute_line(
        [(0.5, 0.5), (4.5, 0.5)], sampler, spacing=1.0, segment_id=0, dem_id="d"
    )
    repaired = repair_monotonic(line, RepairPolicy(enabled=True))
    assert repaired == (10.0, 8.0, 8.0, 7.0, 5.0)  # bump clamped down
    # Source Z on the line is untouched.
    assert [v.z for v in line.vertices] == [10.0, 8.0, 9.0, 7.0, 5.0]


def test_repair_monotonic_disabled_returns_source_surface() -> None:
    sampler = _sampler([10, 8, 9, 7, 5])
    line = attribute_line(
        [(0.5, 0.5), (4.5, 0.5)], sampler, spacing=1.0, segment_id=0, dem_id="d"
    )
    assert repair_monotonic(line, RepairPolicy(enabled=False)) == (10, 8, 9, 7, 5)


def test_repair_monotonic_carries_last_valid_over_nodata() -> None:
    sampler = _sampler([10, 8, 9, 7, 5], nodata=9.0)  # middle vertex is nodata
    line = attribute_line(
        [(0.5, 0.5), (4.5, 0.5)], sampler, spacing=1.0, segment_id=0, dem_id="d"
    )
    repaired = repair_monotonic(line, RepairPolicy(enabled=True))
    assert repaired[2] is None  # nodata preserved as a gap
    assert repaired[0] == 10.0 and repaired[-1] == 5.0


def test_render_z_applies_exaggeration_and_lift() -> None:
    assert render_z(100.0, vertical_exaggeration=2.0, river_lift=5.0) == 205.0
    assert render_z(None, vertical_exaggeration=2.0, river_lift=5.0) is None
