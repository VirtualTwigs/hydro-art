"""Tests for geometry validation & repair (Item #3, Task Group 2)."""

from shapely.geometry import (
    LineString,
    MultiLineString,
    Point,
    Polygon,
)

from src.geometry import RepairStats, repair_geometry, repair_layer


def test_bowtie_polygon_is_made_valid():
    # A self-intersecting "bowtie" polygon is invalid.
    bowtie = Polygon([(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)])
    assert not bowtie.is_valid

    outcome = repair_geometry(bowtie)
    assert outcome.geometry is not None
    assert outcome.geometry.is_valid
    assert outcome.invalid_fixed
    assert outcome.self_intersection_fixed


def test_duplicate_vertices_removed_without_changing_shape():
    dupey = LineString([(0, 0), (0, 0), (1, 1), (1, 1), (2, 2)])
    outcome = repair_geometry(dupey)
    assert outcome.duplicate_vertices_removed == 2
    # Shape is preserved: same endpoints and length.
    assert outcome.geometry.equals(LineString([(0, 0), (1, 1), (2, 2)]))


def test_empty_geometry_is_dropped_and_counted():
    outcome = repair_geometry(LineString())
    assert outcome.geometry is None
    assert outcome.dropped == "empty"


def test_collapsed_zero_length_line_is_dropped():
    # All-identical points collapse to zero length after dedup.
    outcome = repair_geometry(LineString([(5, 5), (5, 5), (5, 5)]))
    assert outcome.geometry is None
    assert outcome.dropped == "collapsed"


def test_singleton_multipart_normalized_genuine_multipart_preserved():
    singleton = MultiLineString([[(0, 0), (1, 1)]])
    out_single = repair_geometry(singleton)
    assert out_single.multipart_normalized
    assert out_single.geometry.geom_type == "LineString"

    genuine = MultiLineString([[(0, 0), (1, 1)], [(2, 2), (3, 3)]])
    out_multi = repair_geometry(genuine)
    assert not out_multi.multipart_normalized
    assert out_multi.geometry.geom_type == "MultiLineString"


def test_repair_layer_aggregates_and_merges_stats():
    geoms = [
        LineString([(0, 0), (1, 1)]),                 # clean
        LineString([(0, 0), (0, 0), (1, 1)]),          # 1 dup vertex
        LineString(),                                  # empty -> dropped
        Polygon([(0, 0), (1, 1), (1, 0), (0, 1), (0, 0)]),  # invalid -> fixed
    ]
    kept, stats = repair_layer(geoms)
    assert stats.total_in == 4
    assert stats.total_out == 3
    assert stats.empties_dropped == 1
    assert stats.duplicate_vertices_removed == 1
    assert stats.invalid_fixed == 1
    assert len(kept) == 3

    merged = stats.merge(stats)
    assert merged.total_in == 8
    assert merged.invalid_fixed == 2


def test_point_is_not_treated_as_collapsed():
    outcome = repair_geometry(Point(1, 2))
    assert outcome.geometry is not None
    assert outcome.dropped is None
