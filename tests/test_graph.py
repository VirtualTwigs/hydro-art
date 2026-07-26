"""Tests for directed graph construction (Item #5, Task Group 1)."""

from shapely.geometry import LineString, MultiLineString

from src.graph import build_graph
from src.loading import Layer


def _flow(*geoms):
    return Layer("NHDFlowline", "nhdplus_hr", "1707", tuple(geoms), crs="EPSG:5070")


def _wbd(*geoms):
    return Layer("WBDHU4", "wbd", "1707", tuple(geoms), crs="EPSG:5070")


def test_shared_endpoint_becomes_one_junction():
    # Two segments meeting at (1, 1): upstream (0,0)->(1,1), (2,0)->(1,1).
    a = LineString([(0, 0), (1, 1)])
    b = LineString([(2, 0), (1, 1)])
    graph = build_graph([_flow(a, b)])
    assert graph.digraph.number_of_nodes() == 3  # (0,0),(2,0),(1,1)
    assert graph.digraph.number_of_edges() == 2


def test_edge_oriented_first_to_last_vertex():
    line = LineString([(0, 0), (5, 5)])
    graph = build_graph([_flow(line)])
    assert graph.digraph.has_edge((0.0, 0.0), (5.0, 5.0))
    assert not graph.digraph.has_edge((5.0, 5.0), (0.0, 0.0))


def test_multilinestring_exploded_and_empty_skipped():
    multi = MultiLineString([[(0, 0), (1, 0)], [(1, 0), (2, 0)]])
    graph = build_graph([_flow(multi, LineString())])
    assert graph.digraph.number_of_edges() == 2


def test_parallel_braided_segments_preserved():
    a = LineString([(0, 0), (1, 0), (2, 0)])
    b = LineString([(0, 0), (1, 1), (2, 0)])  # same endpoints, different path
    graph = build_graph([_flow(a, b)])
    assert graph.digraph.number_of_edges() == 2  # MultiDiGraph keeps both


def test_zero_length_segment_dropped_and_counted():
    degenerate = LineString([(3, 3), (3, 3)])
    graph = build_graph([_flow(degenerate)])
    assert graph.digraph.number_of_edges() == 0
    assert graph.dropped_degenerate == 1


def test_boundary_layers_are_skipped():
    from shapely.geometry import box

    graph = build_graph([_wbd(box(0, 0, 10, 10)), _flow(LineString([(0, 0), (1, 1)]))])
    assert graph.digraph.number_of_edges() == 1
