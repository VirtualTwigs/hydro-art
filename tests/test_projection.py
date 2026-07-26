"""Tests for reprojection to the internal CRS (Item #4, Task Group 1)."""

import pytest
from shapely import get_num_coordinates
from shapely.geometry import LineString

from src.loading import Layer
from src.projection import ProjectionError, reproject_layer


def _layer(geom, crs):
    return Layer("NHDFlowline", "nhdplus_hr", "1707", (geom,), crs=crs)


def test_reproject_4326_to_5070_changes_coordinates():
    # A point in the Pacific Northwest, lon/lat.
    line = LineString([(-122.5, 45.5), (-122.0, 46.0)])
    out = reproject_layer(_layer(line, "EPSG:4326"), "EPSG:5070")
    assert out.crs == "EPSG:5070"
    new = out.geometries[0]
    # EPSG:5070 is a metric Albers projection: coordinates are large meters,
    # nothing like the original degrees.
    xs = [c[0] for c in new.coords]
    assert all(abs(x) > 1000 for x in xs)


def test_reproject_identity_when_already_target():
    line = LineString([(0, 0), (1, 1)])
    layer = _layer(line, "EPSG:5070")
    out = reproject_layer(layer, "EPSG:5070")
    assert out is layer  # unchanged identity


def test_missing_crs_raises():
    line = LineString([(0, 0), (1, 1)])
    with pytest.raises(ProjectionError, match="no CRS"):
        reproject_layer(_layer(line, None), "EPSG:5070")


def test_reprojection_preserves_vertex_count():
    line = LineString([(-122.5, 45.5), (-122.3, 45.7), (-122.0, 46.0)])
    out = reproject_layer(_layer(line, "EPSG:4326"), "EPSG:5070")
    assert get_num_coordinates(out.geometries[0]) == get_num_coordinates(line)
