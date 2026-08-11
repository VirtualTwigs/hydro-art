"""Tests for stream-hierarchy ordering (Item #6, Task Group 1)."""

import networkx as nx
import pytest

from src.config import ConfigError, DEFAULTS, build_settings
from src.ordering import (
    OrderingError,
    assign_stream_order,
    custom_order,
    hack_order,
    shreve_order,
    strahler_order,
)


def _graph(*edges):
    """Build a MultiDiGraph from (u, v, segment_id, length) tuples."""
    g = nx.MultiDiGraph()
    for u, v, sid, length in edges:
        g.add_edge(u, v, segment_id=sid, length=length)
    return g


# Confluence graph: A(0) and B(1) merge -> C(2); D(3) joins C -> E(4).
_CONFLUENCE = _graph(
    ("a", "c", 0, 1.0),
    ("b", "c", 1, 1.0),
    ("c", "e", 2, 1.0),
    ("d", "e", 3, 1.0),
    ("e", "f", 4, 1.0),
)


def test_strahler_ties_increment_but_unequal_do_not():
    order = strahler_order(_CONFLUENCE)
    assert order[0] == 1 and order[1] == 1  # sources
    assert order[2] == 2  # two order-1 streams tie -> 2
    assert order[3] == 1  # source tributary
    assert order[4] == 2  # order-2 + order-1 -> stays 2


def test_shreve_sums_incoming_magnitudes():
    order = shreve_order(_CONFLUENCE)
    assert order[0] == 1 and order[1] == 1
    assert order[2] == 2  # 1 + 1
    assert order[4] == 3  # 2 + 1


def test_hack_main_stem_is_one_tributary_is_two():
    # Long tributary A + short tributary B meet, continue as stem C.
    g = _graph(
        ("s0", "j", 0, 5.0),  # long -> main channel
        ("s1", "j", 1, 2.0),  # short -> tributary
        ("j", "out", 2, 5.0),  # downstream stem
    )
    order = hack_order(g)
    assert order[2] == 1  # stem
    assert order[0] == 1  # main channel continues the stem
    assert order[1] == 2  # tributary increments outward


def test_dispatch_matches_direct_methods():
    assert assign_stream_order(_CONFLUENCE, "strahler") == strahler_order(_CONFLUENCE)
    assert assign_stream_order(_CONFLUENCE, "shreve") == shreve_order(_CONFLUENCE)


def test_unknown_method_raises():
    with pytest.raises(OrderingError):
        assign_stream_order(_CONFLUENCE, "nonsense")


def test_cyclic_graph_is_tolerated():
    # Real hydrography can contain small directed cycles; ordering must not
    # raise. Every segment still receives an order via the condensation.
    cyclic = _graph(("x", "y", 0, 1.0), ("y", "x", 1, 1.0))
    order = assign_stream_order(cyclic, "strahler")
    assert set(order) == {0, 1}
    assert all(isinstance(v, int) for v in order.values())


def test_custom_order_uses_weight_fn():
    order = custom_order(_CONFLUENCE, lambda data: data["length"] * 10)
    assert order[0] == 10.0
    # Dispatcher default weight = cumulative upstream length.
    default = assign_stream_order(_CONFLUENCE, "custom")
    assert default[4] == pytest.approx(5.0)  # all five unit-length segments


def test_stream_method_validation_and_yaml_survives_unset_flag():
    with pytest.raises(ConfigError):
        build_settings({**DEFAULTS, "stream_method": "bogus"})
    # A YAML-supplied method survives when the CLI flag is unset (None).
    settings = build_settings({**DEFAULTS, "stream_method": "shreve"})
    assert settings.stream_method == "shreve"
