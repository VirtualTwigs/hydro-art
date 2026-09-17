"""Stream-hierarchy ordering over the river-network graph (PRD section 12).

Computes a per-segment stream order using one of four user-selectable methods:

* **Strahler** — sources are order 1; at a confluence the order increments only
  when the two highest incoming orders are equal (otherwise it inherits the
  single highest).
* **Shreve** — additive *magnitude*: sources are 1 and a confluence sums its
  incoming orders.
* **Hack** — the main stem is 1 and order grows outward to tributaries; the main
  channel at each junction is the incoming segment with the greatest cumulative
  upstream length.
* **Custom** — a per-segment weight from a supplied ``weight(edge_data)`` hook
  (the dispatcher's default weight is cumulative upstream length).

Every method processes the directed graph in (approximate) topological order.
Real hydrography occasionally contains small directed cycles (braided channels,
digitizing artifacts); rather than fail, node ordering is derived from the
graph's *condensation* — its DAG of strongly-connected components — so cyclic
graphs still yield a stream order (segments inside a cycle are ordered
arbitrarily among themselves). All functions are pure computations over a
``networkx.MultiDiGraph`` and are fully unit-testable with hand-built line
networks (no GDAL, no real data).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

import networkx as nx

from src.datasets import AcquisitionError
from src.graph import HydroGraph

__all__ = [
    "OrderingError",
    "assign_stream_order",
    "custom_order",
    "hack_order",
    "shreve_order",
    "strahler_order",
]

WeightFn = Callable[[Mapping[str, Any]], float]


class OrderingError(AcquisitionError):
    """Raised when stream order cannot be computed (unknown method)."""


def _digraph(graph: HydroGraph | nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Return the underlying NetworkX graph for ``graph``."""
    return graph.digraph if isinstance(graph, HydroGraph) else graph


def _topo_nodes(g: nx.MultiDiGraph) -> list[Any]:
    """Return nodes in a cycle-tolerant topological order.

    Acyclic graphs give a true topological sort. When the graph contains
    directed cycles, ordering falls back to the condensation (the DAG of
    strongly-connected components): components are sorted topologically and each
    component's member nodes are emitted together. Nodes inside a cycle are thus
    ordered arbitrarily among themselves but still respect the acyclic structure
    around them, so no cycle ever raises.
    """
    if nx.is_directed_acyclic_graph(g):
        return list(nx.topological_sort(g))
    condensed = nx.condensation(g)
    nodes: list[Any] = []
    for component in nx.topological_sort(condensed):
        nodes.extend(condensed.nodes[component]["members"])
    return nodes


def _incoming_orders(
    g: nx.MultiDiGraph, node: Any, order: dict[int, float]
) -> list[float]:
    """Orders of the segments flowing into ``node`` that are already computed.

    Segments not yet ordered (only possible inside a cycle, where an upstream
    edge may be visited after its head node) are skipped.
    """
    return [
        order[data["segment_id"]]
        for _, _, data in g.in_edges(node, data=True)
        if data["segment_id"] in order
    ]


def strahler_order(graph: HydroGraph | nx.MultiDiGraph) -> dict[int, int]:
    """Compute Strahler order for every segment.

    Source segments are order 1. At a confluence the outgoing segment takes the
    single highest incoming order, incremented by one only when the two highest
    incoming orders tie.
    """
    g = _digraph(graph)
    order: dict[int, float] = {}
    for node in _topo_nodes(g):
        incoming = _incoming_orders(g, node, order)
        if incoming:
            top = max(incoming)
            base = top + 1 if incoming.count(top) >= 2 else top
        else:
            base = None  # headwater node: outgoing segments start at 1
        for _, _, data in g.out_edges(node, data=True):
            order[data["segment_id"]] = 1 if base is None else base
    return {sid: int(v) for sid, v in order.items()}


def shreve_order(graph: HydroGraph | nx.MultiDiGraph) -> dict[int, int]:
    """Compute Shreve magnitude for every segment.

    Source segments are 1; a confluence's outgoing segment is the sum of its
    incoming magnitudes.
    """
    g = _digraph(graph)
    order: dict[int, float] = {}
    for node in _topo_nodes(g):
        incoming = _incoming_orders(g, node, order)
        base = sum(incoming) if incoming else 1
        for _, _, data in g.out_edges(node, data=True):
            order[data["segment_id"]] = base
    return {sid: int(v) for sid, v in order.items()}


