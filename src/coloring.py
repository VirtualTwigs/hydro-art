"""Deterministic basin coloring (PRD sections 15-16).

Assigns each watershed a color so that adjacent watersheds maximize contrast,
using **graph coloring followed by palette assignment** — never random colors.
Two watersheds are adjacent when they share a river junction (a graph node with
incident edges in both), so adjacency falls straight out of the hydro graph and
the item #6 watershed grouping without any polygon geometry.

Coloring is a pure, deterministic computation over the in-memory graph and the
``watersheds`` mapping (HUC code -> segment ids): identical inputs always yield
identical colors. It is fully unit-testable with hand-built graphs and watershed
dicts (no GDAL, no real data).
"""

from __future__ import annotations

import networkx as nx

from src.graph import HydroGraph

__all__ = [
    "PALETTES",
    "ColoringError",
    "assign_colors",
    "build_adjacency",
    "get_palette",
    "greedy_color",
]


class ColoringError(Exception):
    """Raised when coloring cannot proceed (e.g. an unknown palette)."""


#: Named color palettes. ``neon`` is the twelve PRD section 16 colors as hex
#: (cyan, electric blue, indigo, purple, violet, magenta, orange, gold, lime,
#: teal, turquoise, green) — vivid, none muted, on a black background.
PALETTES: dict[str, tuple[str, ...]] = {
    "neon": (
        "#00ffff",  # cyan
        "#0a5cff",  # electric blue
        "#4b0082",  # indigo
        "#9d00ff",  # purple
        "#8f00ff",  # violet
        "#ff00ff",  # magenta
        "#ff7a00",  # orange
        "#ffd700",  # gold
        "#aaff00",  # lime
        "#00ffab",  # teal
        "#00e0d1",  # turquoise
        "#00ff5f",  # green
    ),
}


def get_palette(name: str) -> tuple[str, ...]:
    """Return the palette named ``name``.

    Raises:
        ColoringError: If ``name`` is not a known palette.
    """
    try:
        return PALETTES[str(name).lower()]
    except KeyError:
        valid = ", ".join(sorted(PALETTES))
        raise ColoringError(
            f"Unknown palette: {name!r}. Valid palettes are: {valid}."
        ) from None


def _digraph(graph: HydroGraph | nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Return the underlying NetworkX graph for ``graph``."""
    return graph.digraph if isinstance(graph, HydroGraph) else graph


def build_adjacency(
    graph: HydroGraph | nx.MultiDiGraph, watersheds: dict[str, set[int]]
) -> dict[str, set[str]]:
    """Build the watershed adjacency map from shared river junctions.

    Two watershed codes are adjacent when some graph node has incident edges
    (in or out) belonging to both. Every code in ``watersheds`` appears as a key
    (isolated watersheds map to an empty set); self-adjacency is excluded.

    Args:
        graph: The river-network graph; each edge carries a ``segment_id``.
        watersheds: Mapping of HUC code -> set of segment ids (item #6 output).

    Returns:
        Mapping of HUC code -> set of adjacent HUC codes.
    """
    g = _digraph(graph)
    segment_to_code: dict[int, str] = {}
    for code, segment_ids in watersheds.items():
        for segment_id in segment_ids:
            segment_to_code[segment_id] = code

    adjacency: dict[str, set[str]] = {code: set() for code in watersheds}
    for node in g.nodes:
        codes_at_node: set[str] = set()
        for _, _, data in g.in_edges(node, data=True):
            code = segment_to_code.get(data.get("segment_id"))
            if code is not None:
                codes_at_node.add(code)
        for _, _, data in g.out_edges(node, data=True):
            code = segment_to_code.get(data.get("segment_id"))
            if code is not None:
                codes_at_node.add(code)
        for code in codes_at_node:
            adjacency[code].update(codes_at_node - {code})
    return adjacency


def greedy_color(adjacency: dict[str, set[str]]) -> dict[str, int]:
    """Assign a color-class index to each watershed via greedy Welsh-Powell.

    Vertices are ordered by descending adjacency degree, ties broken by code, so
    the result is fully deterministic. Each vertex takes the lowest color index
    not used by its already-colored neighbors — a proper coloring using at most
    ``max_degree + 1`` classes.

    Args:
        adjacency: Mapping of code -> adjacent codes (see :func:`build_adjacency`).

    Returns:
        Mapping of code -> color-class index (0-based).
    """
    order = sorted(adjacency, key=lambda code: (-len(adjacency[code]), code))
    colors: dict[str, int] = {}
    for code in order:
        used = {colors[nbr] for nbr in adjacency[code] if nbr in colors}
        index = 0
        while index in used:
            index += 1
        colors[code] = index
    return colors


def assign_colors(
    graph: HydroGraph | nx.MultiDiGraph,
    watersheds: dict[str, set[int]],
    palette: str = "neon",
) -> dict[str, str]:
    """Assign each watershed a hex color maximizing contrast with neighbors.

    Composes adjacency -> greedy graph coloring -> palette lookup. Color classes
    map to ``palette[index % len(palette)]``; when the number of classes does not
    exceed the palette size (the common case for the 12-color neon palette),
    adjacent watersheds always get distinct colors. Deterministic: identical
    inputs yield identical colors.

    Args:
        graph: The river-network graph.
        watersheds: Mapping of HUC code -> set of segment ids.
        palette: Named palette (see :data:`PALETTES`).

    Returns:
        Mapping of HUC code -> hex color string.

    Raises:
        ColoringError: If ``palette`` is unknown.
    """
    colors = get_palette(palette)
    classes = greedy_color(build_adjacency(graph, watersheds))
    return {code: colors[index % len(colors)] for code, index in classes.items()}
