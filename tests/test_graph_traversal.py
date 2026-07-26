"""Tests for traversal, basins & statistics (Item #5, Task Group 2)."""

import math

from shapely.geometry import LineString

from src.graph import NetworkStats, build_graph
from src.loading import Layer

# Two headwaters (0,0) and (4,0) join at confluence (2,2), then flow to
# outlet (2,5).
S1 = LineString([(0, 0), (2, 2)])
S2 = LineString([(4, 0), (2, 2)])
S3 = LineString([(2, 2), (2, 5)])
SOURCE_A = (0.0, 0.0)
SOURCE_B = (4.0, 0.0)
CONFLUENCE = (2.0, 2.0)
OUTLET = (2.0, 5.0)


def _graph():
    layer = Layer("NHDFlowline", "nhdplus_hr", "1707", (S1, S2, S3), crs="EPSG:5070")
    return build_graph([layer])


def test_sources_and_outlets():
    g = _graph()
    assert set(g.sources()) == {SOURCE_A, SOURCE_B}
    assert set(g.outlets()) == {OUTLET}


def test_upstream_and_downstream():
    g = _graph()
    assert g.upstream(OUTLET) == {SOURCE_A, SOURCE_B, CONFLUENCE}
    assert g.downstream(SOURCE_A) == {CONFLUENCE, OUTLET}


def test_basin_of_outlet_contains_all_segments():
    g = _graph()
    assert g.basin(OUTLET) == {0, 1, 2}
    # A basin at the confluence excludes the segment below it.
    assert g.basin(CONFLUENCE) == {0, 1}


def test_statistics():
    g = _graph()
    stats = g.statistics()
    assert isinstance(stats, NetworkStats)
    assert stats.num_nodes == 4
    assert stats.num_edges == 3
    assert stats.num_sources == 2
    assert stats.num_outlets == 1
    expected = math.sqrt(8) + math.sqrt(8) + 3.0
    assert stats.total_length == expected


def test_empty_graph_has_zero_stats():
    g = build_graph([])
    stats = g.statistics()
    assert stats == NetworkStats()
