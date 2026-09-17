"""Watershed (HUC) grouping over the river-network graph (PRD section 13).

Groups river segments into hydrologic units by their HUC code. HUC codes are
hierarchical *prefixes*: a segment's 4-digit ``huc4`` determines its HUC2 (first
two digits) and HUC4 (all four). Grouping truncates each segment's ``huc4`` to
the digit count of the requested level.

Levels finer than the available data (HUC6–HUC12) require sub-HUC boundary
polygons we do not yet load, so they degrade to full ``huc4`` grouping and emit
a single warning. The function signature is stable, so finer WBD layers can drop
in later without an API change.

Grouping is a pure computation over a ``networkx.MultiDiGraph`` and is fully
unit-testable with hand-built graphs carrying per-edge ``huc4`` (no GDAL, no
real data).
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import networkx as nx

from src.graph import HydroGraph

__all__ = [
    "HUC_LEVEL_DIGITS",
    "WatershedStats",
    "group_segments_by_huc",
    "watershed_stats",
]

#: HUC level name -> number of significant digits in the code.
HUC_LEVEL_DIGITS: dict[str, int] = {
    "HUC2": 2,
    "HUC4": 4,
    "HUC6": 6,
    "HUC8": 8,
    "HUC10": 10,
    "HUC12": 12,
}

#: Digits available from the data we currently load (WBDHU4 -> 4-digit codes).
_AVAILABLE_DIGITS = 4


@dataclass(frozen=True)
class WatershedStats:
    """Immutable summary of a watershed grouping."""

    num_watersheds: int = 0
    num_segments: int = 0


def _digraph(graph: HydroGraph | nx.MultiDiGraph) -> nx.MultiDiGraph:
    """Return the underlying NetworkX graph for ``graph``."""
    return graph.digraph if isinstance(graph, HydroGraph) else graph


def group_segments_by_huc(
    graph: HydroGraph | nx.MultiDiGraph, level: str
) -> dict[str, set[int]]:
    """Group segment ids by their HUC code at ``level``.

    Args:
        graph: The river-network graph; each edge carries a ``huc4`` string.
        level: One of :data:`HUC_LEVEL_DIGITS` (e.g. ``"HUC4"``).

    Returns:
        Mapping of HUC code (truncated to the level's digit count) to the set of
        segment ids in that watershed. Segments with no ``huc4`` are skipped.

    Raises:
        KeyError: If ``level`` is not a known HUC level.
    """
    digits = HUC_LEVEL_DIGITS[str(level).upper()]
    if digits > _AVAILABLE_DIGITS:
        warnings.warn(
            f"{level} is finer than the available HUC4 data; "
            f"grouping by HUC4 instead.",
            stacklevel=2,
        )
        digits = _AVAILABLE_DIGITS

    g = _digraph(graph)
    groups: dict[str, set[int]] = {}
    for _, _, data in g.edges(data=True):
        huc4 = data.get("huc4")
        if not huc4:
            continue
        code = str(huc4)[:digits]
        groups.setdefault(code, set()).add(data["segment_id"])
    return groups


def watershed_stats(groups: dict[str, set[int]]) -> WatershedStats:
    """Summarize a grouping produced by :func:`group_segments_by_huc`."""
    return WatershedStats(
        num_watersheds=len(groups),
        num_segments=sum(len(ids) for ids in groups.values()),
    )