def _cumulative_upstream_length(
    g: nx.MultiDiGraph, topo: list[Any]
) -> dict[int, float]:
    """Cumulative upstream length draining through each segment.

    Computed forward in topological order: a segment's cumulative length is its
    own length plus the total cumulative length of everything entering its head
    node.
    """
    cum: dict[int, float] = {}
    for node in topo:
        incoming_total = sum(
            cum.get(data["segment_id"], 0.0)
            for _, _, data in g.in_edges(node, data=True)
        )
        for _, _, data in g.out_edges(node, data=True):
            cum[data["segment_id"]] = incoming_total + data.get("length", 0.0)
    return cum


def hack_order(graph: HydroGraph | nx.MultiDiGraph) -> dict[int, int]:
    """Compute Hack order for every segment.

    The main stem is order 1, growing outward: at each junction the incoming
    segment with the greatest cumulative upstream length continues the parent's
    order, while the remaining tributaries are one greater. Order is assigned in
    reverse topological order (outlets first) so parents are known before their
    tributaries.
    """
    g = _digraph(graph)
    topo = _topo_nodes(g)
    cum = _cumulative_upstream_length(g, topo)

    order: dict[int, int] = {}
    # Reverse topological walk: process a node after its outgoing segments are
    # ordered, then order its incoming segments relative to the main channel.
    for node in reversed(topo):
        out_edges = list(g.out_edges(node, data=True))
        # An outgoing segment may be unordered when it lies inside a cycle;
        # default it to the stem order so the junction still resolves.
        downstream = [
            order[d["segment_id"]]
            for _, _, d in out_edges
            if d["segment_id"] in order
        ]
        parent_order = min(downstream) if downstream else 1

        in_edges = list(g.in_edges(node, data=True))
        if not in_edges:
            continue
        main = max(
            in_edges,
            key=lambda e: (cum[e[2]["segment_id"]], e[2]["segment_id"]),
        )
        main_sid = main[2]["segment_id"]
        for _, _, data in in_edges:
            sid = data["segment_id"]
            order[sid] = parent_order if sid == main_sid else parent_order + 1
    return order


def custom_order(
    graph: HydroGraph | nx.MultiDiGraph, weight: WeightFn
) -> dict[int, float]:
    """Compute a custom per-segment order from a ``weight(edge_data)`` hook.

    The weight function receives each segment's edge-data mapping and returns a
    numeric order. This is the extensibility seam for PRD section 12's "custom
    weighting"; the dispatcher supplies cumulative upstream length by default.
    """
    g = _digraph(graph)
    # Validate acyclicity for parity with the other methods.
    _topo_nodes(g)
    order: dict[int, float] = {}
    for _, _, data in g.edges(data=True):
        order[data["segment_id"]] = weight(data)
    return order


def assign_stream_order(
    graph: HydroGraph | nx.MultiDiGraph, method: str = "strahler"
) -> dict[int, float]:
    """Dispatch to the requested ordering method.

    Args:
        graph: The river-network graph.
        method: One of ``strahler``, ``shreve``, ``hack``, ``custom``.

    Returns:
        Mapping of ``segment_id`` to its computed order.

    Raises:
        OrderingError: If ``method`` is unknown. Cyclic graphs no longer raise;
            see :func:`_topo_nodes` for the cycle-tolerant ordering.
    """
    key = str(method).lower()
    if key == "strahler":
        return strahler_order(graph)
    if key == "shreve":
        return shreve_order(graph)
    if key == "hack":
        return hack_order(graph)
    if key == "custom":
        g = _digraph(graph)
        topo = _topo_nodes(g)
        cum = _cumulative_upstream_length(g, topo)
        return custom_order(graph, lambda data: cum[data["segment_id"]])
    raise OrderingError(
        f"Unknown stream ordering method: {method!r}. "
        "Valid methods are: strahler, shreve, hack, custom."
    )
