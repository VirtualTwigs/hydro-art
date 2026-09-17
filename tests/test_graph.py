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


# --- Task Group 2 (Item #66): FType propagation to graph edges ---


def _flow_with_attrs(geoms, attributes):
    """Helper: create a flowline Layer with parallel attributes."""
    return Layer(
        "NHDFlowline", "nhdplus_hr", "1707", tuple(geoms),
        crs="EPSG:5070", attributes=tuple(attributes),
    )


def test_build_graph_preserves_ftype():
    """Edge data includes ftype when layer has attributes."""
    line_a = LineString([(0, 0), (1, 1)])
    line_b = LineString([(2, 2), (3, 3)])
    layer = _flow_with_attrs(
        [line_a, line_b],
        [{"FType": 336, "FCode": 33600}, {"FType": 460, "FCode": 46006}],
    )
    graph = build_graph([layer])
    edges = list(graph.digraph.edges(data=True))
    assert len(edges) == 2
    ftypes = {data["ftype"] for _, _, data in edges}
    assert ftypes == {336, 460}


def test_build_graph_no_ftype_without_attributes():
    """ftype absent from edge data when layer has no attributes."""
    line = LineString([(0, 0), (1, 1)])
    layer = _flow(line)
    graph = build_graph([layer])
    edges = list(graph.digraph.edges(data=True))
    assert len(edges) == 1
    _, _, data = edges[0]
    assert "ftype" not in data


def test_build_graph_ftype_propagated_to_multi_segments():
    """MultiLineString explosion: all child segments get the parent's FType."""
    multi = MultiLineString([[(0, 0), (1, 0)], [(1, 0), (2, 0)]])
    layer = _flow_with_attrs(
        [multi],
        [{"FType": 428}],
    )
    graph = build_graph([layer])
    edges = list(graph.digraph.edges(data=True))
    assert len(edges) == 2
    for _, _, data in edges:
        assert data["ftype"] == 428


def test_build_graph_mixed_layers_with_and_without_attrs():
    """Layers with attributes and layers without can coexist."""
    line_a = LineString([(0, 0), (1, 1)])
    line_b = LineString([(5, 5), (6, 6)])
    layer_with = _flow_with_attrs([line_a], [{"FType": 336}])
    layer_without = _flow(line_b)
    graph = build_graph([layer_with, layer_without])
    edges = list(graph.digraph.edges(data=True))
    assert len(edges) == 2
    ftype_present = [data.get("ftype") for _, _, data in edges]
    assert 336 in ftype_present
    assert None in ftype_present or any(
        "ftype" not in data for _, _, data in edges
    )
