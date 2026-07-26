"""Tests for region boundary & clipping (Item #4, Task Group 2)."""

import warnings

from shapely.geometry import LineString, box

from src.clipping import (
    ClipStats,
    clip_geometry,
    clip_layers,
    region_boundary,
)
from src.loading import Layer


def _flowline(*geoms):
    return Layer("NHDFlowline", "nhdplus_hr", "1707", tuple(geoms), crs="EPSG:5070")


def _wbd(*geoms):
    return Layer("WBDHU4", "wbd", "1707", tuple(geoms), crs="EPSG:5070")


UNIT = box(0, 0, 10, 10)


def test_region_boundary_unions_wbd_layers():
    layers = [_wbd(box(0, 0, 5, 10)), _wbd(box(5, 0, 10, 10)), _flowline()]
    boundary = region_boundary(layers)
    assert boundary.equals(box(0, 0, 10, 10))


def test_region_boundary_warns_when_no_wbd():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        boundary = region_boundary([_flowline()])
    assert boundary is None
    assert any("No WBD boundary" in str(w.message) for w in caught)


def test_line_crossing_boundary_is_trimmed():
    crossing = LineString([(-5, 5), (5, 5)])  # half outside on the left
    clipped = clip_geometry(crossing, UNIT)
    assert clipped is not None
    assert clipped.bounds[0] >= 0  # trimmed at the boundary edge


def test_line_fully_outside_is_dropped():
    outside = LineString([(20, 20), (30, 30)])
    assert clip_geometry(outside, UNIT) is None


def test_clip_layers_counts_and_preserves_inside():
    inside = LineString([(1, 1), (2, 2)])
    crossing = LineString([(-5, 5), (5, 5)])
    outside = LineString([(20, 20), (30, 30)])
    layers = [_wbd(UNIT), _flowline(inside, crossing, outside)]

    clipped, stats = clip_layers(layers, UNIT)
    assert stats.total_in == 3
    assert stats.total_out == 2
    assert stats.dropped_outside == 1
    assert stats.clipped_partial == 1

    # Boundary layer passes through unchanged; inside line unchanged.
    flow = next(layer for layer in clipped if layer.dataset_id == "nhdplus_hr")
    assert any(g.equals(inside) for g in flow.geometries)


def test_clip_stats_merge():
    a = ClipStats(total_in=2, total_out=1, dropped_outside=1)
    b = ClipStats(total_in=3, total_out=3, clipped_partial=2)
    merged = a.merge(b)
    assert merged.total_in == 5
    assert merged.total_out == 4
    assert merged.dropped_outside == 1
    assert merged.clipped_partial == 2
