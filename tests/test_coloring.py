"""Tests for adjacency + deterministic graph coloring (Item #7, TG2)."""

import networkx as nx

from src.coloring import (
    PALETTES,
    assign_colors,
    build_adjacency,
    greedy_color,
)


def _graph(*edges):
    """Build a MultiDiGraph from (segment_id, u_node, v_node) tuples."""
    g = nx.MultiDiGraph()
    for segment_id, u, v in edges:
        g.add_edge(u, v, segment_id=segment_id, length=1.0)
    return g


# Two watersheds that touch at node 3 (seg 1 flows into it, seg 2 out of it),
# plus an isolated watershed C on a disconnected pair of nodes.
def _touching_graph():
    return _graph(
        (0, 1, 2),  # A
        (1, 2, 3),  # A  -> node 3
        (2, 3, 4),  # B  -> shares node 3 with A
        (3, 10, 11),  # C  -> isolated
    )


_WATERSHEDS = {"1707": {0, 1}, "1710": {2}, "1801": {3}}


def test_shared_junction_makes_watersheds_adjacent():
    adjacency = build_adjacency(_touching_graph(), _WATERSHEDS)
    assert adjacency["1707"] == {"1710"}
    assert adjacency["1710"] == {"1707"}


def test_isolated_watershed_has_empty_adjacency_but_is_a_key():
    adjacency = build_adjacency(_touching_graph(), _WATERSHEDS)
    assert "1801" in adjacency
    assert adjacency["1801"] == set()
    # No self-adjacency.
    assert all(code not in nbrs for code, nbrs in adjacency.items())


def test_greedy_color_gives_adjacent_watersheds_distinct_classes():
    adjacency = build_adjacency(_touching_graph(), _WATERSHEDS)
    classes = greedy_color(adjacency)
    assert classes["1707"] != classes["1710"]


def test_greedy_color_is_deterministic():
    adjacency = build_adjacency(_touching_graph(), _WATERSHEDS)
    assert greedy_color(adjacency) == greedy_color(adjacency)


def test_assign_colors_adjacent_get_distinct_neon_hex():
    result = assign_colors(_touching_graph(), _WATERSHEDS, "neon")
    assert set(result) == {"1707", "1710", "1801"}
    assert result["1707"] != result["1710"]
    assert all(color in PALETTES["neon"] for color in result.values())
    # Fully deterministic across runs.
    assert assign_colors(_touching_graph(), _WATERSHEDS, "neon") == result


def test_single_watershed_gets_one_color():
    g = _graph((0, 1, 2))
    result = assign_colors(g, {"1707": {0}}, "neon")
    assert result == {"1707": PALETTES["neon"][0]}


def test_empty_watersheds_yield_empty_result():
    assert assign_colors(_graph(), {}, "neon") == {}
