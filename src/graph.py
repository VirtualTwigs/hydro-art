"""Directed river-network graph construction (PRD section 14).

Turns the clipped flowline geometries into a directed graph whose nodes are
river junctions (snapped segment endpoints) and whose edges are river segments
oriented downstream (first vertex -> last vertex, following NHD digitizing
direction). A thin :class:`HydroGraph` wraps ``networkx.MultiDiGraph`` — a
*multi* graph so genuinely parallel/braided channels between the same two
junctions are preserved — and exposes upstream/downstream traversal, basin
extraction, and network statistics without leaking NetworkX internals.

Construction is a pure function over shapely geometries + NetworkX, so it is
fully unit-testable with hand-built line networks (no GDAL, no real data).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Any

import networkx as nx

from src.clipping import is_boundary_layer
from src.loading import Layer

__all__ = ["HydroGraph", "NetworkStats", "build_graph"]

Node = tuple[float, float]


@dataclass(frozen=True)
class NetworkStats:
    """Immutable summary of a constructed river network."""

    num_nodes: int = 0
    num_edges: int = 0
    num_sources: int = 0
    num_outlets: int = 0
    total_length: float = 0.0


def _iter_segments(geom: Any) -> Iterator[Any]:
    """Yield the LineString parts of a (possibly multi) line geometry."""
    if geom is None or geom.is_empty:
        return
    kind = geom.geom_type
    if kind == "LineString":
        yield geom
    elif kind == "MultiLineString":
        for part in geom.geoms:
            if not part.is_empty:
                yield part
    # Non-line geometries (e.g. stray points/polygons) are not segments.


def _snap(coord: tuple[float, float], tolerance: float) -> Node:
    """Snap a coordinate to a shared junction key.

    With ``tolerance <= 0`` coordinates are rounded to sub-metric precision so
    bit-coincident endpoints collapse; a positive tolerance snaps to a grid.
    """
    x, y = coord[0], coord[1]
    if tolerance and tolerance > 0:
        return (round(x / tolerance) * tolerance, round(y / tolerance) * tolerance)
    return (round(x, 6), round(y, 6))


class HydroGraph:
    """A directed river network over ``networkx.MultiDiGraph``."""

    def __init__(self, digraph: nx.MultiDiGraph, dropped_degenerate: int = 0) -> None:
        self._g = digraph
        self.dropped_degenerate = dropped_degenerate

    @property
    def digraph(self) -> nx.MultiDiGraph:
        """The underlying NetworkX graph (for advanced use)."""
        return self._g

    def sources(self) -> list[Node]:
        """Headwater junctions: nothing flows into them (in-degree 0)."""
        return [n for n in self._g if self._g.in_degree(n) == 0]

    def outlets(self) -> list[Node]:
        """Terminal junctions: nothing flows out of them (out-degree 0)."""
        return [n for n in self._g if self._g.out_degree(n) == 0]

    def upstream(self, node: Node) -> set[Node]:
        """All junctions that flow to ``node`` (graph ancestors)."""
        return nx.ancestors(self._g, node)

    def downstream(self, node: Node) -> set[Node]:
        """All junctions ``node`` flows to (graph descendants)."""
        return nx.descendants(self._g, node)

    def basin(self, node: Node) -> set[int]:
        """Segment ids of everything draining to ``node`` (node + ancestors)."""
        nodes = nx.ancestors(self._g, node) | {node}
        sub = self._g.subgraph(nodes)
        return {data["segment_id"] for _, _, data in sub.edges(data=True)}

    def statistics(self) -> NetworkStats:
        """Summarize the network."""
        total_length = sum(data["length"] for _, _, data in self._g.edges(data=True))
        return NetworkStats(
            num_nodes=self._g.number_of_nodes(),
            num_edges=self._g.number_of_edges(),
            num_sources=len(self.sources()),
            num_outlets=len(self.outlets()),
            total_length=total_length,
        )


def build_graph(layers: Iterable[Layer], snap_tolerance: float = 0.0) -> HydroGraph:
    """Construct a :class:`HydroGraph` from flowline layers.

    Boundary (WBD) layers are skipped; MultiLineStrings are exploded into
    component segments; segments whose endpoints snap to the same junction are
    dropped-and-counted.
    """
    graph = nx.MultiDiGraph()
    dropped = 0
    segment_id = 0

    for layer in layers:
        if is_boundary_layer(layer):
            continue
        for geom in layer.geometries:
            for segment in _iter_segments(geom):
                coords = list(segment.coords)
                if len(coords) < 2:
                    dropped += 1
                    continue
                start = _snap(coords[0], snap_tolerance)
                end = _snap(coords[-1], snap_tolerance)
                if start == end:
                    dropped += 1
                    continue
                graph.add_edge(
                    start,
                    end,
                    segment_id=segment_id,
                    geometry=segment,
                    length=segment.length,
                    huc4=layer.huc4,
                )
                segment_id += 1

    return HydroGraph(graph, dropped_degenerate=dropped)
